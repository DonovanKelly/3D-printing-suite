"""Exercise fabrication invariants across tracing, partitions, material solids, and exports."""

import io
import json
from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pytest
import trimesh
from PIL import Image, ImageDraw
from pydantic import ValidationError
from shapely.geometry import Point, box
from shapely.ops import unary_union

from relief_studio.artwork import load_image, trace_image
from relief_studio.cli import sample_bytes
from relief_studio.exports import CORE, export_project
from relief_studio.geometry import build_project
from relief_studio.layout import choose_layout, partition
from relief_studio.settings import Settings


def ring_image() -> bytes:
    image = Image.new("RGBA", (200, 200), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 180, 180), fill="black")
    draw.rectangle((60, 60, 140, 140), fill="white")
    draw.rectangle((85, 85, 115, 115), fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_nested_negative_space_and_island_are_preserved():
    region, _ = trace_image(
        ring_image(),
        Settings(width_mm=200, height_mm=200, frame=False, margin_mm=0, crop_to_artwork=False),
    )
    assert region.covers(Point(30, 100))
    assert not region.covers(Point(70, 100))
    assert region.covers(Point(100, 100))
    assert not region.covers(Point(10, 10))


@pytest.mark.parametrize("fill", ["#D4A62A", "#ffffff", "#000000"])
def test_transparent_svg_extrudes_filled_shapes_regardless_of_color(fill):
    data = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<path fill="{fill}" fill-rule="evenodd" '
        'd="M10 10H90V90H10Z M30 30H70V70H30Z M45 45H55V55H45Z"/></svg>'
    ).encode()
    settings = Settings(
        width_mm=100, height_mm=100, frame=False, margin_mm=0, crop_to_artwork=False
    )
    project = build_project(data, settings)
    assert project.vector.covers(Point(20, 50))
    assert not project.vector.covers(Point(35, 50))
    assert project.vector.covers(Point(50, 50))
    assert not project.vector.covers(Point(5, 5))
    assert project.pieces[0].artwork.is_volume
    assert project.pieces[0].combined.body_count == 1


@pytest.mark.parametrize("background", ["#ffffff", "#000000"])
def test_opaque_svg_selects_artwork_against_its_background(background):
    data = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<rect width="100" height="100" fill="{background}"/>'
        '<circle cx="50" cy="50" r="20" fill="#D4A62A"/></svg>'
    ).encode()
    vector, _ = trace_image(data, Settings(frame=False, margin_mm=0))
    assert vector.covers(Point(90, 90))
    assert not vector.covers(Point(10, 10))


def test_svg_brightness_selection_remains_available():
    data = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        b'<circle cx="50" cy="50" r="20" fill="#D4A62A"/></svg>'
    )
    with pytest.raises(ValueError, match="No artwork"):
        trace_image(data, Settings(foreground="dark"))
    light, _ = trace_image(data, Settings(foreground="light", frame=False, margin_mm=0))
    assert light.covers(Point(90, 90))
    assert not light.covers(Point(10, 10))


def test_inversion_changes_foreground_and_transparency_composites_white():
    normal, _ = trace_image(ring_image(), Settings(frame=False, margin_mm=0, crop_to_artwork=False))
    inverted, _ = trace_image(
        ring_image(), Settings(frame=False, margin_mm=0, invert=True, crop_to_artwork=False)
    )
    assert normal.intersection(inverted).area < 1e-5
    assert inverted.covers(Point(3, 3))


@pytest.mark.parametrize("layout", ["tiles", "puzzle"])
def test_partitions_cover_rectangle_without_overlap(layout):
    settings = Settings(width_mm=450, height_mm=300, layout=layout, clearance_mm=0)
    tiles = partition(settings, 3, 2)
    union = unary_union([t.shape for t in tiles])
    assert union.symmetric_difference(box(0, 0, 450, 300)).area < 1e-6
    for a, b in combinations(tiles, 2):
        assert a.shape.intersection(b.shape).area < 1e-6


def test_puzzle_clearance_and_outer_dimensions():
    settings = Settings(
        width_mm=80, height_mm=40, layout="puzzle", clearance_mm=0.3, puzzle_style="regular"
    )
    left, right = partition(settings, 2, 1)
    assert left.shape.distance(right.shape) == pytest.approx(0.3, abs=0.002)
    assert unary_union([left.shape, right.shape]).bounds == pytest.approx((0, 0, 80, 40))
    assert left.shape.bounds[2] > 40
    assert left.shape.is_valid and right.shape.is_valid


def test_auto_layout_measures_tabs_and_loops():
    settings = Settings(width_mm=440, height_mm=220, layout="puzzle", hanging="loops")
    tiles, columns, rows = choose_layout(settings)
    assert columns * rows > 2  # Two plain cells fit; the protruding tab does not.
    for tile in tiles:
        x0, y0, x1, y1 = tile.shape.bounds
        assert x1 - x0 <= 230 and y1 - y0 <= 230


@pytest.mark.parametrize(
    "config",
    [
        {"width_mm": 250},
        {"width_mm": 230, "height_mm": 230, "hanging": "loops"},
        {"layout": "puzzle", "width_mm": 460, "columns": 2, "rows": 1},
    ],
)
def test_oversize_layouts_fail(config):
    with pytest.raises(ValueError, match="exceeds"):
        choose_layout(Settings(**config))


