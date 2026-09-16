"""Cover SVG color/opacity/contrast and manual selection boundaries before extrusion."""

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from shapely.geometry import Point

from relief_studio.artwork import ImageSelectionError, load_image, trace_image
from relief_studio.settings import Settings

GOLD = (Path(__file__).parent / "fixtures/gold-cutout.svg").read_bytes()


@pytest.mark.parametrize("color", ["#000000", "#ffffff", "#958714", "#fefefe", "#808080"])
@pytest.mark.parametrize("opacity", [1, 0.2, 0.01])
@pytest.mark.parametrize("threshold", [1, 128, 254])
def test_auto_svg_preserves_shapes_holes_and_islands_for_all_colors(color, opacity, threshold):
    svg = GOLD.replace(b"#958714", color.encode()).replace(
        b"<path ", f'<path opacity="{opacity}" '.encode()
    )
    settings = Settings(
        threshold=threshold,
        detail="draft",
        crop_to_artwork=False,
        frame=False,
        margin_mm=0,
        width_mm=100,
        height_mm=140,
    )
    region, _ = trace_image(svg, settings)
    assert region.covers(Point(12, 70))
    assert not region.covers(Point(30, 70))
    assert region.covers(Point(50, 70))


@pytest.mark.parametrize(
    "colors", [("#fefefe", "#ffffff"), ("#141414", "#121212"), ("#958714", "#978916")]
)
@pytest.mark.parametrize("threshold", [1, 128, 254])
def test_auto_opaque_svg_normalizes_low_contrast(colors, threshold):
    fill, background = colors
    svg = GOLD.replace(b"#958714", fill.encode()).replace(
        b"<path ", f'<rect width="100" height="140" fill="{background}"/><path '.encode()
    )
    gray = np.asarray(load_image(svg, Settings(detail="draft")))
    assert gray.min() == 0 and gray.max() == 255
    region, _ = trace_image(
        svg,
        Settings(
            threshold=threshold,
            detail="draft",
            width_mm=100,
            height_mm=140,
            crop_to_artwork=False,
            frame=False,
            margin_mm=0,
        ),
    )
    assert region.covers(Point(12, 70))
    assert not region.covers(Point(30, 70))
    assert region.covers(Point(50, 70))


@pytest.mark.parametrize("foreground", ["dark", "light"])
@pytest.mark.parametrize("threshold", [1, 64, 125, 126, 127, 128, 254])
@pytest.mark.parametrize("invert", [False, True])
def test_manual_threshold_boundary_is_explicit_and_recoverable(foreground, threshold, invert):
    settings = Settings(foreground=foreground, threshold=threshold, invert=invert, detail="draft")
    empty = not invert and (threshold < 126 if foreground == "dark" else threshold >= 126)
    if empty:
        with pytest.raises(ImageSelectionError, match="Reset image selection"):
            trace_image(GOLD, settings)
    else:
        region, _ = trace_image(GOLD, settings)
        assert not region.is_empty
    recovered, _ = trace_image(GOLD, Settings(detail="draft"))
    assert not recovered.is_empty


@pytest.mark.parametrize("detail", ["draft", "balanced", "fine"])
@pytest.mark.parametrize("invert", [False, True])
def test_auto_selection_remains_nonempty_at_every_detail(detail, invert):
    region, _ = trace_image(GOLD, Settings(detail=detail, invert=invert))
    assert region.is_valid and region.area > 0


def test_truly_blank_svg_stays_an_explicit_error():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"/>'
    with pytest.raises(ImageSelectionError, match="visible shapes"):
        trace_image(svg, Settings())


def test_touching_pixel_contours_keep_holes_instead_of_flooding_the_outline():
    # An original synthetic ring with pixel contacts reproduces the same
    # shell/hole repair failure as a detailed private SVG at Balanced detail.
    mask = np.zeros((32, 32), dtype=np.uint8)
    mask[1:31, 1:31] = 255
    mask[2:30, 2:30] = 0
    rng = np.random.default_rng(0)
    for _ in range(60):
        x, y = rng.integers(2, 30, 2)
        mask[y : y + 2, x : x + 2] = 255
    data = io.BytesIO()
    Image.fromarray(255 - mask).save(data, format="PNG")
    region, _ = trace_image(
        data.getvalue(),
        Settings(
            shape="contour", width_mm=90, height_mm=90, min_area_mm2=0, frame=False, margin_mm=0
        ),
    )
    scale = 90 / 29
    assert region.area < np.count_nonzero(mask) * scale**2
    assert region.area > 0
