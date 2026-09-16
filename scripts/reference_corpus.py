"""Capture version-one geometric invariants without depending on mesh triangulation order."""

import argparse
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw

from relief_studio.artwork import polygons
from relief_studio.exports import project_manifest
from relief_studio.geometry import build_project
from relief_studio.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/reference-v1.json"


def cases():
    base = {"detail": "draft"}
    for name, updates in [
        ("default", {}),
        ("no-border", {"frame": False}),
        ("flat-border", {"frame_width_mm": 8, "frame_height_mm": 3}),
        ("rounded-border", {"frame_profile": "rounded", "corner_radius_mm": 24}),
        ("beaded-border", {"frame_profile": "beaded", "width_mm": 90, "height_mm": 90}),
        ("loops", {"hanging": "loops", "corner_radius_mm": 40}),
        ("keyholes", {"hanging": "keyholes", "base_mm": 5}),
        ("tiles", {"layout": "tiles"}),
        ("large-tiles", {"layout": "tiles", "width_mm": 420, "height_mm": 320}),
        ("regular-puzzle", {"layout": "puzzle", "puzzle_style": "regular"}),
        ("random-puzzle", {"layout": "puzzle", "puzzle_seed": 17}),
        ("zero-clearance", {"layout": "puzzle", "clearance_mm": 0}),
        ("wide-clearance", {"layout": "puzzle", "clearance_mm": 1}),
        ("puzzle-loops", {"layout": "puzzle", "hanging": "loops", "corner_radius_mm": 30}),
        ("puzzle-keyholes", {"layout": "puzzle", "hanging": "keyholes", "base_mm": 5}),
        ("contour", {"shape": "contour"}),
        ("contour-bare", {"shape": "contour", "frame": False, "margin_mm": 0}),
        ("contour-rounded", {"shape": "contour", "frame_profile": "rounded"}),
        ("contour-beaded", {"shape": "contour", "frame_profile": "beaded"}),
        ("contour-loop", {"shape": "contour", "hanging": "loops"}),
        ("contour-keyhole", {"shape": "contour", "hanging": "keyholes", "base_mm": 5}),
        ("canvas-margins", {"crop_to_artwork": False}),
        ("inverted", {"invert": True}),
        ("too-wide", {"width_mm": 300}),
        ("invalid-width", {"width_mm": 1}),
        ("invalid-keyholes", {"hanging": "keyholes"}),
        ("invalid-contour-layout", {"shape": "contour", "layout": "tiles"}),
        ("invalid-grid", {"columns": 12, "rows": 12, "layout": "tiles"}),
    ]:
        yield name, "src/relief_studio/assets/alpine.svg", base | updates
    for name, source, updates in [
        ("gold-holes", "tests/fixtures/gold-cutout.svg", {}),
        ("empty-selection", "tests/fixtures/gold-cutout.svg", {"foreground": "light"}),
        ("raster-holes", "tests/fixtures/raster-rings.png", {}),
        ("raster-light", "tests/fixtures/raster-rings.png", {"foreground": "light"}),
        ("icon", "tests/fixtures/contour-icon.svg", {"shape": "contour"}),
    ]:
        yield name, source, base | updates


def capture():
    records = []
    for name, source, values in cases():
        record = {"name": name, "source": source, "settings": values}
        try:
            project = build_project((ROOT / source).read_bytes(), Settings(**values))
            record["manifest"] = project_manifest(project)
            record["artwork"] = {
                "area": project.vector.area,
                "bounds": list(project.vector.bounds),
                "regions": len(polygons(project.vector)),
                "holes": sum(len(p.interiors) for p in polygons(project.vector)),
            }
        except ValueError as error:
            record["error"] = str(error)
        records.append(record)
        print(name, "error" if "error" in record else "ok", flush=True)
    return {"reference_commit": "9d79cce", "cases": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=CORPUS)
    args = parser.parse_args()
    raster = ROOT / "tests/fixtures/raster-rings.png"
    if not raster.exists():
        image = Image.new("RGB", (240, 180), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((20, 10, 220, 170), fill="black")
        draw.ellipse((55, 40, 185, 140), fill="white")
        draw.ellipse((90, 65, 150, 115), fill="black")
        data = io.BytesIO()
        image.save(data, format="PNG")
        raster.write_bytes(data.getvalue())
    args.output.write_text(json.dumps(capture(), indent=2) + "\n")
