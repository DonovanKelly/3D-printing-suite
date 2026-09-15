"""Write self-contained, reproducible print packs with explicit material parts.

3MF core components preserve material alignment. Bambu project metadata binds
those components to two logical filaments and installed P1S/PLA presets. Physical
AMS tray selection remains a slicer operation; no printer jobs are generated.
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
from .packing import Placement, plan_plates, separated_layout

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def bambu_plate_offset(pieces: list[tuple[Piece, float, float]]) -> tuple[float, float]:
    min_x = min(x + piece.combined.bounds[0, 0] for piece, x, _ in pieces)
    min_y = min(y + piece.combined.bounds[0, 1] for piece, _, y in pieces)
    max_x = max(x + piece.combined.bounds[1, 0] for piece, x, _ in pieces)
    max_y = max(y + piece.combined.bounds[1, 1] for piece, _, y in pieces)
    dx, dy = (256 - max_x - min_x) / 2, (256 - max_y - min_y) / 2
    # P1S excludes the front-left 18 × 28 mm rectangle. Keep a 5 mm
    # clearance from it; translate the entire plate to preserve all gaps.
    for ox, oy in ((dx, dy), (max(dx, 23 - min_x), dy), (dx, max(dy, 33 - min_y))):
        if max_x + ox > 256 + 1e-5 or max_y + oy > 256 + 1e-5:
            continue
        if all(
            x + piece.combined.bounds[0, 0] + ox >= 23 - 1e-5
            or y + piece.combined.bounds[0, 1] + oy >= 33 - 1e-5
            for piece, x, y in pieces
        ):
            return float(ox), float(oy)
    raise ValueError(
        "Arranged plate reaches the P1S front-left exclusion zone. "
        "Reduce the usable bed width to 230 mm or use smaller pieces."
    )


def bambu_project_settings(project: Project) -> dict:
    # Preset references let Studio resolve its installed machine/PLA settings,
    # including machine G-code. Two AMS filaments still use ONE physical nozzle.
    printer = "Bambu Lab P1S 0.4 nozzle"
    process = "0.20mm Standard @BBL X1C"
    filament = "Generic PLA"
    return {
        "name": "project_settings",
        "from": "project",
        "version": "2.0.0.0",
        "printer_technology": "FFF",
        "printer_model": "Bambu Lab P1S",
        "printer_variant": "0.4",
        "printer_settings_id": printer,
        "print_settings_id": process,
        "filament_settings_id": [filament, filament],
        "inherits_group": [process, filament, filament, printer],
        "different_settings_to_system": ["", "filament_colour", "filament_colour", ""],
        "nozzle_diameter": ["0.4"],
        "filament_diameter": ["1.75", "1.75"],
        "filament_type": ["PLA", "PLA"],
        "filament_is_support": ["0", "0"],
        "filament_soluble": ["0", "0"],
        "filament_colour": [
            project.settings.background_color.upper(),
            project.settings.artwork_color.upper(),
        ],
        "filament_ids": ["GFL99", "GFL99"],
        "printable_area": ["0x0", "256x0", "256x256", "0x256"],
        "printable_height": "256",
    }


def path_data(geometry: Geometry) -> str:
    paths = []
    for polygon in polygons(geometry):
        for ring in (polygon.exterior, *polygon.interiors):
            points = list(ring.coords)
            paths.append("M" + " L".join(f"{x:.5f},{y:.5f}" for x, y in points) + " Z")
    return " ".join(paths)


def vector_svg(project: Project, assembly: bool = False, separated: bool = False) -> str:
    settings = project.settings
    height = settings.height_mm + (10 if settings.hanging == "loops" else 0)
    width = settings.width_mm
    min_x = min_y = 0
    if settings.shape == "contour":
        min_x, min_y, max_x, max_y = project.pieces[0].tile.shape.bounds
        width, height = max_x - min_x, max_y - min_y
    placements, extent = separated_layout(project)
    if separated:
        width, height = extent
        min_x = min_y = 0
    paths = []
    if assembly:
        for index, piece in enumerate(project.pieces):
            dx = placements[index].x - piece.origin[0] if separated else 0
            dy = placements[index].y - piece.origin[1] if separated else 0
            paths.append(f'<g transform="translate({dx:.5f} {dy:.5f})">')
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
            paths.append("</g>")
    else:
        paths.append(
            f'<rect x="{min_x}" y="{min_y}" width="{width}" height="{height}" fill="white"/>'
        )
        paths.append(f'<path d="{path_data(project.vector)}" fill="black"/>')
    labels = []
    if assembly and (settings.shape != "contour" or len(project.pieces) > 1):
        font_size = min(width / project.columns, height / project.rows) * 0.06
        for index, piece in enumerate(project.pieces):
            x, y = piece.tile.shape.representative_point().coords[0]
            if separated:
                x += placements[index].x - piece.origin[0]
                y += placements[index].y - piece.origin[1]
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
        f'transform="translate({-min_x} {height + min_y}) scale(1 -1)">{"".join(paths)}</g>'
        f"{''.join(labels)}</svg>"
    )


def write_3mf(piece: Piece, project: Project, destination: Path) -> None:
    _write_3mf(project, destination, [(piece, 0.0, 0.0)])


def write_plate_3mf(project: Project, destination: Path, placements: list[Placement]) -> None:
    _write_3mf(
        project, destination, [(project.pieces[p.piece_index], p.x, p.y) for p in placements]
    )


def _write_3mf(
    project: Project, destination: Path, pieces: list[tuple[Piece, float, float]]
) -> None:
    dx, dy = bambu_plate_offset(pieces)

    def child(parent: ET.Element, tag: str, **attributes: str) -> ET.Element:
        return ET.SubElement(parent, f"{{{CORE}}}{tag}", attributes)

    ET.register_namespace("", CORE)
    root = ET.Element(f"{{{CORE}}}model", {"unit": "millimeter", "xml:lang": "en-US"})
    child(root, "metadata", name="Title").text = "Relief Studio print plate"
    # Studio ignores ALL project settings unless Application carries its
    # versioned format marker. Record our actual generator separately.
    child(root, "metadata", name="Application").text = "BambuStudio-02.00.00.00"
    child(
        root, "metadata", name="Description"
    ).text = "Generated by Relief Studio 0.1.0; Bambu Studio 2.0 project format."
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
    build = child(root, "build")
    model_settings = ET.Element("config")
    plate_settings = ET.Element("plate")
    ET.SubElement(plate_settings, "metadata", key="plater_id", value="1")
    for piece_index, (piece, x, y) in enumerate(pieces):
        group_id = str(piece_index * 3 + 4)
        object_settings = ET.SubElement(model_settings, "object", id=group_id)
        ET.SubElement(object_settings, "metadata", key="name", value=piece.tile.name)
        ET.SubElement(object_settings, "metadata", key="extruder", value="1")
        object_ids = []
        for index, (name, mesh) in enumerate(
            (("Background", piece.base), ("Artwork + frame", piece.artwork))
        ):
            if mesh is None:
                continue
            object_id = str(piece_index * 3 + index + 2)
            obj = child(
                resources,
                "object",
                id=object_id,
                type="model",
                name=name,
                pid="1",
                pindex=str(index),
            )
            mesh_element = child(obj, "mesh")
            vertices = child(mesh_element, "vertices")
            for vx, vy, vz in mesh.vertices:
                child(vertices, "vertex", x=f"{vx:.7f}", y=f"{vy:.7f}", z=f"{vz:.7f}")
            triangles = child(mesh_element, "triangles")
            for a, b, c in mesh.faces:
                child(triangles, "triangle", v1=str(a), v2=str(b), v3=str(c))
            object_ids.append(object_id)
            # Bambu resolves part IDs to the mesh objects referenced by this
            # component group; core basematerials do not assign AMS filaments.
            part = ET.SubElement(object_settings, "part", id=object_id, subtype="normal_part")
            ET.SubElement(part, "metadata", key="name", value=name)
            ET.SubElement(part, "metadata", key="extruder", value=str(index + 1))
        group = child(resources, "object", id=group_id, type="model", name=piece.tile.name)
        components = child(group, "components")
        for object_id in object_ids:
            child(components, "component", objectid=object_id)
        child(
            build,
            "item",
            objectid=group_id,
            printable="1",
            transform=f"1 0 0 0 1 0 0 0 1 {x + dx:.7f} {y + dy:.7f} 0",
        )
        instance = ET.SubElement(plate_settings, "model_instance")
        ET.SubElement(instance, "metadata", key="object_id", value=group_id)
        ET.SubElement(instance, "metadata", key="instance_id", value="0")
        ET.SubElement(instance, "metadata", key="identify_id", value=str(piece_index + 1))
    model_settings.append(plate_settings)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="model" '
            'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
            '<Override PartName="/Metadata/model_settings.config" ContentType="application/xml"/>'
            '<Override PartName="/Metadata/project_settings.config" '
            'ContentType="application/json"/>'
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
        archive.writestr(
            "Metadata/model_settings.config",
            ET.tostring(model_settings, encoding="utf-8", xml_declaration=True),
        )
        archive.writestr(
            "Metadata/project_settings.config",
            json.dumps(bambu_project_settings(project), indent=2),
        )


def project_manifest(project: Project) -> dict:
    plates = plan_plates(project)
    offsets = [
        bambu_plate_offset([(project.pieces[p.piece_index], p.x, p.y) for p in plate])
        for plate in plates
    ]
    separated, extents = separated_layout(project)
    return {
        "schema_version": 1,
        "generator": "relief-studio/0.1.0",
        "units": "mm",
        "settings": project.settings.model_dump(),
        "grid": {"columns": project.columns, "rows": project.rows},
        "piece_count": len(project.pieces),
        "plate_count": len(plates),
        "separated_extents_mm": extents,
        "plates": [
            {
                "id": f"plate-{i + 1:02d}",
                "file": f"plates/plate-{i + 1:02d}.3mf",
                "pieces": [
                    {
                        "id": project.pieces[p.piece_index].tile.name,
                        "origin_mm": [p.x + dx, p.y + dy, 0],
                    }
                    for p in plate
                ],
            }
            for i, (plate, (dx, dy)) in enumerate(zip(plates, offsets, strict=True))
        ],
        "warnings": project.warnings,
        "physically_tested": False,
        "pieces": [
            {
                "id": p.tile.name,
                "row": p.tile.row + 1,
                "column": p.tile.column + 1,
                "assembly_origin_mm": p.origin,
                "separated_origin_mm": [separated[i].x, separated[i].y, 0],
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
            for i, p in enumerate(project.pieces)
        ],
    }


def print_instructions(project: Project) -> str:
    settings = project.settings
    dimensions = (
        "Image contour, finished piece including hanging: "
        + " × ".join(f"{v:.2f}" for v in project.pieces[0].combined.extents[:2])
        + " mm. Image size limits: "
        + f"{settings.width_mm:g} × {settings.height_mm:g} mm; bezel/padding expand outward."
        if settings.shape == "contour"
        else f"Finished plaque: {settings.width_mm:g} × {settings.height_mm:g} mm "
        "(loops extend above this)."
    )
    return f"""# Relief Studio print pack

