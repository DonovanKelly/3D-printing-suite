"""Complementary planar partitions with measured clearance and printer fit.

Each seam transfers one shared lobe between neighbors, so the zero-clearance
pieces exactly cover the plaque without overlaps. Clearance removes a narrow
strip around internal seams only; the requested outside dimensions stay exact.
"""

from dataclasses import dataclass
from math import ceil
from random import Random

import numpy as np
from shapely import Geometry
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from .profiles import outline
from .settings import Settings


@dataclass
class Tile:
    row: int
    column: int
    shape: Polygon

    @property
    def name(self) -> str:
        return f"r{self.row + 1:02d}-c{self.column + 1:02d}"


def add_loops(shape: Geometry, settings: Settings, left: float, right: float) -> Geometry:
    top = settings.height_mm
    rings = []
    for x in (left + (right - left) * 0.25, left + (right - left) * 0.75):
        outer = Point(x, top + 3).buffer(6, quad_segs=24)
        hole = Point(x, top + 3).buffer(2.5, quad_segs=24)
        rings.append(outer.difference(hole))
    return unary_union([shape, *rings])


def partition(settings: Settings, columns: int, rows: int) -> list[Tile]:
    cw, ch = settings.width_mm / columns, settings.height_mm / rows
    if min(cw, ch) < 24:
        raise ValueError("Each grid cell must be at least 24 mm wide and tall.")
    cells = [
        box(c * cw, r * ch, (c + 1) * cw, (r + 1) * ch) for r in range(rows) for c in range(columns)
    ]
    if settings.layout == "puzzle":
        radius = min(cw, ch) * 0.09
        rng = Random(settings.puzzle_seed)

        def seam(a: int, b: int, x: float, y: float, length: float, vertical: bool, sign: int):
            randomized = settings.puzzle_style == "random"
            direction = rng.choice((-1, 1)) if randomized else sign
            position = rng.uniform(0.35, 0.65) if randomized else 0.5
            size = radius * (rng.uniform(0.8, 1.1) if randomized else 1)
            bow = rng.uniform(-0.04, 0.04) * min(cw, ch) if randomized else 0

            def point(t: float, offset: float = 0) -> tuple[float, float]:
                lateral = bow * np.sin(np.pi * t) + offset
                return (x + lateral, y + length * t) if vertical else (x + length * t, y + lateral)

            # Transfer the same bounded region once; neighbors never compute separate seams.
            if bow:
                strip = Polygon(
                    [point(0), *[point(t) for t in np.linspace(0, 1, 25)[1:-1]], point(1)]
                )
                owner, neighbor = (a, b) if bow > 0 else (b, a)
                cells[owner] = cells[owner].union(strip)
                cells[neighbor] = cells[neighbor].difference(strip)
            tab = Point(point(position, direction * size * 0.8)).buffer(size, quad_segs=24)
            owner, neighbor = (a, b) if direction == 1 else (b, a)
            cells[owner] = cells[owner].union(tab)
            cells[neighbor] = cells[neighbor].difference(tab)

        for r in range(rows):
            for c in range(columns - 1):
                left, right = r * columns + c, r * columns + c + 1
                seam(left, right, (c + 1) * cw, r * ch, ch, True, 1 if (r + c) % 2 == 0 else -1)
        for r in range(rows - 1):
            for c in range(columns):
                bottom, top = r * columns + c, (r + 1) * columns + c
                seam(bottom, top, c * cw, (r + 1) * ch, cw, False, 1 if (r + c) % 2 else -1)
    outer = box(0, 0, settings.width_mm, settings.height_mm)
    footprint = outline(settings)
    tiles = []
    for r in range(rows):
        for c in range(columns):
            shape = cells[r * columns + c]
            if settings.clearance_mm and len(cells) > 1:
                seam = shape.boundary.difference(outer.boundary)
                shape = shape.difference(seam.buffer(settings.clearance_mm / 2))
            shape = shape.intersection(footprint)
            if settings.hanging == "loops" and r == rows - 1:
                shape = add_loops(shape, settings, c * cw, (c + 1) * cw)
            if shape.is_empty or shape.geom_type != "Polygon" or not shape.is_valid:
                raise ValueError(
                    "Layout disconnected a piece. Reduce clearance or use larger pieces."
                )
            # Labels count rows from the top, matching the front-view assembly map.
            tiles.append(Tile(rows - r - 1, c, shape))
    return sorted(tiles, key=lambda t: (t.row, t.column))


def fits(tiles: list[Tile], settings: Settings, size_limit: bool = False) -> bool:
    width, height = settings.bed_width_mm, settings.bed_height_mm
    if size_limit:
        width, height = min(width, settings.piece_size_mm), min(height, settings.piece_size_mm)
    return all(
        t.shape.bounds[2] - t.shape.bounds[0] <= width + 1e-6
        and t.shape.bounds[3] - t.shape.bounds[1] <= height + 1e-6
        for t in tiles
    )


def choose_layout(settings: Settings) -> tuple[list[Tile], int, int]:
    if settings.layout == "plaque" or settings.columns:
        columns, rows = settings.columns or 1, settings.rows or 1
        tiles = partition(settings, columns, rows)
        if not fits(tiles, settings):
            raise ValueError(
                "A piece exceeds the usable build plate. Choose automatic Tiles/Puzzle "
                "or increase the grid count; tabs and loops also need room."
            )
        return tiles, columns, rows
    size_limit = settings.split_mode == "size"
    width_limit = (
        min(settings.bed_width_mm, settings.piece_size_mm) if size_limit else settings.bed_width_mm
    )
    height_limit = (
        min(settings.bed_height_mm, settings.piece_size_mm)
        if size_limit
        else settings.bed_height_mm
    )
    candidates = sorted(
        (
            (c, r)
            for c in range(max(1, ceil(settings.width_mm / width_limit)), 13)
            for r in range(max(1, ceil(settings.height_mm / height_limit)), 13)
            if 2 <= c * r <= 64 and min(settings.width_mm / c, settings.height_mm / r) >= 24
        ),
        key=lambda cr: (cr[0] * cr[1], abs(settings.width_mm / cr[0] - settings.height_mm / cr[1])),
    )
    for columns, rows in candidates:
        tiles = partition(settings, columns, rows)
        if fits(tiles, settings, size_limit):
            return tiles, columns, rows
    raise ValueError(
        "No split fits the piece size and build plate within 64 pieces (minimum cell 24 mm). "
        "Increase Max piece size, use Largest panels, or adjust the finished dimensions."
    )
