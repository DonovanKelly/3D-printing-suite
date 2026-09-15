"""Follow selected artwork with one supported backing and optional decorative rim.

Only the backing fills enclosed holes; the image geometry remains untouched.
Disconnected silhouettes must join through padding, never an implicit convex
hull. Rounded rims use bounded height bands so inward offsets may split or
vanish at concave corners without attempting to loft incompatible rings.
"""

from math import ceil, sqrt

import trimesh
from shapely import Geometry
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .artwork import polygons
from .layout import Tile, add_top_loop, fits
from .settings import Settings
from .solids import extrude


def contour_layout(vector: Geometry, settings: Settings) -> tuple[list[Tile], Geometry, Geometry]:
    silhouette = unary_union([Polygon(p.exterior) for p in polygons(vector)])
    inner = silhouette.buffer(settings.margin_mm, quad_segs=24)
    outer = silhouette.buffer(
        settings.margin_mm + (settings.frame_width_mm if settings.frame else 0), quad_segs=24
    )
    # Expanding disconnected shapes can enclose new pockets. Fill those only
    # in the backing; they are background within the bezel, not through-holes.
    outer = unary_union([Polygon(p.exterior) for p in polygons(outer)])
    inner = unary_union([Polygon(p.exterior) for p in polygons(inner)])
    if outer.geom_type != "Polygon" or not outer.is_valid:
        raise ValueError(
            "Image contour has disconnected islands. Increase Padding or Border width "
            "to join them, or choose Rectangle."
        )
    shape = outer
    if settings.hanging == "loops":
        shape = add_top_loop(outer, settings, outer.bounds[0], outer.bounds[2])
    if shape.geom_type != "Polygon" or not shape.is_valid:
        raise ValueError("The top loop is unsupported. Increase Padding or choose no hanging.")
    tiles = [Tile(0, 0, shape)]
    if not fits(tiles, settings):
        raise ValueError(
            "Image contour exceeds the usable build plate, including its bezel and loop. "
            "Reduce Width or Height, or remove the top loop."
        )
    return tiles, outer, inner


def decorated_border(frame: Geometry, outer: Geometry, settings: Settings) -> trimesh.Trimesh:
    height, width, z = settings.frame_height_mm, settings.frame_width_mm, settings.base_mm
    if settings.frame_profile == "rounded":
        roll = min(height / 2, width * 0.45)
        shoulder = height - roll
        solids = [extrude(frame, shoulder, z)]
        count = max(12, ceil(roll / 0.1))
        # Midpoint sampling approximates a quarter-circle roll on both edges.
        # Each band overlaps the supporting prism down to the background.
        for i in range(count):
            t = (i + 0.5) / count
            inset = roll * (1 - sqrt(1 - t * t))
            section = frame.buffer(-inset, quad_segs=24)
            mesh = extrude(section, shoulder + roll * (i + 1) / count, z)
            if mesh is not None:
                solids.append(mesh)
        return trimesh.boolean.union(solids, engine="manifold")

    radius = min(width * 0.35, 3)
    stem = height * 0.4
    center_z = height * 0.3
    solids = [extrude(frame, stem, z)]
    center = outer.buffer(-width / 2, quad_segs=24)
    # Beads follow arc length, with a bounded count even on a highly detailed
    # source. The rim prism clips caps at narrow or concave parts of the bezel.
    rings = [p.exterior for p in polygons(center)]
    pitch = max(radius * 2.6, sum(r.length for r in rings) / 500)
    for ring in rings:
        count = max(1, int(ring.length / pitch))
        for i in range(count):
            point = ring.interpolate((i + 0.5) * ring.length / count)
            bead = trimesh.creation.icosphere(subdivisions=2)
            # Keep the rim top away from the sphere's equator vertices. A cut
            # exactly through them can leave duplicate edges after float32 welding.
            bead.apply_scale([radius, radius, (height - center_z) / bead.bounds[1, 2]])
            bead.apply_translation([point.x, point.y, z + center_z])
            solids.append(bead)
    beads = trimesh.boolean.union(solids, engine="manifold")
    return trimesh.boolean.intersection([beads, extrude(frame, height, z)], engine="manifold")
