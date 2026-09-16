"""Regress Bambu project import: one nozzle, two filaments, and aligned named parts.

Core display colors alone did not satisfy Bambu Studio's project-config check
and did not assign filaments. Inspect the downloaded archive, not just meshes.
"""

import json
import os
import subprocess
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pytest
import trimesh

from relief_studio.cli import sample_bytes
from relief_studio.exports import CORE, project_manifest, write_3mf, write_plate_3mf
from relief_studio.geometry import build_project
from relief_studio.packing import plan_plates
from relief_studio.settings import Settings


def placed_meshes(path):
    # Studio saves several mesh objects in each Production-extension subfile.
    # Resolve (path, objectid) together: trimesh's 3MF reader currently combines
    # every mesh in that subfile for each reference, hiding material alignment.
    ns = {"c": CORE}
    production = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
    with ZipFile(path) as archive:
        models = {
            name: ET.fromstring(archive.read(name))
            for name in archive.namelist()
            if name.endswith(".model")
        }

    def transform(element):
        matrix = np.eye(4)
        if "transform" in element.attrib:
            matrix[:3, :] = (
                np.array(element.attrib["transform"].split(), dtype=float).reshape(4, 3).T
            )
        return matrix

    def resolve(filename, object_id, placement):
        obj = models[filename].find(f"c:resources/c:object[@id='{object_id}']", ns)
        mesh = obj.find("c:mesh", ns)
        if mesh is not None:
            vertices = [
                [float(v.attrib[k]) for k in "xyz"] for v in mesh.findall("c:vertices/c:vertex", ns)
            ]
            faces = [
                [int(t.attrib[k]) for k in ("v1", "v2", "v3")]
                for t in mesh.findall("c:triangles/c:triangle", ns)
            ]
            solid = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            solid.apply_transform(placement)
            yield solid
        for component in obj.findall("c:components/c:component", ns):
            part_file = component.attrib.get(f"{{{production}}}path", filename).lstrip("/")
            yield from resolve(
                part_file, component.attrib["objectid"], placement @ transform(component)
            )

    return [
        mesh
        for item in models["3D/3dmodel.model"].findall("c:build/c:item", ns)
        for mesh in resolve("3D/3dmodel.model", item.attrib["objectid"], transform(item))
    ]


@pytest.mark.parametrize("layout", ["plaque", "tiles", "puzzle"])
@pytest.mark.parametrize("colors", [("#123456", "#abcdef"), ("#123456", "#123456")])
def test_bambu_project_contains_config_and_matching_filament_assignments(tmp_path, layout, colors):
    project = build_project(
        sample_bytes(),
        Settings(layout=layout, background_color=colors[0], artwork_color=colors[1]),
    )
    paths = []
    for index, plate in enumerate(plan_plates(project)):
        path = tmp_path / f"plate-{index}.3mf"
        write_plate_3mf(project, path, plate)
        paths.append(path)
    for piece in project.pieces:
        path = tmp_path / f"{piece.tile.name}.3mf"
        write_3mf(piece, project, path)
        paths.append(path)

    for path in paths:
        with ZipFile(path) as archive:
            config = json.loads(archive.read("Metadata/project_settings.config"))
            # The P1S switches two filaments through ONE physical nozzle. Missing
            # nozzle_diameter triggers Bambu's "invalid config" geometry-only fallback.
            assert config["nozzle_diameter"] == ["0.4"]
            assert config["filament_colour"] == [color.upper() for color in colors]
            assert config["filament_type"] == ["PLA", "PLA"]
            assert config["filament_is_support"] == ["0", "0"]
            assert len(config["filament_settings_id"]) == 2
            assert len(config["inherits_group"]) == 4
            assert config["printer_settings_id"] == "Bambu Lab P1S 0.4 nozzle"

            root = ET.fromstring(archive.read("3D/3dmodel.model"))
            ns = {"c": CORE}
            assert root.find("c:metadata[@name='Application']", ns).text == (
                "BambuStudio-02.00.00.00"
            )
            assert "Relief Studio" in root.find("c:metadata[@name='Description']", ns).text
            objects = {o.attrib["id"]: o for o in root.findall("c:resources/c:object", ns)}
            model_config = ET.fromstring(archive.read("Metadata/model_settings.config"))
            settings = {o.attrib["id"]: o for o in model_config.findall("object")}
            build_ids = {i.attrib["objectid"] for i in root.findall("c:build/c:item", ns)}
            assert set(settings) == build_ids
            instances = model_config.findall("plate/model_instance")
            assert {i.find("metadata[@key='object_id']").attrib["value"] for i in instances} == (
                build_ids
            )
            for object_id, metadata in settings.items():
                group = objects[object_id]
                assert (
                    metadata.find("metadata[@key='name']").attrib["value"] == (group.attrib["name"])
                )
                parts = {p.attrib["id"]: p for p in metadata.findall("part")}
                assert set(parts) == {
                    c.attrib["objectid"] for c in group.findall("c:components/c:component", ns)
                }
                for part_id, part in parts.items():
                    mesh = objects[part_id]
                    assert part.attrib["subtype"] == "normal_part"
                    assert part.find("metadata[@key='name']").attrib["value"] == mesh.attrib["name"]
                    assert int(part.find("metadata[@key='extruder']").attrib["value"]) == (
                        int(mesh.attrib["pindex"]) + 1
                    )

            types = ET.fromstring(archive.read("[Content_Types].xml"))
            overrides = {
                e.attrib["PartName"]: e.attrib["ContentType"]
                for e in types
                if (e.tag.endswith("Override"))
            }
            assert overrides["/Metadata/project_settings.config"] == "application/json"
            assert overrides["/Metadata/model_settings.config"] == "application/xml"
        scene = trimesh.load_scene(path)
        assert all(mesh.is_volume for mesh in scene.geometry.values())


