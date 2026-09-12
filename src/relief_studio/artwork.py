"""Normalize local images to bounded binary contours, preserving nested holes.

SVG is rasterized before tracing so filled paths, transforms, and strokes share
the same conversion controls as photos. Resource fetching is denied at the
renderer boundary; uploaded SVG never gets embedded directly in the workbench.
"""

import io
import re
import warnings

import cv2
import numpy as np
from cairosvg.surface import PNGSurface
from defusedxml import ElementTree
from PIL import Image, ImageOps
from shapely import Geometry, affinity, make_valid
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .settings import Settings

MAX_INPUT_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 24_000_000


def polygons(geometry: Geometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [p for child in getattr(geometry, "geoms", []) for p in polygons(child)]


def _deny_resource(url: str, resource_type: str) -> bytes:
    raise ValueError("SVG must be self-contained; linked resources are not supported.")


def load_image(data: bytes, settings: Settings) -> Image.Image:
    if not data or len(data) > MAX_INPUT_BYTES:
        raise ValueError("Choose an image or SVG smaller than 12 MiB.")
    is_svg = b"<svg" in data[:2048].lower()
    try:
        if is_svg:
            root = ElementTree.fromstring(data)
            if root.tag.rsplit("}", 1)[-1] != "svg":
                raise ValueError("The document must have an SVG root.")
            if sum(1 for _ in root.iter()) > 10_000:
                raise ValueError("SVG is too complex; flatten or simplify it first.")
            if re.search(rb"@import", data, re.IGNORECASE):
                raise ValueError("SVG stylesheet imports are not supported.")
            for element in root.iter():
                if element.tag.rsplit("}", 1)[-1] in {"script", "foreignObject", "image"}:
                    raise ValueError(
                        "SVG scripts, embedded images, and foreign objects are unsupported."
                    )
                for key, value in element.attrib.items():
                    if key.rsplit("}", 1)[-1] == "href" and not value.startswith("#"):
                        raise ValueError("SVG links must reference a shape inside the same file.")
            # Force a bounded viewport while retaining the document's aspect ratio.
            viewbox = re.split(r"[\s,]+", root.attrib.get("viewBox", "").strip())
            if len(viewbox) == 4:
                width, height = float(viewbox[2]), float(viewbox[3])
            else:

                def dimension(name: str) -> float:
                    match = re.fullmatch(r"([\d.]+)(?:px|mm|cm|in|pt|pc)?", root.get(name, ""))
                    if not match:
                        raise ValueError("SVG needs a viewBox or explicit width and height.")
                    return float(match[1])

                width, height = dimension("width"), dimension("height")
            if not np.isfinite([width, height]).all() or min(width, height) <= 0:
                raise ValueError("SVG dimensions must be finite and positive.")
            if not 1 / 50 <= width / height <= 50:
                raise ValueError("Image aspect ratio must be between 1:50 and 50:1.")
            scale = settings.trace_resolution / max(width, height)
            data = PNGSurface.convert(
                bytestring=data,
                output_width=max(2, round(width * scale)),
                output_height=max(2, round(height * scale)),
                url_fetcher=_deny_resource,
            )
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("Image exceeds the 24 megapixel limit; resize it first.")
                if not 1 / 50 <= source.width / source.height <= 50:
                    raise ValueError("Image aspect ratio must be between 1:50 and 50:1.")
                rgba = ImageOps.exif_transpose(source).convert("RGBA")
        rgba.thumbnail((settings.trace_resolution, settings.trace_resolution))
        background = Image.new("RGBA", rgba.size, "white")
        return Image.alpha_composite(background, rgba).convert("L")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            "Could not read this image. Use a PNG, JPEG, WebP, or self-contained SVG."
        ) from exc


def trace_image(data: bytes, settings: Settings) -> tuple[Geometry, list[str]]:
    gray = np.asarray(load_image(data, settings))
    mask = gray <= settings.threshold
    if settings.invert:
        mask = ~mask
    contours, hierarchy = cv2.findContours(
        mask.astype(np.uint8) * 255,
        cv2.RETR_TREE,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None:
        raise ValueError("No artwork remains. Adjust the threshold or invert the image.")
    if len(contours) > 5000:
        raise ValueError(
            "Too many small regions. Simplify the image or use a lower detail setting."
        )
    hierarchy = hierarchy[0]
    regions = []
    for index, contour in enumerate(contours):
        depth, parent = 0, hierarchy[index][3]
        while parent != -1:
            depth, parent = depth + 1, hierarchy[parent][3]
        if depth % 2 or len(contour) < 3:
            continue
        holes = []
        child = hierarchy[index][2]
        while child != -1:
            if len(contours[child]) >= 3:
                holes.append(contours[child][:, 0, :])
            child = hierarchy[child][0]
        regions.extend(polygons(make_valid(Polygon(contour[:, 0, :], holes))))
    if not regions:
        raise ValueError("Artwork is too thin to trace. Increase its resolution or line weight.")
    region = unary_union(regions)
    inset = settings.margin_mm + (settings.frame_width_mm if settings.frame else 0)
    height, width = gray.shape
    scale = min((settings.width_mm - 2 * inset) / width, (settings.height_mm - 2 * inset) / height)
    # Image y points down; model y points toward the top of the finished plaque.
    region = affinity.affine_transform(
        region,
        [
            scale,
            0,
            0,
            -scale,
            (settings.width_mm - width * scale) / 2 + scale / 2,
            (settings.height_mm + height * scale) / 2 - scale / 2,
        ],
    )
    simplified = make_valid(region.simplify(settings.simplify_mm, preserve_topology=True))
    parts = polygons(simplified)
    kept = [p for p in parts if p.area >= settings.min_area_mm2]
    if not kept:
        raise ValueError("All artwork was smaller than the minimum area. Reduce detail filtering.")
    notes = []
    if len(kept) != len(parts):
        notes.append(
            f"Removed {len(parts) - len(kept)} tiny artwork regions below the area filter."
        )
    result = unary_union(kept)
    narrow = result.difference(result.buffer(-0.2).buffer(0.2))
    if narrow.area > max(result.area * 0.03, 1):
        notes.append(
            "Some fine features may be narrower than a 0.4 mm nozzle; inspect the sliced preview."
        )
    return result, notes