@pytest.mark.parametrize("hanging", ["none", "loops", "keyholes"])
def test_materials_are_closed_nonoverlapping_and_combined_volume_adds(hanging):
    project = build_project(ring_image(), Settings(hanging=hanging, base_mm=5))
    piece = project.pieces[0]
    assert piece.base.is_volume and piece.artwork.is_volume and piece.combined.is_volume
    assert piece.base.bounds[1, 2] == pytest.approx(5)
    assert piece.artwork.bounds[0, 2] == pytest.approx(5)
    assert piece.combined.volume == pytest.approx(
        piece.base.volume + piece.artwork.volume, rel=1e-6
    )
    assert piece.combined.body_count == 1
    if hanging == "keyholes":
        assert piece.base.volume < 180 * 180 * 5
        assert piece.base.volume > 180 * 180 * 5 - 2000
    if hanging == "loops":
        assert piece.combined.extents[1] == pytest.approx(189)


def test_export_contains_grouped_materials_and_valid_meshes(tmp_path):
    settings = Settings(width_mm=80, height_mm=40, layout="puzzle", columns=2, rows=1)
    data = sample_bytes()
    project = build_project(data, settings)
    output = tmp_path / "pack"
    manifest = export_project(project, output, data)
    assert json.loads((output / "manifest.json").read_text())["units"] == "mm"
    assert manifest["piece_count"] == 2
    for record in manifest["pieces"]:
        scene = trimesh.load_scene(output / record["files"]["3mf"])
        assert scene.units == "millimeter"
        assert len(scene.geometry) == 2
        assert all(mesh.is_volume for mesh in scene.geometry.values())
        for key in ("background", "artwork", "combined"):
            mesh = trimesh.load_mesh(output / record["files"][key])
            assert mesh.is_volume
        with ZipFile(output / record["files"]["3mf"]) as archive:
            root = ET.fromstring(archive.read("3D/3dmodel.model"))
            assert root.attrib["unit"] == "millimeter"
            ns = {"c": CORE}
            assert len(root.findall(".//c:component", ns)) == 2
            assert root.find("c:build/c:item", ns).attrib["objectid"] == "4"
            for obj in root.findall("c:resources/c:object", ns)[:2]:
                vertices = [
                    [float(v.attrib[c]) for c in "xyz"]
                    for v in obj.findall("c:mesh/c:vertices/c:vertex", ns)
                ]
                faces = [
                    [int(t.attrib[f"v{i}"]) for i in (1, 2, 3)]
                    for t in obj.findall("c:mesh/c:triangles/c:triangle", ns)
                ]
                assert trimesh.Trimesh(vertices=vertices, faces=faces).is_volume
    with ZipFile(output / "print-pack.zip") as archive:
        assert "PRINTING.md" in archive.namelist()
        assert "print-pack.zip" not in archive.namelist()
    with pytest.raises(FileExistsError):
        export_project(project, output, data)


@pytest.mark.parametrize(
    "data",
    [
        b"not an image",
        b"",
        b'<svg width="100" height="100"><image href="file:///etc/passwd"/></svg>',
        b'<svg width="100" height="100"><use href="https://example.invalid/a.svg"/></svg>',
        b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b'<svg width="100" height="100">&xxe;</svg>',
        b'<svg width="100" height="100"><style>'
        b'@import url("https://example.invalid/style.css");</style></svg>',
    ],
)
def test_invalid_or_external_input_fails(data):
    with pytest.raises(ValueError):
        load_image(data, Settings())


@pytest.mark.parametrize(
    "config",
    [
        {"width_mm": float("nan")},
        {"columns": 2},
        {"hanging": "keyholes", "base_mm": 2.4},
        {"background_color": '"/><script>'},
        {"width_mm": 30, "frame_width_mm": 20},
        {"unexpected": 1},
    ],
)
def test_invalid_settings_fail(config):
    with pytest.raises(ValidationError):
        Settings(**config)


def test_empty_threshold_has_actionable_error():
    data = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(data, format="PNG")
    with pytest.raises(ValueError, match="No artwork"):
        trace_image(data.getvalue(), Settings())


def test_puzzle_assembly_origins_recover_global_coordinates():
    project = build_project(
        sample_bytes(), Settings(width_mm=120, height_mm=120, layout="puzzle", columns=2, rows=2)
    )
    for piece in project.pieces:
        restored = piece.base.vertices + np.array(piece.origin)
        assert np.min(restored[:, :2], axis=0) == pytest.approx(
            piece.tile.shape.bounds[:2], abs=1e-5
        )
        assert np.max(restored[:, :2], axis=0) == pytest.approx(
            piece.tile.shape.bounds[2:], abs=1e-5
        )


