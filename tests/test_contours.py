"""Regress silhouette fabrication, outward expansion, mount fit, and export recovery.

The committed icon is synthetic. Optional user art is read only from external
paths and exercises exactly the same pipeline without embedding it in Git.
"""

import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pytest
import trimesh
from fastapi.testclient import TestClient
from pydantic import ValidationError
from shapely.geometry import Point, Polygon, box

from relief_studio.artwork import load_image, polygons
from relief_studio.exports import export_project, vector_svg
from relief_studio.geometry import build_project
from relief_studio.server import create_app
from relief_studio.settings import Settings

ICON = (Path(__file__).parent / "fixtures/contour-icon.svg").read_bytes()
ISLANDS = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    b'<circle cx="25" cy="50" r="20"/><circle cx="75" cy="50" r="20"/></svg>'
)


def config(**kwargs):
    return Settings(shape="contour", width_mm=120, height_mm=180, **kwargs)


@pytest.mark.parametrize("profile", ["none", "flat", "rounded", "beaded"])
@pytest.mark.parametrize("hanging", ["none", "loops", "keyholes"])
def test_contour_is_connected_with_preserved_image_holes_and_aligned_materials(profile, hanging):
    settings = config(
        frame=profile != "none",
        frame_profile="flat" if profile == "none" else profile,
        hanging=hanging,
        base_mm=5 if hanging == "keyholes" else 2.4,
    )
    project = build_project(ICON, settings)
    (piece,) = project.pieces
    footprint = piece.tile.shape
    assert footprint.area < box(*footprint.bounds).area * 0.7
    assert footprint.buffer(1e-6).covers(project.vector)
    holes = [Polygon(ring) for p in polygons(project.vector) for ring in p.interiors]
    assert holes and all(footprint.covers(hole) for hole in holes)
    assert sum(len(p.interiors) for p in polygons(footprint)) == (hanging == "loops")
    assert piece.combined.is_volume and piece.combined.body_count == 1
    assert piece.base.is_volume and piece.base.body_count == 1
    assert piece.artwork.is_volume
    assert piece.artwork.bounds[0, 2] == pytest.approx(settings.base_mm)
    assert piece.combined.volume == pytest.approx(
        piece.base.volume + piece.artwork.volume, rel=1e-5
    )
    assert np.all(piece.combined.extents[:2] < 230)
    if hanging == "keyholes":
        assert piece.base.volume < footprint.area * settings.base_mm
    if hanging == "loops":
        hole = Polygon(footprint.interiors[0])
        assert hole.centroid.x == pytest.approx(60, abs=0.1)
        assert hole.area == pytest.approx(Point(0, 0).buffer(2.5, quad_segs=24).area)


def test_widening_bezel_and_padding_expands_backing_without_resizing_image():
    plain = build_project(ICON, config(frame=False, margin_mm=0))
    padded = build_project(ICON, config(frame=False, margin_mm=5))
    framed = build_project(ICON, config(frame_width_mm=8, margin_mm=5))
    assert plain.vector.equals(padded.vector) and plain.vector.equals(framed.vector)
    assert padded.pieces[0].combined.extents[:2] == pytest.approx(
        plain.pieces[0].combined.extents[:2] + 10, abs=0.01
    )
    assert framed.pieces[0].combined.extents[:2] == pytest.approx(
        padded.pieces[0].combined.extents[:2] + 16, abs=0.01
    )
    assert framed.raised.difference(framed.vector).distance(framed.vector) == pytest.approx(
        5, abs=0.01
    )
    # Rectangle-only controls must not distort or move a contour image.
    retained = build_project(
        ICON, config(frame=False, margin_mm=0, crop_to_artwork=False, corner_radius_mm=90)
    )
    assert retained.vector.equals(plain.vector)


def test_disconnected_islands_fail_then_recover_with_padding():
    with pytest.raises(ValueError, match="disconnected islands"):
        build_project(ISLANDS, config(frame=False, margin_mm=0))
    recovered = build_project(ISLANDS, config(frame=False, margin_mm=9))
    assert recovered.pieces[0].combined.body_count == 1


def test_loop_and_bezel_are_included_in_bed_fit_and_recover():
    settings = Settings(shape="contour", width_mm=150, height_mm=210)
    build_project(ICON, settings)
    with pytest.raises(ValueError, match="including its bezel and loop"):
        build_project(ICON, settings.model_copy(update={"hanging": "loops"}))
    recovered = build_project(
        ICON, settings.model_copy(update={"height_mm": 200, "hanging": "loops"})
    )
    assert recovered.pieces[0].combined.extents[1] < 230
    with pytest.raises(ValueError, match="exceeds the usable build plate"):
        build_project(ICON, settings.model_copy(update={"frame_width_mm": 15}))


