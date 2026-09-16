/*! Complementary partitions transfer each seam exactly once between neighboring cells.
Clearance removes internal seams only; original outer dimensions remain exact.
Fit checks use actual polygons including tabs, rounded corners, and hanging loops. */
use crate::{
    EngineError, Result,
    artwork::{bounds, offset, region, silhouette},
    random::PythonRandom,
    settings::*,
};
use manifold_csg::CrossSection;
use std::f64::consts::PI;

pub struct Tile {
    pub row: usize,
    pub column: usize,
    pub shape: CrossSection,
}
impl Tile {
    pub fn name(&self) -> String {
        format!("r{:02}-c{:02}", self.row + 1, self.column + 1)
    }
}
pub fn rect(x0: f64, y0: f64, x1: f64, y1: f64) -> CrossSection {
    CrossSection::square(x1 - x0, y1 - y0, false).translate(x0, y0)
}
pub fn circle(x: f64, y: f64, r: f64) -> CrossSection {
    CrossSection::circle(r, 96).translate(x, y)
}
pub fn corner_loop(s: &Settings, inset: f64) -> Vec<[f64; 2]> {
    let r = (s.corner_radius_mm - inset).max(0.0);
    let centers = [
        [s.width_mm - inset - r, inset + r],
        [s.width_mm - inset - r, s.height_mm - inset - r],
        [inset + r, s.height_mm - inset - r],
        [inset + r, inset + r],
    ];
    centers
        .iter()
        .enumerate()
        .flat_map(|(i, c)| {
            (0..17).map(move |j| {
                let a = ((i as f64 - 1.0) + j as f64 / 16.0) * PI / 2.0;
                [c[0] + r * a.cos(), c[1] + r * a.sin()]
            })
        })
        .collect()
}
pub fn outline(s: &Settings, inset: f64) -> CrossSection {
    region(&[corner_loop(s, inset)])
}
pub fn add_loop(shape: &CrossSection, left: f64, right: f64) -> Result<CrossSection> {
    let x = (left + right) / 2.0;
    let mut top = f64::NEG_INFINITY;
    for ring in shape.to_polygons() {
        for (a, b) in ring
            .iter()
            .zip(ring.iter().cycle().skip(1))
            .take(ring.len())
        {
            if (a[0] - x).abs() < 1e-8 {
                top = top.max(a[1]);
            }
            if (a[0] < x && b[0] > x) || (a[0] > x && b[0] < x) {
                top = top.max(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]));
            }
        }
    }
    if !top.is_finite() {
        return Err(EngineError::input(
            "No backing supports the top loop. Reduce corner radius or use larger pieces.",
        ));
    }
    Ok(shape
        .union(&circle(x, top + 3.0, 6.0))
        .difference(&circle(x, top + 3.0, 2.5)))
}
pub fn partition(s: &Settings, columns: usize, rows: usize) -> Result<Vec<Tile>> {
    let cw = s.width_mm / columns as f64;
    let ch = s.height_mm / rows as f64;
    if cw.min(ch) < 24.0 {
        return Err(EngineError::input(
            "Each grid cell must be at least 24 mm wide and tall.",
        ));
    }
    let mut cells: Vec<_> = (0..rows)
        .flat_map(|r| {
            (0..columns).map(move |c| {
                rect(
                    c as f64 * cw,
                    r as f64 * ch,
                    (c + 1) as f64 * cw,
                    (r + 1) as f64 * ch,
                )
            })
        })
        .collect();
    if s.layout == Layout::Puzzle {
        let radius = cw.min(ch) * 0.09;
        let mut rng = PythonRandom::new(s.puzzle_seed);
        let mut seam =
            |a: usize, b: usize, x: f64, y: f64, length: f64, vertical: bool, sign: f64| {
                let random = s.puzzle_style == PuzzleStyle::Random;
                let direction = if random { rng.sign() } else { sign };
                let position = if random { rng.uniform(0.35, 0.65) } else { 0.5 };
                let size = radius * if random { rng.uniform(0.8, 1.1) } else { 1.0 };
                let bow = if random {
                    rng.uniform(-0.04, 0.04) * cw.min(ch)
                } else {
                    0.0
                };
                let point = |t: f64, offset: f64| {
                    let lateral = bow * (PI * t).sin() + offset;
                    if vertical {
                        [x + lateral, y + length * t]
                    } else {
                        [x + length * t, y + lateral]
                    }
                };
                if bow != 0.0 {
                    let strip = region(&[(0..=24).map(|i| point(i as f64 / 24.0, 0.0)).collect()]);
                    let (owner, neighbor) = if bow > 0.0 { (a, b) } else { (b, a) };
                    cells[owner] = cells[owner].union(&strip);
                    cells[neighbor] = cells[neighbor].difference(&strip);
                }
                let p = point(position, direction * size * 0.8);
                let tab = circle(p[0], p[1], size);
                let (owner, neighbor) = if direction == 1.0 { (a, b) } else { (b, a) };
                cells[owner] = cells[owner].union(&tab);
                cells[neighbor] = cells[neighbor].difference(&tab);
            };
        for r in 0..rows {
            for c in 0..columns - 1 {
                seam(
                    r * columns + c,
                    r * columns + c + 1,
                    (c + 1) as f64 * cw,
                    r as f64 * ch,
                    ch,
                    true,
                    if (r + c) % 2 == 0 { 1.0 } else { -1.0 },
                );
            }
        }
        for r in 0..rows - 1 {
            for c in 0..columns {
                seam(
                    r * columns + c,
                    (r + 1) * columns + c,
                    c as f64 * cw,
                    (r + 1) as f64 * ch,
                    cw,
                    false,
                    if (r + c) % 2 == 1 { 1.0 } else { -1.0 },
                );
            }
        }
    }
    let footprint = outline(s, 0.0);
    let mut tiles = Vec::new();
    for r in 0..rows {
        for c in 0..columns {
            let mut shape = cells[r * columns + c].clone();
            if s.clearance_mm > 0.0 && cells.len() > 1 {
                let half = s.clearance_mm / 2.0;
                let mut cuts = Vec::new();
                for ring in shape.to_polygons() {
                    for (a, b) in ring
                        .iter()
                        .zip(ring.iter().cycle().skip(1))
                        .take(ring.len())
                    {
                        let outer = (a[0].abs() < 1e-7 && b[0].abs() < 1e-7)
                            || ((a[0] - s.width_mm).abs() < 1e-7
                                && (b[0] - s.width_mm).abs() < 1e-7)
                            || (a[1].abs() < 1e-7 && b[1].abs() < 1e-7)
                            || ((a[1] - s.height_mm).abs() < 1e-7
                                && (b[1] - s.height_mm).abs() < 1e-7);
                        if !outer {
                            cuts.push(
                                circle(a[0], a[1], half)
                                    .union(&circle(b[0], b[1], half))
                                    .hull(),
                            );
                        }
                    }
                }
                shape = shape.difference(&CrossSection::batch_union(&cuts));
            }
            shape = shape.intersection(&footprint);
            if s.hanging == Hanging::Loops && r == rows - 1 {
                shape = add_loop(&shape, c as f64 * cw, (c + 1) as f64 * cw)?;
            }
            if shape.is_empty() || shape.decompose().len() != 1 {
                return Err(EngineError::input(
                    "Layout disconnected a piece. Reduce clearance or use larger pieces.",
                ));
            }
            tiles.push(Tile {
                row: rows - r - 1,
                column: c,
                shape,
            });
        }
    }
    tiles.sort_by_key(|t| (t.row, t.column));
    Ok(tiles)
}
pub fn fits(tiles: &[Tile], s: &Settings, size_limit: bool) -> bool {
    let w = if size_limit {
        s.bed_width_mm.min(s.piece_size_mm)
    } else {
        s.bed_width_mm
    };
    let h = if size_limit {
        s.bed_height_mm.min(s.piece_size_mm)
    } else {
        s.bed_height_mm
    };
    tiles.iter().all(|t| {
        let [x0, y0, x1, y1] = bounds(&t.shape);
        x1 - x0 <= w + 1e-6 && y1 - y0 <= h + 1e-6
    })
}
pub fn choose(s: &Settings) -> Result<(Vec<Tile>, usize, usize)> {
    if s.layout == Layout::Plaque || s.columns > 0 {
        let c = s.columns.max(1) as usize;
        let r = s.rows.max(1) as usize;
        let tiles = partition(s, c, r)?;
        if !fits(&tiles, s, false) {
            return Err(EngineError::input(
                "A piece exceeds the usable build plate. Choose automatic Tiles/Puzzle or increase the grid count; tabs and loops also need room.",
            ));
        }
        return Ok((tiles, c, r));
    }
    let size = s.split_mode == SplitMode::Size;
    let w = if size {
        s.bed_width_mm.min(s.piece_size_mm)
    } else {
        s.bed_width_mm
    };
    let h = if size {
        s.bed_height_mm.min(s.piece_size_mm)
    } else {
        s.bed_height_mm
    };
    let mut candidates: Vec<_> = ((s.width_mm / w).ceil() as usize..=12)
        .flat_map(|c| ((s.height_mm / h).ceil() as usize..=12).map(move |r| (c, r)))
        .filter(|&(c, r)| {
            (2..=64).contains(&(c * r))
                && (s.width_mm / c as f64).min(s.height_mm / r as f64) >= 24.0
        })
        .collect();
    candidates.sort_by(|&(c, r), &(c2, r2)| {
        (c * r).cmp(&(c2 * r2)).then_with(|| {
            (s.width_mm / c as f64 - s.height_mm / r as f64)
                .abs()
                .total_cmp(&(s.width_mm / c2 as f64 - s.height_mm / r2 as f64).abs())
        })
    });
    for (c, r) in candidates {
        let tiles = partition(s, c, r)?;
        if fits(&tiles, s, size) {
            return Ok((tiles, c, r));
        }
    }
    Err(EngineError::input(
        "No split fits the piece size and build plate within 64 pieces (minimum cell 24 mm). Increase Max piece size, use Largest panels, or adjust the finished dimensions.",
    ))
}
pub fn contour(
    vector: &CrossSection,
    s: &Settings,
) -> Result<(Vec<Tile>, CrossSection, CrossSection)> {
    let silhouette = silhouette(vector);
    let inner = crate::artwork::silhouette(&offset(&silhouette, s.margin_mm));
    let outer = crate::artwork::silhouette(&offset(
        &silhouette,
        s.margin_mm + if s.frame { s.frame_width_mm } else { 0.0 },
    ));
    if outer.decompose().len() != 1 {
        return Err(EngineError::input(
            "Image contour has disconnected islands. Increase Padding or Border width to join them, or choose Rectangle.",
        ));
    }
    let shape = if s.hanging == Hanging::Loops {
        let b = bounds(&outer);
        add_loop(&outer, b[0], b[2])?
    } else {
        outer.clone()
    };
    if shape.decompose().len() != 1 {
        return Err(EngineError::input(
            "The top loop is unsupported. Increase Padding or choose no hanging.",
        ));
    }
    let tiles = vec![Tile {
        row: 0,
        column: 0,
        shape,
    }];
    if !fits(&tiles, s, false) {
        return Err(EngineError::input(
            "Image contour exceeds the usable build plate, including its bezel and loop. Reduce Width or Height, or remove the top loop.",
        ));
    }
    Ok((tiles, outer, inner))
}
