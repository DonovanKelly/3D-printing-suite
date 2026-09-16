/*! Closed-solid fabrication and independent triangle validation. Meshes exported to
slicers have welded vertices, paired opposite edges, and positive signed volume. */
use crate::{
    EngineError, Result,
    artwork::{offset, signed_area},
    layout::corner_loop,
    settings::*,
};
use manifold_csg::{CrossSection, Manifold};
use std::collections::HashMap;

#[derive(Clone, serde::Serialize)]
pub struct Mesh {
    pub vertices: Vec<f64>,
    pub faces: Vec<u32>,
}
impl Mesh {
    pub fn from_solid(solid: &Manifold) -> Result<Self> {
        solid.status().map_err(|e| {
            EngineError::input(format!(
                "Generated geometry is not a closed positive-volume solid: {e}"
            ))
        })?;
        // STL stores float32 coordinates. Validate that representation before
        // any preview/export so slicer welding cannot collapse hidden seam faces.
        let (vertices, _, faces) = solid.simplify(1e-5).to_mesh_f32();
        let mesh = Self::weld(
            vertices.into_iter().map(f64::from).collect(),
            faces.into_iter().map(u64::from).collect(),
        );
        mesh.validate()?;
        Ok(mesh)
    }
    fn weld(vertices: Vec<f64>, faces: Vec<u64>) -> Self {
        let mut map = HashMap::new();
        let mut merged = Vec::new();
        let mut ids = Vec::new();
        for p in vertices.as_chunks::<3>().0.iter() {
            let key = [
                (p[0] * 1e7).round() as i64,
                (p[1] * 1e7).round() as i64,
                (p[2] * 1e7).round() as i64,
            ];
            let id = *map.entry(key).or_insert_with(|| {
                let id = (merged.len() / 3) as u32;
                merged.extend_from_slice(p);
                id
            });
            ids.push(id);
        }
        let faces = faces
            .as_chunks::<3>()
            .0
            .iter()
            .flat_map(|f| {
                let a = ids[f[0] as usize];
                let b = ids[f[1] as usize];
                let c = ids[f[2] as usize];
                if a != b && b != c && c != a {
                    vec![a, b, c]
                } else {
                    vec![]
                }
            })
            .collect();
        Self {
            vertices: merged,
            faces,
        }
    }
    pub fn volume(&self) -> f64 {
        self.faces
            .as_chunks::<3>()
            .0
            .iter()
            .map(|f| {
                let a = self.point(f[0]);
                let b = self.point(f[1]);
                let c = self.point(f[2]);
                a[0] * (b[1] * c[2] - b[2] * c[1])
                    + a[1] * (b[2] * c[0] - b[0] * c[2])
                    + a[2] * (b[0] * c[1] - b[1] * c[0])
            })
            .sum::<f64>()
            / 6.0
    }
    pub fn point(&self, i: u32) -> [f64; 3] {
        let k = i as usize * 3;
        [self.vertices[k], self.vertices[k + 1], self.vertices[k + 2]]
    }
    pub fn validate(&self) -> Result<()> {
        let mut edges: HashMap<(u32, u32), (u32, i32)> = HashMap::new();
        for f in self.faces.as_chunks::<3>().0.iter() {
            for (a, b) in [(f[0], f[1]), (f[1], f[2]), (f[2], f[0])] {
                let (key, sign) = if a < b { ((a, b), 1) } else { ((b, a), -1) };
                let e = edges.entry(key).or_default();
                e.0 += 1;
                e.1 += sign;
            }
        }
        if !self.vertices.iter().all(|v| v.is_finite())
            || self.volume() <= 0.0
            || edges.values().any(|&(n, w)| n != 2 || w != 0)
        {
            return Err(EngineError::input(
                "Generated geometry is not a closed positive-volume solid. Try simplifying the artwork or increasing the piece size.",
            ));
        }
        Ok(())
    }
    pub fn stl(&self) -> Vec<u8> {
        let mut bytes = vec![0; 80];
        bytes[..17].copy_from_slice(b"Relief Studio mm ");
        bytes.extend_from_slice(&((self.faces.len() / 3) as u32).to_le_bytes());
        for face in self.faces.as_chunks::<3>().0.iter() {
            let a = self.point(face[0]);
            let b = self.point(face[1]);
            let c = self.point(face[2]);
            let u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
            let v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
            let n = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ];
            let length = n.iter().map(|x| x * x).sum::<f64>().sqrt();
            for value in n.map(|x| x / length).into_iter().chain(a).chain(b).chain(c) {
                bytes.extend_from_slice(&(value as f32).to_le_bytes());
            }
            bytes.extend_from_slice(&0u16.to_le_bytes());
        }
        bytes
    }
}
pub fn extrude(region: &CrossSection, height: f64, z: f64) -> Manifold {
    if region.is_empty() {
        Manifold::empty()
    } else {
        region.extrude(height).translate(0.0, 0.0, z)
    }
}
fn from_loft(vertices: Vec<f64>, faces: Vec<u64>) -> Result<Manifold> {
    let mesh = Mesh::weld(vertices, faces);
    Manifold::from_mesh_f64(
        &mesh.vertices,
        3,
        &mesh.faces.iter().map(|&i| i as u64).collect::<Vec<_>>(),
    )
    .map_err(|e| EngineError::input(format!("Could not construct border: {e}")))
}
pub fn rounded_border(s: &Settings) -> Result<Manifold> {
    let height = s.frame_height_mm;
    let width = s.frame_width_mm;
    let roll = (height / 2.0).min(width * 0.45);
    let mut levels = vec![(0.0, 0.0), (height - roll, 0.0)];
    levels.extend((1..=12).map(|i| {
        let angle = i as f64 / 12.0 * std::f64::consts::FRAC_PI_2;
        (
            height - roll + roll * angle.sin(),
            roll * (1.0 - angle.cos()),
        )
    }));
    let count = corner_loop(s, 0.0).len();
    let mut vertices = Vec::new();
    for &(z, inset) in &levels {
        for offset in [inset, width - inset] {
            for p in corner_loop(s, offset) {
                vertices.extend([p[0], p[1], z + s.base_mm]);
            }
        }
    }
    let mut faces = Vec::new();
    let mut connect = |a: usize, b: usize, reverse: bool| {
        for k in 0..count {
            let n = (k + 1) % count;
            for mut face in [[a + k, a + n, b + n], [a + k, b + n, b + k]] {
                if reverse {
                    face.reverse();
                }
                faces.extend(face.map(|v| v as u64));
            }
        }
    };
    for i in 0..levels.len() - 1 {
        let a = i * 2 * count;
        let b = (i + 1) * 2 * count;
        connect(a, b, false);
        connect(a + count, b + count, true);
    }
    connect(0, count, true);
    let start = (levels.len() - 1) * 2 * count;
    connect(start, start + count, false);
    from_loft(vertices, faces)
}
pub fn decorated_border(frame: &CrossSection, outer: &CrossSection, s: &Settings) -> Manifold {
    let height = s.frame_height_mm;
    let width = s.frame_width_mm;
    let z = s.base_mm;
    if s.frame_profile == FrameProfile::Rounded {
        let roll = (height / 2.0).min(width * 0.45);
        let shoulder = height - roll;
        let count = 12usize.max((roll / 0.1).ceil() as usize);
        let mut solids = vec![extrude(frame, shoulder, z)];
        for i in 0..count {
            let t = (i as f64 + 0.5) / count as f64;
            let inset = roll * (1.0 - (1.0 - t * t).sqrt());
            let section = offset(frame, -inset);
            if !section.is_empty() {
                solids.push(extrude(
                    &section,
                    shoulder + roll * (i + 1) as f64 / count as f64,
                    z,
                ));
            }
        }
        return Manifold::batch_union(&solids);
    }
    let radius = (width * 0.35).min(3.0);
    let stem = height * 0.4;
    let center_z = height * 0.3;
    let mut solids = vec![extrude(frame, stem, z)];
    let rings: Vec<_> = offset(outer, -width / 2.0)
        .to_polygons()
        .into_iter()
        .filter(|r| signed_area(r) > 0.0)
        .collect();
    let length = |r: &Vec<[f64; 2]>| {
        r.iter()
            .zip(r.iter().cycle().skip(1))
            .take(r.len())
            .map(|(a, b)| (a[0] - b[0]).hypot(a[1] - b[1]))
            .sum::<f64>()
    };
    let pitch = (radius * 2.6).max(rings.iter().map(length).sum::<f64>() / 500.0);
    let sphere = Manifold::sphere(1.0, 24);
    for ring in rings {
        let len = length(&ring);
        let count = (len / pitch) as usize;
        let count = count.max(1);
        for i in 0..count {
            let mut distance = (i as f64 + 0.5) * len / count as f64;
            for (a, b) in ring
                .iter()
                .zip(ring.iter().cycle().skip(1))
                .take(ring.len())
            {
                let span = (a[0] - b[0]).hypot(a[1] - b[1]);
                if distance <= span {
                    let t = distance / span;
                    solids.push(sphere.scale(radius, radius, height - center_z).translate(
                        a[0] + (b[0] - a[0]) * t,
                        a[1] + (b[1] - a[1]) * t,
                        z + center_z,
                    ));
                    break;
                }
                distance -= span;
            }
        }
    }
    Manifold::batch_union(&solids).intersection(&extrude(frame, height, z))
}