def test_narrow_rear_mount_fails_then_padding_supports_it():
    narrow = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 180">'
        b'<rect x="46" y="10" width="8" height="160"/></svg>'
    )
    with pytest.raises(ValueError, match="too narrow for rear keyholes"):
        build_project(narrow, config(frame=False, margin_mm=0, hanging="keyholes", base_mm=5))
    recovered = build_project(
        narrow, config(frame=False, margin_mm=5, hanging="keyholes", base_mm=5)
    )
    assert recovered.pieces[0].combined.body_count == 1


@pytest.mark.parametrize("layout", ["tiles", "puzzle"])
def test_contours_reject_splits_at_shared_settings_boundary(layout):
    with pytest.raises(ValidationError, match="single piece"):
        config(layout=layout)


@pytest.mark.parametrize("profile", ["rounded", "beaded"])
def test_export_keeps_actual_extents_and_material_alignment(tmp_path, profile):
    project = build_project(ICON, config(frame_profile=profile, hanging="loops"))
    folder = tmp_path / "contour"
    manifest = export_project(project, folder, ICON)
    assert manifest["settings"]["shape"] == "contour" and manifest["piece_count"] == 1
    scene = trimesh.load_scene(folder / "plates/plate-01.3mf")
    assert len(scene.geometry) == 2 and all(m.is_volume for m in scene.geometry.values())
    assert scene.bounds[1] - scene.bounds[0] == pytest.approx(
        project.pieces[0].combined.extents, abs=1e-4
    )
    combined = trimesh.load_mesh(folder / "pieces/r01-c01/combined.stl")
    assert combined.is_volume and combined.body_count == 1
    svg = ET.fromstring(vector_svg(project, assembly=True))
    assert list(map(float, svg.attrib["viewBox"].split()))[2:] == pytest.approx(
        combined.extents[:2], abs=1e-4
    )
    assert "finished piece including hanging" in (folder / "PRINTING.md").read_text()


def test_api_rejects_disconnected_contour_then_exports_recovered_project(tmp_path):
    client = TestClient(create_app(tmp_path / "packs"))
    files = {"image": ("islands.svg", ISLANDS, "image/svg+xml")}
    settings = config(frame=False, margin_mm=0).model_dump()
    rejected = client.post("/api/preview", files=files, data={"settings": json.dumps(settings)})
    assert rejected.status_code == 422 and "disconnected islands" in rejected.json()["detail"]
    settings["margin_mm"] = 9
    restored = client.post("/api/preview", files=files, data={"settings": json.dumps(settings)})
    assert restored.status_code == 200, restored.text
    exported = client.post(f"/api/export/{restored.json()['id']}")
    assert exported.status_code == 200
    assert client.get(exported.json()["model_url"]).status_code == 200


@pytest.mark.parametrize("shape", ["rectangle", "contour"])
@pytest.mark.parametrize("width,height", [(0.5, 0.4), (0.5, 12), (12, 0.4), (12, 12)])
def test_bead_extremes_stay_attached_and_within_the_border(shape, width, height):
    project = build_project(
        ICON,
        Settings(
            shape=shape,
            width_mm=100,
            height_mm=150,
            frame_profile="beaded",
            frame_width_mm=width,
            frame_height_mm=height,
            detail="fine",
        ),
    )
    piece = project.pieces[0]
    assert piece.combined.body_count == 1 and piece.combined.is_volume
    assert piece.combined.volume == pytest.approx(
        piece.base.volume + piece.artwork.volume, rel=1e-5
    )
    assert piece.artwork.bounds[1, 2] == pytest.approx(2.4 + max(height, 0.8))


PRIVATE_SOURCES = [
    Path(p) for p in os.environ.get("RELIEF_TEST_ARTWORK", "").split(os.pathsep) if p
]


@pytest.mark.parametrize("source", PRIVATE_SOURCES or [None], ids=lambda _: "private-svg")
@pytest.mark.parametrize("profile", ["none", "flat", "rounded", "beaded"])
@pytest.mark.parametrize("detail", ["balanced", "fine"])
def test_optional_private_contour(source, profile, detail):
    if source is None:
        pytest.skip("Set RELIEF_TEST_ARTWORK to exercise private contour images.")
    project = build_project(
        source.read_bytes(),
        Settings(
            shape="contour",
            width_mm=130,
            height_mm=200,
            detail=detail,
            frame=profile != "none",
            frame_profile="flat" if profile == "none" else profile,
            hanging="loops",
            frame_width_mm=6,
            frame_height_mm=3,
        ),
    )
    assert project.vector.area > 0
    assert project.pieces[0].combined.is_volume and project.pieces[0].combined.body_count == 1
    # A repaired outline must not silently flood the image's negative space.
    # Use the input mask as the independent area bound so solid icons also work.
    mask = np.asarray(load_image(source.read_bytes(), project.settings)) <= 128
    y, x = np.nonzero(mask)
    scale = min(130 / np.ptp(x), 200 / np.ptp(y))
    assert project.vector.area <= mask.sum() * scale**2 * 1.05
