/*! Stable 3 mm shelf packing preserves each piece's shared material translation.
Separated previews stack fragments within their original cutting cell so even
concave contour cuts cannot overlap. Assembly coordinates remain unchanged.
Bambu placement avoids its front-left exclusion zone and is included in manifests. */
use crate::{EngineError, Result, geometry::Project};
#[derive(Clone, Copy)]
pub struct Placement {
    pub piece: usize,
    pub x: f64,
    pub y: f64,
}
pub fn separated(p: &Project) -> (Vec<Placement>, [f64; 2]) {
    let mut widths = vec![0.0f64; p.columns];
    let mut heights = vec![0.0f64; p.rows];
    let mut cell_heights = vec![0.0f64; p.columns * p.rows];
    for piece in &p.pieces {
        let c = piece.tile.column;
        let r = piece.tile.row;
        widths[c] = widths[c].max(piece.extents[0]);
        let h = &mut cell_heights[r * p.columns + c];
        if *h > 0.0 {
            *h += 3.0;
        }
        *h += piece.extents[1];
        heights[r] = heights[r].max(*h);
    }
    let mut used_heights = vec![0.0; cell_heights.len()];
    let places = p
        .pieces
        .iter()
        .enumerate()
        .map(|(i, piece)| {
            let c = piece.tile.column;
            let r = piece.tile.row;
            let cell = r * p.columns + c;
            let offset = cell_heights[cell] - used_heights[cell] - piece.extents[1];
            used_heights[cell] += piece.extents[1] + 3.0;
            Placement {
                piece: i,
                x: widths[..c].iter().sum::<f64>()
                    + 3.0 * c as f64
                    + (widths[c] - piece.extents[0]) / 2.0,
                y: heights[r + 1..].iter().sum::<f64>()
                    + 3.0 * (p.rows - r - 1) as f64
                    + (heights[r] - cell_heights[cell]) / 2.0
                    + offset,
            }
        })
        .collect();
    (
        places,
        [
            widths.iter().sum::<f64>() + 3.0 * (p.columns - 1) as f64,
            heights.iter().sum::<f64>() + 3.0 * (p.rows - 1) as f64,
        ],
    )
}
pub fn plates(p: &Project) -> Vec<Vec<Placement>> {
    let (arranged, extents) = separated(p);
    let w = p.settings.bed_width_mm;
    let h = p.settings.bed_height_mm;
    if extents[0] <= w + 1e-5 && extents[1] <= h + 1e-5 {
        return vec![arranged];
    }
    let mut plates: Vec<Vec<Placement>> = Vec::new();
    let mut shelves: Vec<Vec<[f64; 3]>> = Vec::new();
    let mut order: Vec<_> = (0..p.pieces.len()).collect();
    order.sort_by(|&a, &b| {
        p.pieces[b].extents[1]
            .total_cmp(&p.pieces[a].extents[1])
            .then(a.cmp(&b))
    });
    for index in order {
        let pw = p.pieces[index].extents[0];
        let ph = p.pieces[index].extents[1];
        let mut placed = false;
        for (plate, rows) in plates.iter_mut().zip(&mut shelves) {
            for row in rows.iter_mut() {
                if ph <= row[1] + 1e-5 && row[2] + pw <= w + 1e-5 {
                    plate.push(Placement {
                        piece: index,
                        x: row[2],
                        y: row[0],
                    });
                    row[2] += pw + 3.0;
                    placed = true;
                    break;
                }
            }
            if placed {
                break;
            }
            let last = rows.last().unwrap();
            let y = last[0] + last[1] + 3.0;
            if y + ph <= h + 1e-5 {
                rows.push([y, ph, pw + 3.0]);
                plate.push(Placement {
                    piece: index,
                    x: 0.0,
                    y,
                });
                placed = true;
                break;
            }
        }
        if !placed {
            plates.push(vec![Placement {
                piece: index,
                x: 0.0,
                y: 0.0,
            }]);
            shelves.push(vec![[0.0, ph, pw + 3.0]]);
        }
    }
    plates
}
pub fn bambu_offset(p: &Project, places: &[Placement]) -> Result<[f64; 2]> {
    let x0 = places.iter().map(|p| p.x).fold(f64::INFINITY, f64::min);
    let y0 = places.iter().map(|p| p.y).fold(f64::INFINITY, f64::min);
    let x1 = places
        .iter()
        .map(|q| q.x + p.pieces[q.piece].extents[0])
        .fold(0.0, f64::max);
    let y1 = places
        .iter()
        .map(|q| q.y + p.pieces[q.piece].extents[1])
        .fold(0.0, f64::max);
    let dx = (256.0 - x1 - x0) / 2.0;
    let dy = (256.0 - y1 - y0) / 2.0;
    for [ox, oy] in [[dx, dy], [dx.max(23.0 - x0), dy], [dx, dy.max(33.0 - y0)]] {
        if x1 + ox <= 256.0 + 1e-5
            && y1 + oy <= 256.0 + 1e-5
            && places
                .iter()
                .all(|p| p.x + ox >= 23.0 - 1e-5 || p.y + oy >= 33.0 - 1e-5)
        {
            return Ok([ox, oy]);
        }
    }
    Err(EngineError::input(
        "Arranged plate reaches the P1S front-left exclusion zone. Reduce the usable bed width to 230 mm or use smaller pieces.",
    ))
}
