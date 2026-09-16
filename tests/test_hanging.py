"""Keep single hanging loops attached to the actual backing, including rounded panels."""

import pytest
from shapely.geometry import Polygon

from relief_studio.cli import sample_bytes
from relief_studio.geometry import build_project
from relief_studio.settings import Settings


@pytest.mark.parametrize("radius", [0, 45, 90])
@pytest.mark.parametrize("profile", ["flat", "rounded"])
def test_one_centered_loop_has_an_open_hole_and_connected_backing(radius, profile):
    project = build_project(
        sample_bytes(),
        Settings(hanging="loops", corner_radius_mm=radius, frame_profile=profile),
    )
    piece = project.pieces[0]
    assert len(piece.tile.shape.interiors) == 1
    hole = Polygon(piece.tile.shape.interiors[0])
    assert hole.centroid.x == pytest.approx(90)
    assert hole.centroid.y == pytest.approx(183)
    assert hole.bounds == pytest.approx((87.5, 180.5, 92.5, 185.5))
    assert piece.combined.body_count == 1
    assert piece.base.is_volume and piece.combined.is_volume
    assert piece.combined.extents[1] == pytest.approx(189)


@pytest.mark.parametrize("layout", ["tiles", "puzzle"])
def test_rounded_top_panels_each_have_one_supported_loop(layout):
    project = build_project(
        sample_bytes(),
        Settings(layout=layout, columns=2, rows=2, hanging="loops", corner_radius_mm=90),
    )
    for piece in project.pieces:
        assert len(piece.tile.shape.interiors) == (1 if piece.tile.row == 0 else 0)
        assert piece.combined.body_count == 1
        assert piece.base.is_volume and piece.combined.is_volume
        if piece.tile.row == 0:
            hole = Polygon(piece.tile.shape.interiors[0])
            assert hole.centroid.x == pytest.approx(45 + 90 * piece.tile.column)
            assert hole.bounds[2] - hole.bounds[0] == pytest.approx(5)
            assert hole.bounds[3] - hole.bounds[1] == pytest.approx(5)
