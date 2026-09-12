"""Write self-contained, reproducible print packs with explicit material parts.

3MF uses core components to keep backing and raised artwork grouped with their
relative z offsets intact. Colors are display/material hints, never a promise
that a slicer will automatically choose the user's AMS filament slots.
"""

import hashlib
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from cairosvg import svg2png
from shapely import Geometry

from .artwork import polygons
from .geometry import Piece, Project

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def path_data(geometry: Geometry) -> str:
    paths = []
    for polygon in polygons(geometry):
        for ring in (polygon.exterior, *polygon.interiors):
            points = list(ring.coords)
            paths.append("M" + " L".join(f"{x:.5f},{y:.5f}" for x, y in points) + " Z")
    return " ".join(paths)


def vector_svg(project: Project, assembly: bool = False) -> str:
    settings = project.settings
    height = settings.height_mm + (10 if settings.hanging == "loops" else 0)
    width = settings.width_mm
    paths = []
    if assembly:
        for piece in project.pieces:
            paths.append(
                f'<path d="{path_data(piece.tile.shape)}" '
                f'fill="{settings.background_color}" stroke="#8e958e" stroke-width="0.3"/>'
            )
            art = project.raised.intersection(piece.tile.shape)
            paths.append(f'<path d="{path_data(art)}" fill="{settings.artwork_color}"/>')
            paths.append(
                f'<path d="{path_data(piece.tile.shape)}" fill="none" '
                'stroke="#859184" stroke-width="0.25"/>'
            )
    else:
        paths.append(f'<rect width="{width}" height="{settings.height_mm}" fill="white"/>')
        paths.append(f'<path d="{path_data(project.vector)}" fill="black"/>')
    labels = []
    if assembly:
        font_size = min(width / project.columns, height / project.rows) * 0.06
        for piece in project.pieces:
            x, y = piece.tile.shape.representative_point().coords[0]
            labels.append(
                f'<rect x="{x - font_size * 2.5:.3f}" y="{height - y - font_size:.3f}" '
                f'width="{font_size * 5:.3f}" height="{font_size * 1.5:.3f}" '
                f'rx="{font_size * 0.25:.3f}" fill="#fcfcfa" stroke="#859184" '
                f'stroke-width="{font_size * 0.04:.3f}"/>'
                f'<text x="{x:.3f}" y="{height - y:.3f}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="{font_size:.2f}" '
                f'fill="#285f49">{piece.tile.name}</text>'
            )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="#f5f4f0"/>'
        f'<g fill-rule="evenodd" '
        f'transform="translate(0 {height}) scale(1 -1)">{"".join(paths)}</g>'
        f"{''.join(labels)}</svg>"
    )


def write_3mf(piece: Piece, project: Project, destination: Path) -> None:
    def child(parent: ET.Element, tag: str, **attributes: str) -> ET.Element:
        return ET.SubElement(parent, f"{{{CORE}}}{tag}", attributes)

    ET.register_namespace("", CORE)
    root = ET.Element(f"{{{CORE}}}model", {"unit": "millimeter", "xml:lang": "en-US"})
    child(root, "metadata", name="Title").text = f"Relief Studio {piece.tile.name}"
    resources = child(root, "resources")
    materials = child(resources, "basematerials", id="1")
    child(
        materials, "base", name="Background", displaycolor=project.settings.background_color.upper()
    )
    child(
        materials,
        "base",
        name="Artwork + frame",
        displaycolor=project.settings.artwork_color.upper(),
    )
    object_ids = []
    for index, (name, mesh) in enumerate(
        (("Background", piece.base), ("Artwork + frame", piece.artwork))
    ):
        if mesh is None:
            continue
        object_id = str(index + 2)
        obj = child(
            resources, "object", id=object_id, type="model", name=name, pid="1", pindex=str(index)
        )
        mesh_element = child(obj, "mesh")
        vertices = child(mesh_element, "vertices")
        for x, y, z in mesh.vertices:
            child(vertices, "vertex", x=f"{x:.7f}", y=f"{y:.7f}", z=f"{z:.7f}")
        triangles = child(mesh_element, "triangles")
        for a, b, c in mesh.faces:
            child(triangles, "triangle", v1=str(a), v2=str(b), v3=str(c))
        object_ids.append(object_id)
    group = child(resources, "object", id="4", type="model", name=piece.tile.name)
    components = child(group, "components")
    for object_id in object_ids:
        child(components, "component", objectid=object_id)
    child(child(root, "build"), "item", objectid="4")
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="model" '
            'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
            "</Relationships>",
        )
        archive.writestr(
            "3D/3dmodel.model", ET.tostring(root, encoding="utf-8", xml_declaration=True)
        )