@pytest.mark.parametrize("example", ["wall-puzzle", "wall-tiles"])
def test_large_materials_survive_importer_vertex_welding(tmp_path, example):
    settings = Settings.model_validate_json(
        (Path(__file__).parents[1] / "examples" / f"{example}.json").read_text()
    )
    data = sample_bytes()
    output = tmp_path / example
    manifest = export_project(build_project(data, settings), output, data)
    for piece in manifest["pieces"]:
        scene = trimesh.load_scene(output / piece["files"]["3mf"])
        assert all(mesh.is_volume for mesh in scene.geometry.values())
        combined = trimesh.load_mesh(output / piece["files"]["combined"])
        assert combined.is_volume and combined.body_count == 1


def test_rear_keyholes_stay_in_puzzle_cell_bodies():
    settings = Settings(
        width_mm=540,
        height_mm=540,
        layout="puzzle",
        hanging="keyholes",
        base_mm=5,
        split_mode="bed",
    )
    project = build_project(sample_bytes(), settings)
    assert len(project.pieces) > 1
    for piece in project.pieces:
        assert piece.base.is_volume
        assert piece.base.volume < piece.tile.shape.area * settings.base_mm


def test_padding_trims_empty_canvas_and_preserves_artwork_proportions():
    data = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        b'<rect x="10" y="30" width="80" height="40" fill="gold"/></svg>'
    )
    settings = Settings(width_mm=100, height_mm=100, margin_mm=10)
    cropped, _ = trace_image(data, settings)
    x0, y0, x1, y1 = cropped.bounds
    assert x0 == pytest.approx(14.01, abs=0.02)
    assert x1 == pytest.approx(85.99, abs=0.02)
    assert (x1 - x0) / (y1 - y0) == pytest.approx(2, abs=0.01)
    preserved, _ = trace_image(data, settings.model_copy(update={"crop_to_artwork": False}))
    assert preserved.area < cropped.area
    padded, _ = trace_image(data, settings.model_copy(update={"margin_mm": 20}))
    assert padded.bounds[0] == pytest.approx(24.01, abs=0.02)


@pytest.mark.parametrize("layout", ["plaque", "tiles", "puzzle"])
@pytest.mark.parametrize("profile", ["flat", "rounded"])
def test_rounded_designs_preserve_closed_materials_and_piece_alignment(tmp_path, layout, profile):
    settings = Settings(
        width_mm=120,
        height_mm=90,
        layout=layout,
        columns=1 if layout == "plaque" else 2,
        rows=1 if layout == "plaque" else 2,
        corner_radius_mm=12,
        frame_profile=profile,
        base_mm=3,
        relief_mm=1.2,
        frame_height_mm=2.4,
    )
    project = build_project(sample_bytes(), settings)
    output = tmp_path / "rounded"
    manifest = export_project(project, output, sample_bytes())
    for piece, record in zip(project.pieces, manifest["pieces"], strict=True):
        assert piece.combined.body_count == 1
        assert piece.base.bounds[1, 2] == pytest.approx(3)
        assert piece.artwork.bounds[0, 2] == pytest.approx(3)
        assert piece.combined.extents[2] == pytest.approx(5.4)
        assert piece.combined.volume == pytest.approx(
            piece.base.volume + piece.artwork.volume, rel=1e-6
        )
        scene = trimesh.load_scene(output / record["files"]["3mf"])
        assert len(scene.geometry) == 2
        assert all(mesh.is_volume for mesh in scene.geometry.values())
        assert trimesh.load_mesh(output / record["files"]["combined"]).is_volume
    assert not project.pieces[-1].tile.shape.covers(Point(0, 0))


@pytest.mark.parametrize("radius", [0, 2, 20])
def test_rounded_border_has_curved_height_sections_and_retains_its_dimensions(radius):
    from relief_studio.geometry import check_mesh
    from relief_studio.profiles import outline, rounded_border

    settings = Settings(corner_radius_mm=radius, frame_profile="rounded")
    border = rounded_border(settings)
    check_mesh(border)
    assert len(np.unique(border.vertices[:, 2])) > 10
    assert border.bounds[:, 2] == pytest.approx([settings.base_mm, 4])
    assert border.extents[:2] == pytest.approx([180, 180])
    flat_volume = (
        outline(settings).area - outline(settings, settings.frame_width_mm).area
    ) * settings.frame_height_mm
    assert 0.8 * flat_volume < border.volume < flat_volume


@pytest.mark.parametrize("hanging", ["none", "loops", "keyholes"])
def test_rounded_background_without_border_supports_optional_hanging(hanging):
    project = build_project(
        sample_bytes(),
        Settings(
            frame=False,
            corner_radius_mm=15,
            hanging=hanging,
            base_mm=5,
        ),
    )
    piece = project.pieces[0]
    assert piece.base.is_volume and piece.combined.body_count == 1
    assert piece.combined.extents[2] == pytest.approx(5.8)
    assert piece.tile.shape.area < 180 * 180


def test_corner_radius_must_fit_the_background():
    with pytest.raises(ValidationError, match="Corner radius"):
        Settings(width_mm=40, corner_radius_mm=25)
    with pytest.raises(ValueError, match="Layout disconnected"):
        choose_layout(
            Settings(
                width_mm=192,
                height_mm=192,
                corner_radius_mm=96,
                layout="tiles",
                columns=8,
                rows=8,
            )
        )
