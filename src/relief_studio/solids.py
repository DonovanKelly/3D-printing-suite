"""Extrude planar regions and reject meshes that cannot form closed printable volumes.

CrossSection normalizes point-touching rings before triangulation. Coordinates
stay in millimeters; callers own placement and material height alignment.
"""

import manifold3d
import numpy as np
import trimesh
from shapely import Geometry

from .artwork import polygons


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


def clean_boolean(mesh: trimesh.Trimesh) -> None:
    # Float32 booleans can collapse seam triangles. Weld the vertices and
    # remove collapsed faces so independent slicer/importer cleanup stays valid.
    if not mesh.copy().process().is_volume:
        mesh.merge_vertices()
        a, b, c = mesh.faces.T
        mesh.update_faces((a != b) & (b != c) & (a != c))
        mesh.remove_unreferenced_vertices()
