"""Exercise interacting fabrication settings, plus optional private SVG regressions."""

import os
from itertools import product
from pathlib import Path

import numpy as np
import pytest

from relief_studio.geometry import build_project
from relief_studio.settings import Settings

GOLD = (Path(__file__).parent / "fixtures/gold-cutout.svg").read_bytes()
CONFIGS = []
for i, (layout, border, hanging, size) in enumerate(
    product(
        ["plaque", "tiles", "puzzle"],
        ["none", "flat", "rounded"],
        ["none", "loops", "keyholes"],
        [(120, 160), (180, 100)],
    )
):
    CONFIGS.append(
        dict(
            layout=layout,
            frame=border != "none",
            frame_profile="flat" if border == "none" else border,
            hanging=hanging,
            width_mm=size[0],
            height_mm=size[1],
            columns=0 if layout == "plaque" else 2,
            rows=0 if layout == "plaque" else 2,
            base_mm=5 if hanging == "keyholes" else [1.2, 2.4, 6][i % 3],
            relief_mm=[0.4, 1.2, 8][i % 3],
            frame_width_mm=[0.5, 4, 12][i % 3],
            frame_height_mm=[0.4, 1.6, 6][i % 3],
            corner_radius_mm=[0, 10, 40][i % 3],
            margin_mm=[0, 3, 12][i % 3],
            puzzle_seed=i,
            detail="draft",
        )
    )


@pytest.mark.parametrize(
    "config",
    CONFIGS,
    ids=[
        f"{c['layout']}-{c['frame_profile'] if c['frame'] else 'none'}"
        f"-{c['hanging']}-{c['width_mm']}"
        for c in CONFIGS
    ],
)
def test_fabrication_combinations_have_connected_closed_aligned_solids(config):
    project = build_project(GOLD, Settings(**config))
    assert len(project.pieces) == (1 if config["layout"] == "plaque" else 4)
    for piece in project.pieces:
        assert piece.combined.is_volume and piece.combined.body_count == 1
        assert piece.base.bounds[:, 2] == pytest.approx([0, config["base_mm"]])
        assert np.all(piece.combined.extents[:2] <= 230.00001)
        if piece.artwork is not None:
            assert piece.artwork.is_volume
            assert piece.artwork.bounds[0, 2] == pytest.approx(config["base_mm"])
            assert piece.combined.volume == pytest.approx(
                piece.base.volume + piece.artwork.volume, rel=1e-5
            )


PRIVATE_SOURCES = [
    Path(p) for p in os.environ.get("RELIEF_TEST_ARTWORK", "").split(os.pathsep) if p
]


@pytest.mark.parametrize("source", PRIVATE_SOURCES or [None], ids=lambda _: "private-svg")
@pytest.mark.parametrize(
    "config",
    [
        {},
        {"frame": False},
        {"frame_width_mm": 30},
        {"frame_profile": "rounded", "hanging": "loops", "corner_radius_mm": 90},
        {"layout": "tiles"},
        {"layout": "puzzle"},
        {"detail": "fine"},
        {"invert": True},
    ],
)
def test_optional_private_artwork(source, config):
    if source is None:
        pytest.skip("Set RELIEF_TEST_ARTWORK to exercise private source files locally.")
    project = build_project(source.read_bytes(), Settings(**config))
    assert project.vector.area > 0
    assert all(p.combined.is_volume and p.combined.body_count == 1 for p in project.pieces)