def test_background_only_piece_keeps_valid_part_ids(tmp_path):
    data = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        b'<rect width="20" height="20"/></svg>'
    )
    project = build_project(
        data,
        Settings(
            layout="tiles",
            columns=2,
            rows=1,
            frame=False,
            crop_to_artwork=False,
            margin_mm=0,
        ),
    )
    piece = next(p for p in project.pieces if p.artwork is None)
    path = tmp_path / "background-only.3mf"
    write_3mf(piece, project, path)
    with ZipFile(path) as archive:
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
        parts = config.findall("object/part")
        assert len(parts) == 1
        assert parts[0].attrib["id"] == "2"
        assert parts[0].find("metadata[@key='extruder']").attrib["value"] == "1"
        assert config.find("object/metadata[@key='extruder']").attrib["value"] == "1"


def test_p1s_exclusion_zone_rejects_full_bed_and_recovers(tmp_path):
    project = build_project(
        sample_bytes(),
        Settings(
            width_mm=250,
            height_mm=250,
            bed_width_mm=256,
            bed_height_mm=256,
        ),
    )
    with pytest.raises(ValueError, match="exclusion zone"):
        project_manifest(project)
    with pytest.raises(ValueError, match="exclusion zone"):
        write_3mf(project.pieces[0], project, tmp_path / "invalid.3mf")
    assert not (tmp_path / "invalid.3mf").exists()
    recovered = build_project(sample_bytes(), Settings(width_mm=230, height_mm=230))
    path = tmp_path / "recovered.3mf"
    write_3mf(recovered.pieces[0], recovered, path)
    bounds = np.array([m.bounds for m in placed_meshes(path)])
    assert bounds[:, 0, 0].min() >= 23 - 1e-5
    assert bounds[:, 1, :2].max() <= 256 + 1e-5
    assert project_manifest(recovered)["plates"][0]["pieces"][0]["origin_mm"] == [23, 13, 0]


@pytest.mark.skipif(not os.environ.get("RELIEF_TEST_BAMBU"), reason="Bambu Studio not configured")
@pytest.mark.parametrize("layout", ["plaque", "puzzle"])
def test_bambu_studio_roundtrip_and_geometry_only_failure(tmp_path, layout):
    project = build_project(
        sample_bytes(),
        Settings(
            layout=layout,
            width_mm=90,
            height_mm=90,
            background_color="#FAFAFA",
            artwork_color="#D4A62A",
        ),
    )
    path = tmp_path / "corrected.3mf"
    write_plate_3mf(project, path, plan_plates(project)[0])

    def studio(source, name):
        settings = tmp_path / f"{name}.json"
        saved = tmp_path / f"{name}.3mf"
        result = subprocess.run(
            [
                os.environ["RELIEF_TEST_BAMBU"],
                "--datadir",
                str(tmp_path / "studio"),
                "--arrange",
                "0",
                "--orient",
                "0",
                "--info",
                "--export-settings",
                str(settings),
                "--export-3mf",
                str(saved),
                str(source),
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        (tmp_path / f"{name}.log").write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(settings.read_text()), saved

    # Retain the original failure boundary: geometry is accepted but its colors
    # do not become project filaments without the Bambu project configuration.
    legacy = tmp_path / "geometry-only.3mf"
    with ZipFile(path) as original, ZipFile(legacy, "w") as archive:
        for name in ("[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"):
            content = original.read(name)
            if name == "3D/3dmodel.model":
                root = ET.fromstring(content)
                root.remove(root.find(f"{{{CORE}}}metadata[@name='Application']"))
                content = ET.tostring(root)
            elif name == "[Content_Types].xml":
                root = ET.fromstring(content)
                for child in list(root):
                    if child.tag.endswith("Override"):
                        root.remove(child)
                content = ET.tostring(root)
            archive.writestr(name, content)
    old_config, _ = studio(legacy, "legacy-import")
    assert len(old_config["filament_colour"]) == 1

    imported, saved = studio(path, "recovered-import")
    assert imported["filament_colour"] == ["#FAFAFA", "#D4A62A"]
    assert imported["nozzle_diameter"] == ["0.4"]
    assert imported["printer_settings_id"] == "Bambu Lab P1S 0.4 nozzle"
    with ZipFile(saved) as archive:
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
        objects = config.findall("object")
        assert len(objects) == len(project.pieces)
        for obj in objects:
            parts = obj.findall("part")
            assert [p.find("metadata[@key='extruder']").attrib["value"] for p in parts] == [
                "1",
                "2",
            ]
            assert [p.find("metadata[@key='name']").attrib["value"] for p in parts] == [
                "Background",
                "Artwork + frame",
            ]
            for part in parts:
                stats = part.find("mesh_stat").attrib
                assert all(int(value) == 0 for key, value in stats.items() if key != "face_count")
    original_meshes = placed_meshes(path)
    saved_meshes = placed_meshes(saved)
    assert len(saved_meshes) == len(original_meshes)
    for before, after in zip(original_meshes, saved_meshes, strict=True):
        assert after.is_volume
        assert after.bounds == pytest.approx(before.bounds, abs=1e-4)
        assert after.volume == pytest.approx(before.volume, rel=1e-5)
