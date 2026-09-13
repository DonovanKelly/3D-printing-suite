"""Shared rounded footprints and closed border surfaces in millimeters.

All height sections have matching corner samples so a rounded border can be
lofted without staircase ledges. Degenerate corner triangles are removed when
an inward offset reaches a square corner. Layouts use the same outside outline.
"""

import numpy as np
import trimesh
from shapely.geometry import Polygon

from .settings import Settings


def corner_loop(settings: Settings, inset: float = 0) -> np.ndarray:
    radius = max(0, settings.corner_radius_mm - inset)
    left = bottom = inset + radius
    right = settings.width_mm - inset - radius
    top = settings.height_mm - inset - radius
    points = []
    for i, center in enumerate(((right, bottom), (right, top), (left, top), (left, bottom))):
        angles = np.linspace((i - 1) * np.pi / 2, i * np.pi / 2, 17)
        points.extend(np.array(center) + radius * np.column_stack((np.cos(angles), np.sin(angles))))
    return np.asarray(points)


def outline(settings: Settings, inset: float = 0) -> Polygon:
    return Polygon(corner_loop(settings, inset)).simplify(0)


def rounded_border(settings: Settings) -> trimesh.Trimesh:
    height, width = settings.frame_height_mm, settings.frame_width_mm
    roll = min(height / 2, width * 0.45)
    levels = [(0.0, 0.0), (height - roll, 0.0)]
    levels.extend(
        (height - roll + roll * np.sin(angle), roll * (1 - np.cos(angle)))
        for angle in np.linspace(0, np.pi / 2, 13)[1:]
    )
    vertices = []
    for z, inset in levels:
        for offset in (inset, width - inset):
            loop = corner_loop(settings, offset)
            vertices.extend(np.column_stack((loop, np.full(len(loop), z + settings.base_mm))))
    count = len(corner_loop(settings))
    faces = []

    def connect(a: int, b: int, reverse: bool = False):
        for k in range(count):
            n = (k + 1) % count
            pair = [[a + k, a + n, b + n], [a + k, b + n, b + k]]
            faces.extend([triangle[::-1] for triangle in pair] if reverse else pair)

    for level in range(len(levels) - 1):
        start, end = level * 2 * count, (level + 1) * 2 * count
        connect(start, end)
        connect(start + count, end + count, reverse=True)
    connect(0, count, reverse=True)
    start = (len(levels) - 1) * 2 * count
    connect(start, start + count)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    return mesh
