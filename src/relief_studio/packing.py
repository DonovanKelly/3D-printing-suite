"""Arrange separate pieces with a 3 mm bounding-box gap on measured print plates.

Preserve assembly row/column order when it fits a plate. Otherwise use stable
height-sorted shelves. Parts within each piece always receive one shared XY
translation; this module never changes the artwork-to-backing alignment.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .geometry import Project

GAP_MM = 3.0


@dataclass
class Placement:
    piece_index: int
    x: float
    y: float


def separated_layout(project: "Project") -> tuple[list[Placement], list[float]]:
    widths = [0.0] * project.columns
    heights = [0.0] * project.rows
    for piece in project.pieces:
        widths[piece.tile.column] = max(widths[piece.tile.column], float(piece.combined.extents[0]))
        heights[piece.tile.row] = max(heights[piece.tile.row], float(piece.combined.extents[1]))
    positions = []
    for i, piece in enumerate(project.pieces):
        c, r = piece.tile.column, piece.tile.row
        x = sum(widths[:c]) + GAP_MM * c + (widths[c] - piece.combined.extents[0]) / 2
        y = sum(heights[r + 1 :]) + GAP_MM * (project.rows - r - 1)
        y += (heights[r] - piece.combined.extents[1]) / 2
        positions.append(Placement(i, float(x), float(y)))
    return positions, [
        sum(widths) + GAP_MM * (project.columns - 1),
        sum(heights) + GAP_MM * (project.rows - 1),
    ]


def plan_plates(project: "Project") -> list[list[Placement]]:
    arranged, extents = separated_layout(project)
    width, height = project.settings.bed_width_mm, project.settings.bed_height_mm
    if extents[0] <= width + 1e-5 and extents[1] <= height + 1e-5:
        return [arranged]
    plates: list[list[Placement]] = []
    shelves: list[list[list[float]]] = []
    for index in sorted(
        range(len(project.pieces)), key=lambda i: (-project.pieces[i].combined.extents[1], i)
    ):
        w, h = (float(n) for n in project.pieces[index].combined.extents[:2])
        if w > width + 1e-5 or h > height + 1e-5:
            raise ValueError("A piece exceeds the usable build plate.")
        placed = False
        for plate, rows in zip(plates, shelves, strict=True):
            for row in rows:
                y, row_height, next_x = row
                if h <= row_height + 1e-5 and next_x + w <= width + 1e-5:
                    plate.append(Placement(index, next_x, y))
                    row[2] += w + GAP_MM
                    placed = True
                    break
            if placed:
                break
            y = rows[-1][0] + rows[-1][1] + GAP_MM
            if y + h <= height + 1e-5:
                rows.append([y, h, w + GAP_MM])
                plate.append(Placement(index, 0, y))
                placed = True
                break
        if not placed:
            plates.append([Placement(index, 0, 0)])
            shelves.append([[0, h, w + GAP_MM]])
    return plates
