"""Regress the default one-piece bug and verify reproducible, complementary random seams."""

from itertools import combinations

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from relief_studio.cli import sample_bytes
from relief_studio.geometry import build_project
from relief_studio.layout import choose_layout, partition
from relief_studio.settings import Settings


@pytest.mark.parametrize("layout", ["tiles", "puzzle"])
@pytest.mark.parametrize("split_mode", ["size", "bed"])
def test_sample_defaults_really_split_even_when_whole_image_fits_bed(layout, split_mode):
    project = build_project(sample_bytes(), Settings(layout=layout, split_mode=split_mode))
    assert len(project.pieces) >= 2
    for piece in project.pieces:
        assert piece.combined.is_volume and piece.combined.body_count == 1
        assert piece.combined.extents[:2].max() <= (90 if split_mode == "size" else 230) + 1e-4


@pytest.mark.parametrize("seed", [0, 1, 17, 42, 123456, 2147483647])
def test_random_seams_cover_artwork_and_remain_complementary(seed):
    settings = Settings(layout="puzzle", puzzle_seed=seed, clearance_mm=0)
    tiles = partition(settings, 4, 3)
    assert len(tiles) == 12
    assert (
        unary_union([p.shape for p in tiles]).symmetric_difference(box(0, 0, 180, 180)).area < 1e-6
    )
    for a, b in combinations(tiles, 2):
        assert a.shape.intersection(b.shape).area < 1e-6
    spaced = partition(settings.model_copy(update={"clearance_mm": 0.3}), 4, 3)
    for a, b in combinations(spaced, 2):
        assert a.shape.distance(b.shape) >= 0.298


def test_seed_changes_the_cut_and_reproduces_it_exactly():
    a = partition(Settings(layout="puzzle", puzzle_seed=1), 3, 3)
    same = partition(Settings(layout="puzzle", puzzle_seed=1), 3, 3)
    b = partition(Settings(layout="puzzle", puzzle_seed=2), 3, 3)
    assert [p.shape.wkb for p in a] == [p.shape.wkb for p in same]
    assert sum(x.shape.symmetric_difference(y.shape).area for x, y in zip(a, b, strict=True)) > 100


def test_smaller_maximum_size_produces_more_pieces_and_measures_tabs():
    large, _, _ = choose_layout(Settings(layout="puzzle", piece_size_mm=90))
    small, _, _ = choose_layout(Settings(layout="puzzle", piece_size_mm=50))
    assert len(small) > len(large)
    for p in small:
        x0, y0, x1, y1 = p.shape.bounds
        assert max(x1 - x0, y1 - y0) <= 50 + 1e-6


def test_impossible_split_is_actionable_instead_of_returning_a_plaque():
    with pytest.raises(ValueError, match="No split fits"):
        choose_layout(Settings(layout="puzzle", width_mm=30, height_mm=30))
    with pytest.raises(ValueError, match="at least two"):
        Settings(layout="tiles", columns=1, rows=1)
