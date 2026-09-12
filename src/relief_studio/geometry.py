"""Extrude partitioned artwork into aligned material solids and validated pieces.

Material volumes meet at z=base thickness without overlap. Optional keyholes
have a wide internal head channel and a narrow opening at the back, retaining
a front skin and a lip for the screw head. They are experimental print features.
"""

from dataclasses import dataclass

import manifold3d
import numpy as np
import trimesh
from shapely import Geometry
from shapely.geometry import GeometryCollection, Point, box
from shapely.ops import unary_union

from .artwork import polygons, trace_image
from .layout import Tile, choose_layout
from .settings import Settings


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


def extrude(region: Geometry, height: float, z: float = 0) -> trimesh.Trimesh | None:
    contours = []
    for polygon in polygons(region):
        if polygon.area < 1e-7:
            continue
        contours.extend(
            np.array(ring.coords)[:-1] for ring in (polygon.exterior, *polygon.interiors)
        )
    if not contours:
        return None
    # Clipped artwork can contain point-touching holes. CrossSection normalizes
    # those contours before triangulation instead of creating open earcut shells.
    section = manifold3d.CrossSection(contours, manifold3d.FillRule.EvenOdd)
    solid = section.extrude(height).to_mesh()
    mesh = trimesh.Trimesh(
        vertices=solid.vert_properties[:, :3], faces=solid.tri_verts, process=False
    )
    mesh.apply_translation([0, 0, z])
    return mesh


def check_mesh(mesh: trimesh.Trimesh) -> None:
    if not (
        mesh.is_watertight
        and mesh.is_winding_consistent
        and mesh.is_volume
        and np.isfinite(mesh.vertices).all()
        and mesh.volume > 0
        and mesh.copy().process().is_volume
    ):
        raise ValueError(
            "Generated geometry is not a closed positive-volume solid. "
            "Try simplifying the artwork or increasing the piece size."
        )


def keyhole_cutters(
    tile: Tile, settings: Settings, columns: int, rows: int
) -> list[trimesh.Trimesh]:
    # Anchor to the nominal cell, not its tab-expanded bounds; otherwise a top
    # tab could move the keyholes above the solid body of a puzzle piece.
    cell_width = settings.width_mm / columns
    left, right = tile.column * cell_width, (tile.column + 1) * cell_width
    top = settings.height_mm * (1 - tile.row / rows)
    cutters = []
    for x in (left + (right - left) * 0.3, left + (right - left) * 0.7):
        y = top - 16
        head = Point(x, y).buffer(4, quad_segs=24)
        shaft = box(x - 2, y, x + 2, y + 7).union(Point(x, y + 7).buffer(2, quad_segs=24))
        opening = head.union(shaft)
        channel = head.union(Point(x, y + 7).buffer(4, quad_segs=24)).convex_hull
        if not tile.shape.buffer(-3).covers(channel):
            raise ValueError("Piece is too small for rear keyholes. Use fewer pieces or top loops.")
        # Open from the bed-facing back; leave a 1.2 mm retaining lip over the head channel.
        cutters.extend([extrude(opening, 3.2, -0.1), extrude(channel, 1.9, 1.2)])
    return cutters


def build_project(data: bytes, settings: Settings) -> Project:
    vector, notes = trace_image(data, settings)
    tiles, columns, rows = choose_layout(settings)
    outer = box(0, 0, settings.width_mm, settings.height_mm)
    frame = (
        outer.difference(outer.buffer(-settings.frame_width_mm))
        if settings.frame
        else GeometryCollection()
    )
    raised = unary_union([vector, frame])
    pieces = []
    for tile in tiles:
        base = extrude(tile.shape, settings.base_mm)
        if settings.hanging == "keyholes":
            base = trimesh.boolean.difference(
                [base, *keyhole_cutters(tile, settings, columns, rows)], engine="manifold"
            )
        art = extrude(vector.intersection(tile.shape), settings.relief_mm, settings.base_mm)
        border = extrude(frame.intersection(tile.shape), settings.frame_height_mm, settings.base_mm)
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
