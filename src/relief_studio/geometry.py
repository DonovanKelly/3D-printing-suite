"""Extrude partitioned artwork into aligned material solids and validated pieces.

Material volumes meet at z=base thickness without overlap. Optional keyholes
have a wide internal head channel and a narrow opening at the back, retaining
a front skin and a lip for the screw head. They are experimental print features.
"""

from dataclasses import dataclass

import numpy as np
import trimesh
from shapely import Geometry
from shapely.geometry import GeometryCollection, Point, box
from shapely.ops import unary_union

from .artwork import trace_image
from .contours import contour_layout, decorated_border
from .layout import Tile, choose_layout
from .profiles import outline, rounded_border
from .settings import Settings
from .solids import check_mesh, clean_boolean, extrude


@dataclass
class Piece:
    tile: Tile
    base: trimesh.Trimesh
    artwork: trimesh.Trimesh | None
    combined: trimesh.Trimesh
    origin: list[float]


@dataclass
class Project:
    settings: Settings
    vector: Geometry
    raised: Geometry
    pieces: list[Piece]
    columns: int
    rows: int
    warnings: list[str]


def keyhole_cutters(
    tile: Tile, settings: Settings, columns: int, rows: int
) -> list[trimesh.Trimesh]:
    # Anchor to the nominal cell, not its tab-expanded bounds; otherwise a top
    # tab could move the keyholes above the solid body of a puzzle piece.
    cell_width = settings.width_mm / columns
    left, right = tile.column * cell_width, (tile.column + 1) * cell_width
    top = settings.height_mm * (1 - tile.row / rows)
    cutters = []
    bottom = top - settings.height_mm / rows
    positions = (left + (right - left) * 0.3, left + (right - left) * 0.7)
    if settings.shape == "contour":
        left, bottom, right, top = tile.shape.bounds
        positions = ((left + right) / 2,)
    for x in positions:
        # Random tab sockets may occupy the preferred mounting position. Search
        # down the cell for a retaining lip fully supported by the actual piece.
        for y in np.arange(top - 16, bottom + 6, -2):
            head = Point(x, y).buffer(4, quad_segs=24)
            shaft = box(x - 2, y, x + 2, y + 7).union(Point(x, y + 7).buffer(2, quad_segs=24))
            opening = head.union(shaft)
            channel = head.union(Point(x, y + 7).buffer(4, quad_segs=24)).convex_hull
            if tile.shape.buffer(-3).covers(channel):
                break
        else:
            raise ValueError(
                "Backing is too narrow for rear keyholes. Increase the size or padding, "
                "or choose a top loop or no hanging."
            )
        # Open from the bed-facing back; leave a 1.2 mm retaining lip over the head channel.
        cutters.extend([extrude(opening, 3.2, -0.1), extrude(channel, 1.9, 1.2)])
    return cutters


def build_project(data: bytes, settings: Settings) -> Project:
    vector, notes = trace_image(data, settings)
    if settings.shape == "contour":
        tiles, outer, inner = contour_layout(vector, settings)
        columns = rows = 1
    else:
        tiles, columns, rows = choose_layout(settings)
        outer = outline(settings)
        inner = outline(settings, settings.frame_width_mm)
    frame = outer.difference(inner) if settings.frame else GeometryCollection()
    raised = unary_union([vector, frame])
    curved_border = None
    if settings.frame:
        if settings.frame_profile == "beaded" or (
            settings.shape == "contour" and settings.frame_profile == "rounded"
        ):
            curved_border = decorated_border(frame, outer, settings)
        elif settings.frame_profile == "rounded":
            curved_border = rounded_border(settings)
    if curved_border is not None:
        clean_boolean(curved_border)
        check_mesh(curved_border)
    pieces = []
    for tile in tiles:
        base = extrude(tile.shape, settings.base_mm)
        if settings.hanging == "keyholes":
            base = trimesh.boolean.difference(
                [base, *keyhole_cutters(tile, settings, columns, rows)], engine="manifold"
            )
        art = extrude(vector.intersection(tile.shape), settings.relief_mm, settings.base_mm)
        if curved_border is not None and frame.intersects(tile.shape):
            border = (
                trimesh.boolean.intersection(
                    [
                        curved_border,
                        extrude(tile.shape, settings.frame_height_mm, settings.base_mm),
                    ],
                    engine="manifold",
                )
                if len(tiles) > 1 or not tile.shape.covers(outer)
                else curved_border.copy()
            )
            if border.is_empty:
                border = None
        else:
            border = extrude(
                frame.intersection(tile.shape), settings.frame_height_mm, settings.base_mm
            )
        colored = [m for m in (art, border) if m is not None]
        artwork = (
            trimesh.boolean.union(colored, engine="manifold")
            if len(colored) > 1
            else colored[0]
            if colored
            else None
        )
        combined = (
            trimesh.boolean.union([base, artwork], engine="manifold")
            if artwork is not None
            else base.copy()
        )
        for mesh in (base, artwork, combined):
            if mesh is not None:
                clean_boolean(mesh)
                check_mesh(mesh)
        origin = [float(combined.bounds[0][0]), float(combined.bounds[0][1]), 0.0]
        for mesh in (base, artwork, combined):
            if mesh is not None:
                mesh.apply_translation(-np.array(origin))
        if (
            combined.extents[:2] > np.array([settings.bed_width_mm, settings.bed_height_mm]) + 1e-4
        ).any():
            raise ValueError("Final mesh exceeds the selected build plate.")
        pieces.append(Piece(tile, base, artwork, combined, origin))
    if settings.shape == "contour":
        notes.append(
            "Width and height bound the image; padding and bezel expand outward. "
            "The backing fills enclosed image holes; the raised artwork preserves them."
        )
        if settings.frame and settings.frame_profile == "rounded":
            notes.append("Rounded contour bezels use height bands no taller than 0.1 mm.")
    if settings.layout == "puzzle" and len(pieces) > 1:
        notes.append(
            "Print a small fit pair first. Puzzle clearance is uncalibrated for your printer."
        )
    if settings.hanging != "none":
        notes.append(
            "Mounting features are experimental and not load-rated. Support every wall panel."
        )
    if settings.hanging == "keyholes":
        notes.append(
            "Rear keyholes: 8 mm head entry, 4 mm shaft, 7 mm slide. Inspect bridging/supports."
        )
    notes.append(
        "Check brim, prime tower, exclusion zones, and filament assignments in Bambu Studio."
    )
    return Project(settings, vector, raised, pieces, columns, rows, notes)
