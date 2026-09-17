/*! In-memory preview DTOs and reproducible ZIP/STL/3MF packs. Core component groups
and Bambu project metadata assign two or three logical filaments through one nozzle.
All material parts keep identical local origins; source images are never exported. */
use crate::{
    EngineError, Result,
    artwork::{bounds, render_svg},
    geometry::Project,
    packing::{self, Placement},
    settings::*,
};
use manifold_csg::CrossSection;
use serde_json::{Value, json};
use std::{
    fmt::Write as _,
    io::{Cursor, Write},
};
use zip::{ZipWriter, write::SimpleFileOptions};

pub fn manifest(p: &Project) -> Result<Value> {
    let plates = packing::plates(p);
    let (separated, extents) = packing::separated(p);
    let mut plate_data = Vec::new();
    for (i, plate) in plates.iter().enumerate() {
        let [dx, dy] = packing::bambu_offset(p, plate)?;
        plate_data.push(json!({"id":format!("plate-{:02}",i+1),"file":format!("plates/plate-{:02}.3mf",i+1),"pieces":plate.iter().map(|q|json!({"id":p.pieces[q.piece].tile.name(),"origin_mm":[q.x+dx,q.y+dy,0.0]})).collect::<Vec<_>>() }));
    }
    let pieces = p.pieces.iter().enumerate().map(|(i, piece)| {
        let name = piece.tile.name();
        let mut files = json!({
            "3mf": format!("pieces/{name}/{name}.3mf"),
            "combined": format!("pieces/{name}/combined.stl"),
            "background": format!("pieces/{name}/background.stl"),
        });
        for (material, mesh) in [("artwork", &piece.artwork), ("border", &piece.border)] {
            if mesh.is_some() { files[material] = json!(format!("pieces/{name}/{material}.stl")); }
        }
        json!({
            "id": name, "row": piece.tile.row + 1, "column": piece.tile.column + 1,
            "assembly_origin_mm": piece.origin,
            "separated_origin_mm": [separated[i].x, separated[i].y, 0.0],
            "extents_mm": piece.extents, "volume_mm3": piece.combined.volume(), "watertight": true,
            "material_parts": 1 + usize::from(piece.artwork.is_some()) + usize::from(piece.border.is_some()),
            "files": files,
        })
    }).collect::<Vec<_>>();
    Ok(json!({
        "schema_version": 1, "generator": "relief-studio/0.2.0", "units": "mm",
        "settings": p.settings, "source_sha256": p.source_hash,
        "grid": { "columns": p.columns, "rows": p.rows },
        "piece_count": pieces.len(), "plate_count": plates.len(),
        "separated_extents_mm": extents, "plates": plate_data,
        "warnings": p.warnings, "physically_tested": false, "pieces": pieces,
    }))
}

