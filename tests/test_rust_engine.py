"""Compare the native Rust/Wasm core with frozen v1 invariants and independent readers.

Renderer antialiasing and polygon simplification may move draft-detail boundaries
by a fraction of a millimeter. Topology of the synthetic hole fixtures, layout
choices, validity, material alignment, and error/recovery decisions are exact.
"""

import io
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pytest
import trimesh

ROOT = Path(__file__).resolve().parents[1]
CORPUS = json.loads((ROOT / "tests/fixtures/reference-v1.json").read_text())["cases"]
BINARY = ROOT / "target/release/relief-native"


@pytest.fixture(scope="module")
def corpus_results(tmp_path_factory):
    assert BINARY.is_file(), "Build the native engine before tests: cargo build --release"
    folder = tmp_path_factory.mktemp("rust-corpus")
    process = subprocess.Popen(
        [str(BINARY), "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    results = {}
    try:
        for case in CORPUS:
            pack = folder / f"{case['name']}.zip"
            request = {
                "input": str(ROOT / case["source"]),
                "settings": case["settings"],
                "output": str(pack),
            }
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            line = process.stdout.readline()
            assert line, f"Rust engine exited while building {case['name']}"
            results[case["name"]] = json.loads(line), pack
    finally:
        process.stdin.close()
        process.wait(timeout=20)
    assert process.returncode == 0
    return results


@pytest.mark.parametrize("case", CORPUS, ids=lambda c: c["name"])
def test_reference_decisions_and_geometric_invariants(case, corpus_results):
    result, pack = corpus_results[case["name"]]
    if "error" in case:
        assert "error" in result
        assert not pack.exists()
        return
    assert "error" not in result, result
    expected, actual = case["manifest"], result["manifest"]
    assert actual["settings"] == {
        **expected["settings"],
        "border_material": "artwork",
        "border_color": "#c99b48",
    }
    for key in ("grid", "piece_count", "plate_count"):
        assert actual[key] == expected[key]
    assert actual["physically_tested"] is False
    assert actual["units"] == "mm"
    assert result["artwork"]["area"] == pytest.approx(case["artwork"]["area"], rel=0.025)
    assert result["artwork"]["bounds"] == pytest.approx(case["artwork"]["bounds"], abs=0.6)
    if case["name"] in {"gold-holes", "raster-holes", "raster-light", "icon"}:
        assert result["artwork"]["holes"] == case["artwork"]["holes"]
        assert result["artwork"]["regions"] == case["artwork"]["regions"]
    for old, new in zip(expected["pieces"], actual["pieces"], strict=True):
        assert new["id"] == old["id"]
        assert new["material_parts"] == old["material_parts"]
        assert new["extents_mm"] == pytest.approx(old["extents_mm"], abs=0.6)
        assert new["assembly_origin_mm"] == pytest.approx(old["assembly_origin_mm"], abs=0.6)
        assert new["volume_mm3"] == pytest.approx(old["volume_mm3"], rel=0.015)
        assert new["watertight"] is True


@pytest.mark.parametrize("case", [c for c in CORPUS if "error" not in c], ids=lambda c: c["name"])
def test_exports_have_closed_aligned_meshes_and_bambu_metadata(case, corpus_results):
    result, pack = corpus_results[case["name"]]
    assert "error" not in result, result
    with ZipFile(pack) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest == result["manifest"]
        for name in ["artwork.svg", "assembly.svg", "pieces.svg"]:
            ET.fromstring(archive.read(name))
        assert archive.read("preview.png").startswith(b"\x89PNG")
        assert not any(name.endswith((".jpg", ".webp")) for name in archive.namelist())
        for piece in manifest["pieces"]:
            meshes = {}
            for material in ["combined", "background", "artwork"]:
                path = piece["files"].get(material)
                if not path:
                    continue
                mesh = trimesh.load_mesh(io.BytesIO(archive.read(path)), file_type="stl")
                assert mesh.is_watertight and mesh.is_winding_consistent and mesh.is_volume
                assert np.isfinite(mesh.vertices).all()
                meshes[material] = mesh
            assert meshes["combined"].body_count == 1
            assert meshes["combined"].extents == pytest.approx(piece["extents_mm"], abs=1e-4)
            if "artwork" in meshes:
                assert meshes["artwork"].bounds[0, 2] == pytest.approx(
                    manifest["settings"]["base_mm"]
                )
                assert meshes["combined"].volume == pytest.approx(
                    meshes["background"].volume + meshes["artwork"].volume, rel=1e-5
                )
        for name in [n for n in archive.namelist() if n.endswith(".3mf")]:
            data = archive.read(name)
            scene = trimesh.load_scene(io.BytesIO(data), file_type="3mf")
            assert all(mesh.is_volume for mesh in scene.geometry.values())
            assert scene.bounds[0, :2].min() >= -1e-5
            assert scene.bounds[1, :2].max() <= 256 + 1e-5
            with ZipFile(io.BytesIO(data)) as project:
                settings = json.loads(project.read("Metadata/project_settings.config"))
                assert settings["nozzle_diameter"] == ["0.4"]
                assert settings["filament_colour"] == [
                    manifest["settings"]["background_color"].upper(),
                    manifest["settings"]["artwork_color"].upper(),
                ]
                config = ET.fromstring(project.read("Metadata/model_settings.config"))
                ns = {"c": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
                model = ET.fromstring(project.read("3D/3dmodel.model"))
                assert model.find("c:metadata[@name='Application']", ns).text == (
                    "BambuStudio-02.00.00.00"
                )
                objects = {o.attrib["id"]: o for o in model.findall("c:resources/c:object", ns)}
                build_ids = {e.attrib["objectid"] for e in model.findall("c:build/c:item", ns)}
                assert {o.attrib["id"] for o in config.findall("object")} == build_ids
                for obj in config.findall("object"):
                    group = objects[obj.attrib["id"]]
                    assert {p.attrib["id"] for p in obj.findall("part")} == {
                        c.attrib["objectid"] for c in group.findall("c:components/c:component", ns)
                    }
                    for part in obj.findall("part"):
                        assert int(part.find("metadata[@key='extruder']").attrib["value"]) == (
                            int(objects[part.attrib["id"]].attrib["pindex"]) + 1
                        )


def native_request(request):
    result = subprocess.run(
        [str(BINARY), "--batch"], input=json.dumps(request) + "\n",
        text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_raster_formats_and_orientation(tmp_path, format):
    from PIL import Image, ImageDraw

    from relief_studio.geometry import build_project
    from relief_studio.settings import Settings

    image = Image.new("RGB", (140, 90), "white")
    ImageDraw.Draw(image).rectangle((15, 10, 105, 65), fill="black")
    source = tmp_path / f"source.{format.lower()}"
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, format=format, exif=exif)
    result = native_request({"input": str(source), "settings": {"detail": "draft"}})
    assert "error" not in result, result
    reference = build_project(source.read_bytes(), Settings(detail="draft"))
    assert result["artwork"]["area"] == pytest.approx(reference.vector.area, rel=0.01)
    assert result["artwork"]["bounds"] == pytest.approx(reference.vector.bounds, abs=0.1)


def test_native_export_never_overwrites_source_and_recovers(tmp_path):
    source = tmp_path / "drawing.svg"
    data = (ROOT / "tests/fixtures/gold-cutout.svg").read_bytes()
    source.write_bytes(data)
    request = {"input": str(source), "output": str(source)}
    assert "error" in native_request(request)
    assert source.read_bytes() == data
    request["output"] = str(tmp_path / "new-pack.zip")
    assert "error" not in native_request(request)


def test_native_rejects_raster_pixel_bomb_before_geometry(tmp_path):
    from PIL import Image

    source = tmp_path / "large.png"
    Image.new("L", (5000, 5000), "black").save(source)
    result = native_request({"input": str(source)})
    assert "24 megapixel" in result["error"]["detail"]


@pytest.mark.parametrize("profile,hanging", [
    ("flat", "none"), ("rounded", "loops"), ("beaded", "none"), ("flat", "keyholes"),
])
def test_inverted_contour_exports_preserve_backing_and_material_alignment(
    tmp_path, profile, hanging,
):
    settings = {
        "shape": "contour", "width_mm": 120, "height_mm": 180,
        "frame_profile": profile, "hanging": hanging, "base_mm": 5,
    }
    packs = []
    for invert in [False, True, False]:
        pack = tmp_path / f"contour-{len(packs)}.zip"
        result = native_request({
            "input": str(ROOT / "tests/fixtures/contour-icon.svg"),
            "settings": {**settings, "invert": invert}, "output": str(pack),
        })
        assert "error" not in result, result
        with ZipFile(pack) as archive:
            piece = result["manifest"]["pieces"][0]
            meshes = {
                name: trimesh.load_mesh(
                    io.BytesIO(archive.read(piece["files"][name])), file_type="stl",
                )
                for name in ["background", "artwork", "combined"]
            }
            assert all(mesh.is_volume for mesh in meshes.values())
            assert meshes["combined"].body_count == 1
            assert meshes["artwork"].bounds[0, 2] == pytest.approx(settings["base_mm"])
            assert meshes["combined"].volume == pytest.approx(
                meshes["background"].volume + meshes["artwork"].volume, rel=1e-5,
            )
            for name in [n for n in archive.namelist() if n.endswith(".3mf")]:
                scene = trimesh.load_scene(io.BytesIO(archive.read(name)), file_type="3mf")
                assert all(mesh.is_volume for mesh in scene.geometry.values())
                with ZipFile(io.BytesIO(archive.read(name))) as project:
                    config = ET.fromstring(project.read("Metadata/model_settings.config"))
                    assert {part.find("metadata[@key='extruder']").attrib["value"]
                            for part in config.findall("object/part")} == {"1", "2"}
            packs.append((result, archive.read(piece["files"]["background"])))
    normal, inverted, restored = packs
    assert normal[1] == inverted[1] == restored[1]
    assert normal[0] == restored[0]
    assert inverted[0]["artwork"]["area"] != normal[0]["artwork"]["area"]
    assert inverted[0]["manifest"]["pieces"][0]["extents_mm"] == pytest.approx(
        normal[0]["manifest"]["pieces"][0]["extents_mm"], abs=1e-5,
    )
