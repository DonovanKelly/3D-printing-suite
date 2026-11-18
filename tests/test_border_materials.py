"""Independently reopen Rust material exports and verify border color assignments.

Color changes must preserve the full piece while keeping closed, non-overlapping
material volumes in shared coordinates and consistent Bambu/Core filament IDs.
"""

import io
import json
from itertools import combinations
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pytest
import trimesh
from test_rust_engine import ROOT, native_request

NS = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def check_3mf(data, colors):
    scene = trimesh.load_scene(io.BytesIO(data), file_type="3mf")
    assert all(mesh.is_volume for mesh in scene.geometry.values())
    with ZipFile(io.BytesIO(data)) as archive:
        settings = json.loads(archive.read("Metadata/project_settings.config"))
        assert settings["filament_colour"] == colors
        assert settings["nozzle_diameter"] == ["0.4"]
        for key in [
            "filament_settings_id",
            "filament_diameter",
            "filament_type",
            "filament_is_support",
            "filament_soluble",
            "filament_ids",
        ]:
            assert len(settings[key]) == len(colors)
        assert settings["inherits_group"] == [
            "0.20mm Standard @BBL X1C",
            *["Generic PLA"] * len(colors),
            "Bambu Lab P1S 0.4 nozzle",
        ]
        assert settings["different_settings_to_system"] == [
            "",
            *["filament_colour"] * len(colors),
            "",
        ]
        model = ET.fromstring(archive.read("3D/3dmodel.model"))
        resources = model.find("c:resources", NS)
        resource_ids = [node.attrib["id"] for node in resources]
        assert len(resource_ids) == len(set(resource_ids))
        assert [
            base.attrib["displaycolor"]
            for base in model.findall(
                "c:resources/c:basematerials/c:base",
                NS,
            )
        ] == colors
        objects = {node.attrib["id"]: node for node in model.findall("c:resources/c:object", NS)}
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
        slots = set()
        for obj in config.findall("object"):
            group = objects[obj.attrib["id"]]
            parts = obj.findall("part")
            assert {part.attrib["id"] for part in parts} == {
                node.attrib["objectid"] for node in group.findall("c:components/c:component", NS)
            }
            for part in parts:
                slot = int(part.find("metadata[@key='extruder']").attrib["value"])
                mesh = objects[part.attrib["id"]]
                assert slot == int(mesh.attrib["pindex"]) + 1
                assert 1 <= slot <= len(colors)
                if mesh.attrib["name"] == "Border":
                    assert slot == 3
                slots.add(slot)
        return slots


@pytest.mark.parametrize(
    "shape,profile,hanging,layout",
    [
        ("rectangle", "flat", "none", "plaque"),
        ("rectangle", "rounded", "loops", "plaque"),
        ("rectangle", "beaded", "none", "plaque"),
        ("contour", "flat", "keyholes", "plaque"),
        ("contour", "rounded", "loops", "plaque"),
        ("contour", "beaded", "none", "plaque"),
        ("rectangle", "flat", "none", "tiles"),
        ("rectangle", "flat", "none", "puzzle"),
    ],
)
def test_material_assignments_preserve_shape_and_aligned_volume(
    tmp_path,
    shape,
    profile,
    hanging,
    layout,
):
    baseline = None
    settings = {
        "shape": shape,
        "frame_profile": profile,
        "hanging": hanging,
        "layout": layout,
        "width_mm": 120,
        "height_mm": 120,
        "detail": "draft",
        "base_mm": 5,
        "background_color": "#112233",
        "artwork_color": "#c3d4e5",
        "border_color": "#c99b48",
    }
    if layout != "plaque":
        settings.update(columns=3, rows=3)
    for mode in ["artwork", "background", "custom"]:
        pack = tmp_path / f"{mode}.zip"
        result = native_request(
            {
                "input": str(ROOT / "tests/fixtures/contour-icon.svg"),
                "settings": {**settings, "border_material": mode},
                "output": str(pack),
            }
        )
        assert "error" not in result, result
        manifest = result["manifest"]
        if baseline is None:
            baseline = manifest
        with ZipFile(pack) as archive:
            assert json.loads(archive.read("project.json"))["border_material"] == mode
            if mode == "custom":
                assert b"#c99b48" in archive.read("assembly.svg")
                assert b"#c99b48" in archive.read("pieces.svg")
                assert b"3 = Border" in archive.read("PRINTING.md")
            if layout != "plaque":
                center = next(p for p in manifest["pieces"] if p["row"] == p["column"] == 2)
                assert "border" not in center["files"]
            for piece, original in zip(manifest["pieces"], baseline["pieces"], strict=True):
                assert piece["assembly_origin_mm"] == original["assembly_origin_mm"]
                assert piece["extents_mm"] == original["extents_mm"]
                assert piece["volume_mm3"] == pytest.approx(original["volume_mm3"], rel=1e-8)
                meshes = {
                    material: trimesh.load_mesh(io.BytesIO(archive.read(path)), file_type="stl")
                    for material, path in piece["files"].items()
                    if material != "3mf"
                }
                assert all(m.is_volume and m.is_watertight for m in meshes.values())
                combined = meshes.pop("combined")
                assert combined.body_count == 1
                assert combined.extents == pytest.approx(piece["extents_mm"], abs=1e-4)
                assert sum(m.volume for m in meshes.values()) == pytest.approx(
                    combined.volume, rel=1e-5
                )
                assert len(meshes) == piece["material_parts"]
                assert ("border" in meshes) == (
                    mode == "custom"
                    and (piece["row"] != 2 or piece["column"] != 2 or layout == "plaque")
                )
                for material, mesh in meshes.items():
                    if material != "background":
                        assert mesh.bounds[0, 2] == pytest.approx(settings["base_mm"])
                    assert np.isfinite(mesh.vertices).all()
                for a, b in combinations(meshes.values(), 2):
                    assert trimesh.boolean.intersection([a, b], engine="manifold").volume < 1e-3
            colors = ["#112233", "#C3D4E5"] + (["#C99B48"] if mode == "custom" else [])
            slots = set()
            for name in archive.namelist():
                if name.endswith(".3mf"):
                    slots.update(check_3mf(archive.read(name), colors))
            assert slots == set(range(1, len(colors) + 1))


def test_equal_display_colors_still_assign_the_border_to_filament_three(tmp_path):
    pack = tmp_path / "equal-colors.zip"
    result = native_request(
        {
            "settings": {
                "detail": "draft",
                "border_material": "custom",
                "background_color": "#123456",
                "artwork_color": "#123456",
                "border_color": "#123456",
            },
            "output": str(pack),
        }
    )
    assert "error" not in result, result
    with ZipFile(pack) as archive:
        assert check_3mf(archive.read("plates/plate-01.3mf"), ["#123456"] * 3) == {1, 2, 3}