fn path(shape: &CrossSection) -> String {
    let mut s = String::new();
    for ring in shape.to_polygons() {
        for (i, p) in ring.iter().enumerate() {
            let _ = write!(
                s,
                "{}{:.5},{:.5}",
                if i == 0 { "M" } else { " L" },
                p[0],
                p[1]
            );
        }
        s.push_str(" Z ");
    }
    s
}
pub fn svg(p: &Project, assembly: bool, separated: bool) -> String {
    let s = &p.settings;
    let mut width = s.width_mm;
    let mut height = s.height_mm
        + if s.hanging == Hanging::Loops {
            10.0
        } else {
            0.0
        };
    let mut min_x = 0.0;
    let mut min_y = 0.0;
    if s.shape == Shape::Contour {
        let all: Vec<_> = p
            .pieces
            .iter()
            .map(|piece| bounds(&piece.tile.shape))
            .collect();
        min_x = all.iter().map(|b| b[0]).fold(f64::INFINITY, f64::min);
        min_y = all.iter().map(|b| b[1]).fold(f64::INFINITY, f64::min);
        width = all.iter().map(|b| b[2]).fold(f64::NEG_INFINITY, f64::max) - min_x;
        height = all.iter().map(|b| b[3]).fold(f64::NEG_INFINITY, f64::max) - min_y;
    }
    let (places, extent) = packing::separated(p);
    if separated {
        width = extent[0];
        height = extent[1];
        min_x = 0.0;
        min_y = 0.0;
    }
    let mut paths = String::new();
    let mut labels = String::new();
    if assembly {
        for (i, piece) in p.pieces.iter().enumerate() {
            let dx = if separated {
                places[i].x - piece.origin[0]
            } else {
                0.0
            };
            let dy = if separated {
                places[i].y - piece.origin[1]
            } else {
                0.0
            };
            let _ = write!(
                paths,
                "<g transform=\"translate({dx:.5} {dy:.5})\"><path d=\"{}\" fill=\"{}\" stroke=\"#8e958e\" stroke-width=\"0.3\"/><path d=\"{}\" fill=\"{}\"/><path d=\"{}\" fill=\"{}\"/><path d=\"{}\" fill=\"none\" stroke=\"#859184\" stroke-width=\"0.25\"/></g>",
                path(&piece.tile.shape),
                s.background_color,
                path(&p.vector.intersection(&piece.tile.shape)),
                s.artwork_color,
                path(&p.border.intersection(&piece.tile.shape)),
                s.resolved_border_color(),
                path(&piece.tile.shape)
            );
            if s.shape != Shape::Contour || p.pieces.len() > 1 {
                let b = bounds(&piece.tile.shape);
                let x = (b[0] + b[2]) / 2.0 + dx - min_x;
                let y = height + min_y - ((b[1] + b[3]) / 2.0 + dy);
                let size = (width / p.columns as f64).min(height / p.rows as f64) * 0.06;
                let name = piece.tile.name();
                let label_width = size * (name.len() as f64 * 0.65 + 1.0);
                let _ = write!(
                    labels,
                    "<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" rx=\"{}\" fill=\"#fcfcfa\" stroke=\"#859184\" stroke-width=\"{}\"/><text x=\"{x}\" y=\"{y}\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"{size}\" fill=\"#285f49\">{}</text>",
                    x - label_width / 2.0,
                    y - size,
                    label_width,
                    size * 1.5,
                    size * 0.25,
                    size * 0.04,
                    name
                );
            }
        }
    } else {
        let _ = write!(
            paths,
            "<rect x=\"{min_x}\" y=\"{min_y}\" width=\"{width}\" height=\"{height}\" fill=\"white\"/><path d=\"{}\" fill=\"black\"/>",
            path(&p.vector)
        );
    }
    format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}mm\" height=\"{height}mm\" viewBox=\"0 0 {width} {height}\"><rect width=\"{width}\" height=\"{height}\" fill=\"#f5f4f0\"/><g fill-rule=\"evenodd\" transform=\"translate({} {}) scale(1 -1)\">{paths}</g>{labels}</svg>",
        -min_x,
        height + min_y
    )
}
pub fn preview(p: &Project, id: &str) -> Result<Value> {
    let mut meshes = Vec::new();
    for piece in &p.pieces {
        for (name, mesh) in [
            ("background", Some(&piece.base)),
            ("artwork", piece.artwork.as_ref()),
            ("border", piece.border.as_ref()),
        ] {
            if let Some(mesh) = mesh {
                meshes.push(json!({"piece":piece.tile.name(),"material":name,"origin":piece.origin,"vertices":mesh.vertices,"faces":mesh.faces}));
            }
        }
    }
    Ok(
        json!({"id":id,"manifest":manifest(p)?,"vector_svg":svg(p,false,false),"assembly_svg":svg(p,true,false),"separated_svg":svg(p,true,true),"meshes":meshes}),
    )
}
fn filaments(p: &Project) -> Vec<(&str, &str)> {
    let s = &p.settings;
    let mut materials = vec![
        (
            if s.frame && s.border_material == BorderMaterial::Background {
                "Background + border"
            } else {
                "Background"
            },
            s.background_color.as_str(),
        ),
        (
            if s.frame && s.border_material == BorderMaterial::Artwork {
                "Artwork + frame"
            } else {
                "Artwork"
            },
            s.artwork_color.as_str(),
        ),
    ];
    if p.pieces.iter().any(|piece| piece.border.is_some()) {
        materials.push(("Border", &s.border_color));
    }
    materials
}
pub fn bambu_settings(p: &Project) -> Value {
    let printer = "Bambu Lab P1S 0.4 nozzle";
    let process = "0.20mm Standard @BBL X1C";
    let filament = "Generic PLA";
    let materials = filaments(p);
    let count = materials.len();
    let mut inherits = vec![process];
    inherits.extend(vec![filament; count]);
    inherits.push(printer);
    let mut differences = vec![""];
    differences.extend(vec!["filament_colour"; count]);
    differences.push("");
    json!({
        "name":"project_settings", "from":"project", "version":"2.0.0.0",
        "printer_technology":"FFF", "printer_model":"Bambu Lab P1S", "printer_variant":"0.4",
        "printer_settings_id":printer, "print_settings_id":process,
        "filament_settings_id":vec![filament; count], "inherits_group":inherits,
        "different_settings_to_system":differences, "nozzle_diameter":["0.4"],
        "filament_diameter":vec!["1.75"; count], "filament_type":vec!["PLA"; count],
        "filament_is_support":vec!["0"; count], "filament_soluble":vec!["0"; count],
        "filament_colour":materials.iter().map(|(_,color)|color.to_uppercase()).collect::<Vec<_>>(),
        "filament_ids":vec!["GFL99"; count],
        "printable_area":["0x0","256x0","256x256","0x256"], "printable_height":"256",
    })
}
fn zip(entries: Vec<(String, Vec<u8>)>) -> Result<Vec<u8>> {
    let mut archive = ZipWriter::new(Cursor::new(Vec::new()));
    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    for (name, data) in entries {
        archive
            .start_file(name, options)
            .map_err(|e| EngineError::input(e.to_string()))?;
        archive
            .write_all(&data)
            .map_err(|e| EngineError::input(e.to_string()))?;
    }
    Ok(archive
        .finish()
        .map_err(|e| EngineError::input(e.to_string()))?
        .into_inner())
}
pub fn three_mf(p: &Project, places: &[Placement]) -> Result<Vec<u8>> {
    let [dx, dy] = packing::bambu_offset(p, places)?;
    let materials = filaments(p);
    let mut resources = String::from("<basematerials id=\"1\">");
    for (label, color) in &materials {
        let _ = write!(
            resources,
            "<base name=\"{label}\" displaycolor=\"{}\"/>",
            color.to_uppercase()
        );
    }
    resources.push_str("</basematerials>");
    let mut build = String::new();
    let mut config = String::from("<config>");
    let mut plate = String::from("<plate><metadata key=\"plater_id\" value=\"1\"/>");
    for (i, place) in places.iter().enumerate() {
        let piece = &p.pieces[place.piece];
        let name = piece.tile.name();
        let group = i * 4 + 5;
        let _ = write!(
            config,
            "<object id=\"{group}\"><metadata key=\"name\" value=\"{name}\"/><metadata key=\"extruder\" value=\"1\"/>"
        );
        let mut components = String::new();
        for (material, mesh) in [
            Some(&piece.base),
            piece.artwork.as_ref(),
            piece.border.as_ref(),
        ]
        .into_iter()
        .enumerate()
        {
            if let Some(mesh) = mesh {
                let id = i * 4 + material + 2;
                let label = materials[material].0;
                let _ = write!(
                    resources,
                    "<object id=\"{id}\" type=\"model\" name=\"{label}\" pid=\"1\" pindex=\"{material}\"><mesh><vertices>"
                );
                for v in mesh.vertices.as_chunks::<3>().0.iter() {
                    let _ = write!(
                        resources,
                        "<vertex x=\"{:.7}\" y=\"{:.7}\" z=\"{:.7}\"/>",
                        v[0], v[1], v[2]
                    );
                }
                resources.push_str("</vertices><triangles>");
                for f in mesh.faces.as_chunks::<3>().0.iter() {
                    let _ = write!(
                        resources,
                        "<triangle v1=\"{}\" v2=\"{}\" v3=\"{}\"/>",
                        f[0], f[1], f[2]
                    );
                }
                resources.push_str("</triangles></mesh></object>");
                let _ = write!(components, "<component objectid=\"{id}\"/>");
                let _ = write!(
                    config,
                    "<part id=\"{id}\" subtype=\"normal_part\"><metadata key=\"name\" value=\"{label}\"/><metadata key=\"extruder\" value=\"{}\"/></part>",
                    material + 1
                );
            }
        }
        config.push_str("</object>");
        let _ = write!(
            resources,
            "<object id=\"{group}\" type=\"model\" name=\"{name}\"><components>{components}</components></object>"
        );
        let _ = write!(
            build,
            "<item objectid=\"{group}\" printable=\"1\" transform=\"1 0 0 0 1 0 0 0 1 {:.7} {:.7} 0\"/>",
            place.x + dx,
            place.y + dy
        );
        let _ = write!(
            plate,
            "<model_instance><metadata key=\"object_id\" value=\"{group}\"/><metadata key=\"instance_id\" value=\"0\"/><metadata key=\"identify_id\" value=\"{}\"/></model_instance>",
            i + 1
        );
    }
    plate.push_str("</plate>");
    config.push_str(&plate);
    config.push_str("</config>");
    let model = format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?><model xmlns=\"http://schemas.microsoft.com/3dmanufacturing/core/2015/02\" unit=\"millimeter\" xml:lang=\"en-US\"><metadata name=\"Title\">Relief Studio print plate</metadata><metadata name=\"Application\">BambuStudio-02.00.00.00</metadata><metadata name=\"Description\">Generated by Relief Studio 0.2.0; Bambu Studio 2.0 project format.</metadata><resources>{resources}</resources><build>{build}</build></model>"
    );
    zip(vec![
        (
            "[Content_Types].xml".into(),
            include_bytes!("../assets/content-types.xml").to_vec(),
        ),
        (
            "_rels/.rels".into(),
            include_bytes!("../assets/relationships.xml").to_vec(),
        ),
        ("3D/3dmodel.model".into(), model.into_bytes()),
        ("Metadata/model_settings.config".into(), config.into_bytes()),
        (
            "Metadata/project_settings.config".into(),
            serde_json::to_vec_pretty(&bambu_settings(p)).unwrap(),
        ),
    ])
}
pub fn instructions(p: &Project) -> String {
    format!(
        "# Relief Studio print pack\n\nLayout: {} columns × {} rows, {} pieces.\nBacking: {} mm. Raised art: {} mm. Internal clearance: {} mm.\n\n{}\n\nNotes from generation:\n{}\n",
        p.columns,
        p.rows,
        p.pieces.len(),
        p.settings.base_mm,
        p.settings.relief_mm,
        p.settings.clearance_mm,
        format_args!(
            "Logical filaments: {}.\n\n{}",
            filaments(p)
                .iter()
                .enumerate()
                .map(|(i, (label, color))| format!("{} = {label} ({color})", i + 1))
                .collect::<Vec<_>>()
                .join("; "),
            include_str!("../assets/PRINTING.md")
        ),
        p.warnings
            .iter()
            .map(|s| format!("- {s}"))
            .collect::<Vec<_>>()
            .join("\n")
    )
}
pub struct Export {
    pub pack: Vec<u8>,
    pub plates: Vec<Vec<u8>>,
}
pub fn export(p: &Project) -> Result<Export> {
    let assembly = svg(p, true, false);
    let mut png = Cursor::new(Vec::new());
    image::DynamicImage::ImageRgba8(render_svg(assembly.as_bytes(), 1200)?)
        .write_to(&mut png, image::ImageFormat::Png)
        .map_err(|e| EngineError::input(e.to_string()))?;
    let mut entries = vec![
        (
            "manifest.json".into(),
            serde_json::to_vec_pretty(&manifest(p)?).unwrap(),
        ),
        (
            "project.json".into(),
            serde_json::to_vec_pretty(&p.settings).unwrap(),
        ),
        ("artwork.svg".into(), svg(p, false, false).into_bytes()),
        ("assembly.svg".into(), assembly.into_bytes()),
        ("pieces.svg".into(), svg(p, true, true).into_bytes()),
        ("preview.png".into(), png.into_inner()),
        ("PRINTING.md".into(), instructions(p).into_bytes()),
    ];
    let mut plates = Vec::new();
    for (i, plate) in packing::plates(p).iter().enumerate() {
        let data = three_mf(p, plate)?;
        entries.push((format!("plates/plate-{:02}.3mf", i + 1), data.clone()));
        plates.push(data);
    }
    for (i, piece) in p.pieces.iter().enumerate() {
        let name = piece.tile.name();
        let folder = format!("pieces/{name}");
        entries.push((
            format!("{folder}/{name}.3mf"),
            three_mf(
                p,
                &[Placement {
                    piece: i,
                    x: 0.0,
                    y: 0.0,
                }],
            )?,
        ));
        entries.push((format!("{folder}/background.stl"), piece.base.stl()));
        entries.push((format!("{folder}/combined.stl"), piece.combined.stl()));
        if let Some(art) = &piece.artwork {
            entries.push((format!("{folder}/artwork.stl"), art.stl()));
        }
        if let Some(border) = &piece.border {
            entries.push((format!("{folder}/border.stl"), border.stl()));
        }
    }
    Ok(Export {
        pack: zip(entries)?,
        plates,
    })
}