def project_manifest(project: Project) -> dict:
    return {
        "schema_version": 1,
        "generator": "relief-studio/0.1.0",
        "units": "mm",
        "settings": project.settings.model_dump(),
        "grid": {"columns": project.columns, "rows": project.rows},
        "piece_count": len(project.pieces),
        "warnings": project.warnings,
        "physically_tested": False,
        "pieces": [
            {
                "id": p.tile.name,
                "row": p.tile.row + 1,
                "column": p.tile.column + 1,
                "assembly_origin_mm": p.origin,
                "extents_mm": [round(float(v), 4) for v in p.combined.extents],
                "volume_mm3": round(float(p.combined.volume), 3),
                "watertight": bool(p.combined.is_watertight),
                "material_parts": 2 if p.artwork is not None else 1,
                "files": {
                    "3mf": f"pieces/{p.tile.name}/{p.tile.name}.3mf",
                    "combined": f"pieces/{p.tile.name}/combined.stl",
                    "background": f"pieces/{p.tile.name}/background.stl",
                    **(
                        {"artwork": f"pieces/{p.tile.name}/artwork.stl"}
                        if p.artwork is not None
                        else {}
                    ),
                },
            }
            for p in project.pieces
        ],
    }


def print_instructions(project: Project) -> str:
    settings = project.settings
    return f"""# Relief Studio print pack

Finished plaque: {settings.width_mm:g} × {settings.height_mm:g} mm (loops extend above this).
Layout: {project.columns} columns × {project.rows} rows, {len(project.pieces)} pieces.
Backing: {settings.base_mm:g} mm. Raised art: {settings.relief_mm:g} mm.
Clearance between internal edges: {settings.clearance_mm:g} mm.

1. Open each piece's 3MF in Bambu Studio as a model. It contains grouped
   Background and Artwork + frame parts with their relative heights preserved.
2. Select the P1S, your nozzle, PLA profiles, and actual AMS filaments. Assign
   the two named parts to the slots you want. Display colors are only hints.
3. If your slicer flattens the 3MF grouping, import background.stl and
   artwork.stl TOGETHER as one object with multiple parts. Preserve their shared
   coordinates; do not arrange or drop artwork to the bed independently.
4. Alternatively use combined.stl and a filament change at z={settings.base_mm:g}
   mm. Choose the first layer above the base using the sliced layer preview.
   The border uses the same color as the art. Set layer heights compatible with
   the backing and relief thicknesses (defaults are multiples of 0.2 mm).
5. Lay the flat back on the bed. Inspect first layer, tiny regions, top surfaces,
   prime tower, brim, and exclusion zones. Slice each piece before printing.
6. Use assembly.svg/preview.png to put pieces together, viewed from the FRONT.
   Row 01 is the top. Names are on the map; they are not embossed on the parts.

The two material volumes touch without overlapping. The combined STL is a
boolean union, not overlapping shells. STLs are unitless; import them in mm.

Puzzle fit has NOT been physically calibrated. Print the supplied calibration
pair or a small project first. Puzzle tabs align pieces in-plane and do not
replace mounting for individual panels. Hanging features are experimental,
not load-rated. Rear keyholes may require support/bridging tuning. Avoid relying
on top-row loops alone to hold a large assembly.

Notes from generation:
{chr(10).join("- " + note for note in project.warnings)}

Reproduce using project.json and the same source image. The original image is
not copied into this pack. Its SHA-256 is recorded in manifest.json.
"""


def export_project(project: Project, destination: Path, source_data: bytes) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    try:
        manifest = project_manifest(project)
        manifest["source_sha256"] = hashlib.sha256(source_data).hexdigest()
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (destination / "project.json").write_text(project.settings.model_dump_json(indent=2) + "\n")
        (destination / "artwork.svg").write_text(vector_svg(project))
        assembly = vector_svg(project, assembly=True)
        (destination / "assembly.svg").write_text(assembly)
        svg2png(
            bytestring=assembly.encode(),
            write_to=str(destination / "preview.png"),
            output_width=1200,
        )
        (destination / "PRINTING.md").write_text(print_instructions(project))
        for piece in project.pieces:
            folder = destination / "pieces" / piece.tile.name
            folder.mkdir(parents=True)
            write_3mf(piece, project, folder / f"{piece.tile.name}.3mf")
            piece.base.export(folder / "background.stl")
            piece.combined.export(folder / "combined.stl")
            if piece.artwork is not None:
                piece.artwork.export(folder / "artwork.stl")
        with ZipFile(destination / "print-pack.zip", "w", ZIP_DEFLATED) as archive:
            for path in sorted(destination.rglob("*")):
                if path.is_file() and path.name != "print-pack.zip":
                    archive.write(path, path.relative_to(destination))
        return manifest
    except Exception:
        # The directory was created exclusively above, so only this failed export is removed.
        shutil.rmtree(destination)
        raise
