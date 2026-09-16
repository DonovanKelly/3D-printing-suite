/*! Build validated, aligned material parts from the selected image and planar layout.
The base and colored solid meet at base_mm; combined meshes are boolean unions,
never overlapping shells. Mounting recesses open only through the bed-facing back. */
use crate::{
    EngineError, Result,
    artwork::{self, bounds, offset},
    layout::{self, Tile, circle, rect},
    settings::*,
    solids::{self, Mesh, extrude},
};
use manifold_csg::{CrossSection, Manifold};

pub struct Piece {
    pub tile: Tile,
    pub base: Mesh,
    pub artwork: Option<Mesh>,
    pub combined: Mesh,
    pub origin: [f64; 3],
    pub extents: [f64; 3],
}
pub struct Project {
    pub settings: Settings,
    pub vector: CrossSection,
    pub raised: CrossSection,
    pub pieces: Vec<Piece>,
    pub columns: usize,
    pub rows: usize,
    pub warnings: Vec<String>,
    pub source_hash: String,
}
fn keyholes(tile: &Tile, s: &Settings, columns: usize, rows: usize) -> Result<Vec<Manifold>> {
    let cw = s.width_mm / columns as f64;
    let left = tile.column as f64 * cw;
    let right = (tile.column + 1) as f64 * cw;
    let top = s.height_mm * (1.0 - tile.row as f64 / rows as f64);
    let bottom = top - s.height_mm / rows as f64;
    let (positions, bottom, top) = if s.shape == Shape::Contour {
        let b = bounds(&tile.shape);
        (vec![(b[0] + b[2]) / 2.0], b[1], b[3])
    } else {
        (
            vec![left + (right - left) * 0.3, left + (right - left) * 0.7],
            bottom,
            top,
        )
    };
    let support = offset(&tile.shape, -3.0);
    let mut cutters = Vec::new();
    for x in positions {
        let mut y = top - 16.0;
        let mut found = false;
        while y > bottom + 6.0 {
            let head = circle(x, y, 4.0);
            let shaft = rect(x - 2.0, y, x + 2.0, y + 7.0).union(&circle(x, y + 7.0, 2.0));
            let opening = head.union(&shaft);
            let channel = head.union(&circle(x, y + 7.0, 4.0)).hull();
            if channel.difference(&support).area() < 1e-7 {
                cutters.push(extrude(&opening, 3.2, -0.1));
                cutters.push(extrude(&channel, 1.9, 1.2));
                found = true;
                break;
            }
            y -= 2.0;
        }
        if !found {
            return Err(EngineError::input(
                "Backing is too narrow for rear keyholes. Increase the size or padding, or choose a top loop or no hanging.",
            ));
        }
    }
    Ok(cutters)
}
pub fn build(data: &[u8], s: Settings) -> Result<Project> {
    let (vector, mut notes) = artwork::trace(data, &s)?;
    let (tiles, columns, rows, outer, inner) = if s.shape == Shape::Contour {
        let (tiles, outer, inner) = layout::contour(&vector, &s)?;
        (tiles, 1, 1, outer, inner)
    } else {
        let (tiles, c, r) = layout::choose(&s)?;
        (
            tiles,
            c,
            r,
            layout::outline(&s, 0.0),
            layout::outline(&s, s.frame_width_mm),
        )
    };
    let frame = if s.frame {
        outer.difference(&inner)
    } else {
        CrossSection::empty()
    };
    let raised = vector.union(&frame);
    let curved = if s.frame
        && (s.frame_profile == FrameProfile::Beaded
            || (s.shape == Shape::Contour && s.frame_profile == FrameProfile::Rounded))
    {
        Some(solids::decorated_border(&frame, &outer, &s))
    } else if s.frame && s.frame_profile == FrameProfile::Rounded {
        Some(solids::rounded_border(&s)?)
    } else {
        None
    };
    let mut pieces = Vec::new();
    for tile in tiles {
        let mut base = extrude(&tile.shape, s.base_mm, 0.0);
        if s.hanging == Hanging::Keyholes {
            base = base.difference(&Manifold::batch_union(&keyholes(&tile, &s, columns, rows)?));
        }
        let art = extrude(&vector.intersection(&tile.shape), s.relief_mm, s.base_mm);
        let border = if let Some(ref curved) = curved {
            curved.intersection(&extrude(&tile.shape, s.frame_height_mm, s.base_mm))
        } else {
            extrude(
                &frame.intersection(&tile.shape),
                s.frame_height_mm,
                s.base_mm,
            )
        };
        let artwork = art.union(&border);
        let combined = base.union(&artwork);
        let bound = combined
            .bounding_box()
            .ok_or_else(|| EngineError::input("Generated empty geometry."))?;
        let low = bound.min();
        let origin = [low[0], low[1], 0.0];
        let extents = bound.dimensions();
        if extents[0] > s.bed_width_mm + 1e-4 || extents[1] > s.bed_height_mm + 1e-4 {
            return Err(EngineError::input(
                "Final mesh exceeds the selected build plate.",
            ));
        }
        let local = |m: &Manifold| Mesh::from_solid(&m.translate(-origin[0], -origin[1], 0.0));
        let base = local(&base)?;
        let artwork = if artwork.is_empty() {
            None
        } else {
            Some(local(&artwork)?)
        };
        let combined = local(&combined)?;
        pieces.push(Piece {
            tile,
            base,
            artwork,
            combined,
            origin,
            extents,
        });
    }
    if s.shape == Shape::Contour {
        notes.push("Width and height bound the image; padding and bezel expand outward. The backing fills enclosed image holes; the raised artwork preserves them.".into());
        if s.frame && s.frame_profile == FrameProfile::Rounded {
            notes.push("Rounded contour bezels use height bands no taller than 0.1 mm.".into());
        }
    }
    if s.layout == Layout::Puzzle && pieces.len() > 1 {
        notes.push(
            "Print a small fit pair first. Puzzle clearance is uncalibrated for your printer."
                .into(),
        );
    }
    if s.hanging != Hanging::None {
        notes.push(
            "Mounting features are experimental and not load-rated. Support every wall panel."
                .into(),
        );
    }
    if s.hanging == Hanging::Keyholes {
        notes.push(
            "Rear keyholes: 8 mm head entry, 4 mm shaft, 7 mm slide. Inspect bridging/supports."
                .into(),
        );
    }
    notes.push(
        "Check brim, prime tower, exclusion zones, and filament assignments in Bambu Studio."
            .into(),
    );
    use sha2::{Digest, Sha256};
    let source_hash = format!("{:x}", Sha256::digest(data));
    Ok(Project {
        settings: s,
        vector,
        raised,
        pieces,
        columns,
        rows,
        warnings: notes,
        source_hash,
    })
}
