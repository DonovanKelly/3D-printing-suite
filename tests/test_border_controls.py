"""Check border adjustments preserve the finished size, padding, and material alignment."""

import pytest

from relief_studio.cli import sample_bytes
from relief_studio.geometry import build_project
from relief_studio.settings import Settings


@pytest.mark.parametrize("profile", ["flat", "rounded"])
@pytest.mark.parametrize("width", [0.5, 8, 30])
def test_border_width_does_not_resize_the_backing_or_overlap_the_image(profile, width):
    settings = Settings(frame_width_mm=width, frame_profile=profile, margin_mm=5)
    project = build_project(sample_bytes(), settings)
    piece = project.pieces[0]
    assert piece.combined.extents[:2] == pytest.approx([180, 180])
    assert piece.artwork.bounds[:, 2] == pytest.approx([2.4, 4])
    assert piece.combined.body_count == 1
    assert piece.combined.volume == pytest.approx(
        piece.base.volume + piece.artwork.volume, rel=1e-6
    )
    x0, y0, x1, y1 = project.vector.bounds
    assert min(x0, y0, 180 - x1, 180 - y1) >= width + 5 - 1e-5
