"""Check that each plate exports separate printable objects with grouped color parts."""

from itertools import combinations
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pytest
import trimesh
from shapely.geometry import box

from relief_studio.cli import sample_bytes
from relief_studio.exports import CORE, export_project
from relief_studio.geometry import build_project
from relief_studio.packing import plan_plates
from relief_studio.settings import Settings


@pytest.mark.parametrize(
    "config",
    [
        {"layout": "tiles"},
        {"layout": "puzzle"},
        {"layout": "puzzle", "piece_size_mm": 60},
        {"layout": "puzzle", "width_mm": 420, "height_mm": 280, "piece_size_mm": 100},
        {"layout": "puzzle", "puzzle_seed": 17, "corner_radius_mm": 12, "frame_profile": "rounded"},
    ],
)
def test_plate_export_keeps_every_piece_separate_and_every_material_aligned(tmp_path, config):
    project = build_project(sample_bytes(), Settings(**config))
    plates = plan_plates(project)
    all_indices = [p.piece_index for plate in plates for p in plate]
    assert sorted(all_indices) == list(range(len(project.pieces)))
    assert len(set(all_indices)) == len(all_indices)
    output = tmp_path / "pack"
    manifest = export_project(project, output, sample_bytes())
    assert manifest["plate_count"] == len(plates)
    for plate, record in zip(plates, manifest["plates"], strict=True):
        rectangles = []
        for placed in plate:
            piece = project.pieces[placed.piece_index]
            w, h = piece.combined.extents[:2]
            rectangles.append(box(placed.x, placed.y, placed.x + w, placed.y + h))
            assert placed.x >= 0 and placed.y >= 0
            assert placed.x + w <= project.settings.bed_width_mm + 1e-5
            assert placed.y + h <= project.settings.bed_height_mm + 1e-5
        for a, b in combinations(rectangles, 2):
            assert a.distance(b) >= 3 - 1e-5
        path = output / record["file"]
        with ZipFile(path) as z:
            root = ET.fromstring(z.read("3D/3dmodel.model"))
            ns = {"c": CORE}
            items = root.findall("c:build/c:item", ns)
            assert len(items) == len(plate)
            objects = {o.attrib["id"]: o for o in root.findall("c:resources/c:object", ns)}
            assert len({item.attrib["objectid"] for item in items}) == len(plate)
            for item, placed in zip(items, plate, strict=True):
                obj = objects[item.attrib["objectid"]]
                assert obj.attrib["name"] == project.pieces[placed.piece_index].tile.name
                components = obj.findall("c:components/c:component", ns)
                expected = 2 if project.pieces[placed.piece_index].artwork is not None else 1
                assert len(components) == expected
                assert item.attrib["printable"] == "1"
                assert list(map(float, item.attrib["transform"].split()))[-3:] == pytest.approx(
                    [placed.x, placed.y, 0]
                )
        scene = trimesh.load_scene(path)
        assert scene.units == "millimeter"
        assert all(m.is_volume for m in scene.geometry.values())
        scene_bounds = []
        for node in scene.graph.nodes_geometry:
            transform, name = scene.graph[node]
            mesh = scene.geometry[name].copy()
            mesh.apply_transform(transform)
            scene_bounds.append(mesh.bounds)
        assert np.min(scene_bounds, axis=(0, 1))[:2].min() >= -1e-5
        assert np.max(scene_bounds, axis=(0, 1))[:2] == pytest.approx(
            np.max([b.bounds[2:] for b in rectangles], axis=0), abs=1e-5
        )


def test_default_puzzle_fits_one_plate_with_nine_build_objects(tmp_path):
    project = build_project(sample_bytes(), Settings(layout="puzzle"))
    assert len(project.pieces) == 9
    assert len(plan_plates(project)) == 1