{dimensions}
Layout: {project.columns} columns × {project.rows} rows, {len(project.pieces)} pieces.
Backing: {settings.base_mm:g} mm. Raised art: {settings.relief_mm:g} mm.
Clearance between internal edges: {settings.clearance_mm:g} mm.

1. Open plates/plate-01.3mf as a PROJECT in Bambu Studio. Each plate 3MF contains
   separate printable objects named rNN-cNN, one per piece. Background and
   Artwork + frame stay grouped INSIDE each piece, with their relative heights
   preserved. Do not merge the whole plate into one object. Pieces are arranged
   with at least 3 mm between bounding boxes. Each plate is a separate file;
   open additional plates/plate-NN.3mf files separately.
   Individual pieces/ folders remain available for printing a replacement.
   Objects are placed clear of the P1S front-left exclusion zone. Brims and
   prime towers still need space; inspect them after slicing.
2. The project starts with P1S / 0.4 mm nozzle / 0.20 mm Standard and two Generic
   PLA filaments in your chosen colors: Background = filament 1, Artwork + frame
   = filament 2. Check the printer, nozzle and PLA profiles for your setup, then
   map these logical filaments to your actual AMS trays in Studio. The file does
   not select physical trays. Use Open Project, not a geometry-only import, to
   retain the supplied project colors and settings.
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
   pieces.svg shows the separated pieces. Rows and columns identify where each
   named object belongs. In Puzzle mode, puzzle_seed and puzzle_style in
   project.json reproduce the cut pattern. Size-based splitting measures tabs
   and loops; a custom grid overrides the maximum-piece-size setting.
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
        (destination / "pieces.svg").write_text(vector_svg(project, True, True))
        svg2png(
            bytestring=assembly.encode(),
            write_to=str(destination / "preview.png"),
            output_width=1200,
        )
        (destination / "PRINTING.md").write_text(print_instructions(project))
        plate_folder = destination / "plates"
        plate_folder.mkdir()
        for i, plate in enumerate(plan_plates(project)):
            write_plate_3mf(project, plate_folder / f"plate-{i + 1:02d}.3mf", plate)
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
