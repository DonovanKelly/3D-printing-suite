"""Reopen contour split packs independently, including multiple fragments per cell.

STL/3MF readers check topology and material alignment while SVG coordinates check
the complete assembly viewport and label transforms for expanded contour bounds.
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


@pytest.mark.parametrize("layout,columns,rows", [
    ("tiles", 1, 2), ("tiles", 3, 3), ("puzzle", 2, 2),
])
def test_contour_fragment_pack(layout, columns, rows, tmp_path):
    pack = tmp_path / "split.zip"
    request = {
        "input": str(ROOT / "tests/fixtures/contour-fork.svg"),
        "settings": {
            "shape": "contour", "layout": layout, "columns": columns, "rows": rows,
            "border_material": "custom", "frame_profile": "rounded", "detail": "draft",
        },
        "output": str(pack),
    }
    run = subprocess.run(
        [str(ROOT / "target/release/relief-native"), "--batch"],
        input=json.dumps(request) + "\n", capture_output=True, text=True, check=True,
    )
    result = json.loads(run.stdout)
    assert "error" not in result, result
    with ZipFile(pack) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        pieces = manifest["pieces"]
        names = {p["id"] for p in pieces}
        assert len(names) == len(pieces)
        if columns == 1:
            assert names == {"r01-c01-p01", "r01-c01-p02", "r02-c01"}
        for piece in pieces:
            meshes = {
                name: trimesh.load_mesh(io.BytesIO(archive.read(path)), file_type="stl")
                for name, path in piece["files"].items() if name != "3mf"
            }
            assert all(m.is_volume and m.is_winding_consistent for m in meshes.values())
            assert meshes["background"].body_count == meshes["combined"].body_count == 1
            assert meshes["combined"].extents == pytest.approx(piece["extents_mm"], abs=1e-4)
            assert meshes["combined"].volume == pytest.approx(
                sum(m.volume for n, m in meshes.items() if n != "combined"), rel=1e-5,
            )
            for name in ["artwork", "border"]:
                if name in meshes:
                    assert meshes[name].bounds[0, 2] == pytest.approx(
                        manifest["settings"]["base_mm"],
                    )
        for name in [n for n in archive.namelist() if n.endswith(".3mf")]:
            scene = trimesh.load_scene(io.BytesIO(archive.read(name)), file_type="3mf")
            assert all(m.is_volume for m in scene.geometry.values())
            assert scene.bounds[0, :2].min() >= -1e-5
            assert scene.bounds[1, :2].max() <= 256 + 1e-5
        origins = np.array([p["assembly_origin_mm"][:2] for p in pieces])
        extents = np.array([p["extents_mm"][:2] for p in pieces])
        low = origins.min(axis=0)
        size = (origins + extents).max(axis=0) - low
        ns = {"s": "http://www.w3.org/2000/svg"}
        for filename in ["assembly.svg", "artwork.svg"]:
            svg = ET.fromstring(archive.read(filename))
            assert [float(v) for v in svg.attrib["viewBox"].split()][2:] == pytest.approx(size)
        svg = ET.fromstring(archive.read("assembly.svg"))
        labels = {node.text: node for node in svg.findall("s:text", ns)}
        assert labels.keys() == names
        for piece in pieces:
            label = labels[piece["id"]]
            center = (
                np.array(piece["assembly_origin_mm"][:2])
                + np.array(piece["extents_mm"][:2]) / 2 - low
            )
            assert float(label.attrib["x"]) == pytest.approx(center[0])
            assert float(label.attrib["y"]) == pytest.approx(size[1] - center[1])
        assert b"suitable adhesive" in archive.read("PRINTING.md")
