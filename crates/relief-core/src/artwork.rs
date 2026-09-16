/*! Decode bounded local images and trace foreground rings, preserving shell/hole roles.
SVG is rasterized with no resource resolver or script engine. Pixel y is reflected
once into model coordinates; offsets and all later operations use millimeters. */
use crate::{EngineError, Result, settings::*};
use image::{DynamicImage, GrayImage, ImageDecoder, ImageReader, RgbaImage};
use imageproc::contours::{BorderType, find_contours};
use manifold_csg::{CrossSection, FillRule, JoinType};
use std::io::Cursor;

pub const MAX_INPUT_BYTES: usize = 12 * 1024 * 1024;
pub const SAMPLE: &[u8] = include_bytes!("../../../src/relief_studio/assets/alpine.svg");

pub fn region(rings: &[Vec<[f64; 2]>]) -> CrossSection {
    CrossSection::from_polygons_with_fill_rule(rings, FillRule::EvenOdd)
}
pub fn offset(shape: &CrossSection, distance: f64) -> CrossSection {
    shape.offset(distance, JoinType::Round, 2.0, 96)
}
pub fn bounds(shape: &CrossSection) -> [f64; 4] {
    let r = shape.bounds_rect2();
    [r.min_x, r.min_y, r.max_x, r.max_y]
}
pub fn signed_area(ring: &[[f64; 2]]) -> f64 {
    ring.iter()
        .zip(ring.iter().cycle().skip(1))
        .take(ring.len())
        .map(|(a, b)| a[0] * b[1] - a[1] * b[0])
        .sum::<f64>()
        / 2.0
}
pub fn silhouette(shape: &CrossSection) -> CrossSection {
    CrossSection::batch_union(
        &shape
            .to_polygons()
            .into_iter()
            .filter(|ring| signed_area(ring) > 0.0)
            .map(|ring| region(&[ring]))
            .collect::<Vec<_>>(),
    )
}
fn dimensions(width: u32, height: u32) -> Result<()> {
    if width == 0 || height == 0 || width as u64 * height as u64 > 24_000_000 {
        return Err(EngineError::input(
            "Image exceeds the 24 megapixel limit; resize it first.",
        ));
    }
    if !(0.02..=50.0).contains(&(width as f64 / height as f64)) {
        return Err(EngineError::input(
            "Image aspect ratio must be between 1:50 and 50:1.",
        ));
    }
    Ok(())
}
pub fn svg_tree(data: &[u8]) -> Result<resvg::usvg::Tree> {
    let text =
        std::str::from_utf8(data).map_err(|_| EngineError::input("Could not read this SVG."))?;
    let document = roxmltree::Document::parse(text).map_err(|_| {
        EngineError::input("Could not read this SVG. DTDs and entities are unsupported.")
    })?;
    if document.root_element().tag_name().name() != "svg" {
        return Err(EngineError::input("The document must have an SVG root."));
    }
    let root = document.root_element();
    let size = if let Some(viewbox) = root.attribute("viewBox") {
        let values: Vec<_> = viewbox
            .split(|c: char| c.is_whitespace() || c == ',')
            .filter(|s| !s.is_empty())
            .map(str::parse::<f64>)
            .collect();
        if values.len() != 4 || values.iter().any(|v| v.is_err()) {
            return Err(EngineError::input("SVG needs a valid viewBox."));
        }
        [*values[2].as_ref().unwrap(), *values[3].as_ref().unwrap()]
    } else {
        let dimension = |name| -> Result<f64> {
            let value = root.attribute(name).unwrap_or("");
            let numeric = value.trim_end_matches(|c: char| c.is_ascii_alphabetic());
            let suffix = &value[numeric.len()..];
            if !["", "px", "mm", "cm", "in", "pt", "pc"].contains(&suffix) {
                return Err(EngineError::input(
                    "SVG needs a viewBox or explicit width and height.",
                ));
            }
            numeric.parse().map_err(|_| {
                EngineError::input("SVG needs a viewBox or explicit width and height.")
            })
        };
        [dimension("width")?, dimension("height")?]
    };
    if size.iter().any(|v| !v.is_finite() || *v <= 0.0) {
        return Err(EngineError::input(
            "SVG dimensions must be finite and positive.",
        ));
    }
    if !(0.02..=50.0).contains(&(size[0] / size[1])) {
        return Err(EngineError::input(
            "Image aspect ratio must be between 1:50 and 50:1.",
        ));
    }
    if document.descendants().filter(|n| n.is_element()).count() > 10_000 {
        return Err(EngineError::input(
            "SVG is too complex; flatten or simplify it first.",
        ));
    }
    if text.to_lowercase().contains("@import") {
        return Err(EngineError::input(
            "SVG stylesheet imports are not supported.",
        ));
    }
    for node in document.descendants().filter(|n| n.is_element()) {
        if ["script", "foreignObject", "image"].contains(&node.tag_name().name()) {
            return Err(EngineError::input(
                "SVG scripts, embedded images, and foreign objects are unsupported.",
            ));
        }
        for attr in node.attributes() {
            if attr.name() == "href" && !attr.value().starts_with('#') {
                return Err(EngineError::input(
                    "SVG links must reference a shape inside the same file.",
                ));
            }
        }
    }
    // No external URL is resolved, including styles that a renderer might otherwise ignore.
    let lower = text.to_lowercase();
    for rest in lower.split("url(").skip(1) {
        if !rest
            .trim_start()
            .trim_start_matches(['\'', '"'])
            .starts_with('#')
        {
            return Err(EngineError::input(
                "SVG must be self-contained; linked resources are not supported.",
            ));
        }
    }
    let mut options = resvg::usvg::Options {
        resources_dir: None,
        font_family: "DejaVu Sans".into(),
        ..Default::default()
    };
    options
        .fontdb_mut()
        .load_font_data(include_bytes!("../assets/DejaVuSans.ttf").to_vec());
    options.fontdb_mut().set_sans_serif_family("DejaVu Sans");
    options.fontdb_mut().set_serif_family("DejaVu Sans");
    options.fontdb_mut().set_monospace_family("DejaVu Sans");
    let tree = resvg::usvg::Tree::from_data(data, &options)
        .map_err(|e| EngineError::input(format!("Could not read this SVG: {e}")))?;
    let ratio = tree.size().width() / tree.size().height();
    if !(0.02..=50.0).contains(&ratio) {
        return Err(EngineError::input(
            "Image aspect ratio must be between 1:50 and 50:1.",
        ));
    }
    Ok(tree)
}
pub fn render_svg(data: &[u8], resolution: u32) -> Result<RgbaImage> {
    let tree = svg_tree(data)?;
    let size = tree.size();
    let scale = resolution as f32 / size.width().max(size.height());
    let w = (size.width() * scale).round().max(2.0) as u32;
    let h = (size.height() * scale).round().max(2.0) as u32;
    let mut pixmap = resvg::tiny_skia::Pixmap::new(w, h)
        .ok_or_else(|| EngineError::input("Image is too large."))?;
    resvg::render(
        &tree,
        resvg::tiny_skia::Transform::from_scale(w as f32 / size.width(), h as f32 / size.height()),
        &mut pixmap.as_mut(),
    );
    let mut rgba = RgbaImage::new(w, h);
    for (pixel, source) in rgba.pixels_mut().zip(pixmap.pixels()) {
        let c = source.demultiply();
        *pixel = image::Rgba([c.red(), c.green(), c.blue(), c.alpha()]);
    }
    Ok(rgba)
}
pub fn load_image(data: &[u8], s: &Settings) -> Result<(RgbaImage, bool)> {
    if data.is_empty() || data.len() > MAX_INPUT_BYTES {
        return Err(EngineError::input(
            "Choose an image or SVG smaller than 12 MiB.",
        ));
    }
    let is_svg = String::from_utf8_lossy(&data[..data.len().min(2048)])
        .to_lowercase()
        .contains("<svg");
    if is_svg {
        return Ok((render_svg(data, s.trace_resolution())?, true));
    }
    let bad = || {
        EngineError::input(
            "Could not read this image. Use a PNG, JPEG, WebP, or self-contained SVG.",
        )
    };
    let reader = ImageReader::new(Cursor::new(data))
        .with_guessed_format()
        .map_err(|_| bad())?;
    let mut decoder = reader.into_decoder().map_err(|_| bad())?;
    let (w, h) = decoder.dimensions();
    dimensions(w, h)?;
    let orientation = decoder.orientation().map_err(|_| bad())?;
    let mut image = DynamicImage::from_decoder(decoder).map_err(|_| bad())?;
    image.apply_orientation(orientation);
    let image = if image.width().max(image.height()) > s.trace_resolution() {
        image.resize(
            s.trace_resolution(),
            s.trace_resolution(),
            image::imageops::FilterType::Lanczos3,
        )
    } else {
        image
    };
    Ok((image.to_rgba8(), false))
}
pub fn trace(data: &[u8], s: &Settings) -> Result<(CrossSection, Vec<String>)> {
    let (rgba, is_svg) = load_image(data, s)?;
    let (w, h) = rgba.dimensions();
    let mut strength = vec![0f64; (w * h) as usize];
    let auto = is_svg && s.foreground == Foreground::Auto;
    if auto {
        let transparent = (1..h.saturating_sub(1))
            .any(|y| (1..w.saturating_sub(1)).any(|x| rgba.get_pixel(x, y)[3] < 255));
        if transparent || w <= 2 || h <= 2 {
            for (v, p) in strength.iter_mut().zip(rgba.pixels()) {
                *v = p[3] as f64;
            }
        } else {
            let mut edge = [Vec::new(), Vec::new(), Vec::new()];
            for (x, y) in (1..w - 1)
                .flat_map(|x| [(x, 1), (x, h - 2)])
                .chain((1..h - 1).flat_map(|y| [(1, y), (w - 2, y)]))
            {
                for (k, channel) in edge.iter_mut().enumerate() {
                    channel.push(rgba.get_pixel(x, y)[k]);
                }
            }
            let background: Vec<f64> = edge
                .iter_mut()
                .map(|e| {
                    e.sort_unstable();
                    (e[e.len() / 2] as f64 + e[(e.len() - 1) / 2] as f64) / 2.0
                })
                .collect();
            for (v, p) in strength.iter_mut().zip(rgba.pixels()) {
                *v = if p[3] < 255 {
                    0.0
                } else {
                    (0..3)
                        .map(|k| (p[k] as f64 - background[k]).abs())
                        .fold(0.0, f64::max)
                };
            }
        }
        let max = strength.iter().copied().fold(0.0, f64::max);
        for v in &mut strength {
            *v = if max == 0.0 {
                255.0
            } else {
                (255.0 - *v * 255.0 / max).floor()
            };
        }
    } else {
        let background = if s.foreground == Foreground::Light {
            0.0
        } else {
            255.0
        };
        for (v, p) in strength.iter_mut().zip(rgba.pixels()) {
            let rgb: Vec<f64> = (0..3)
                .map(|k| {
                    (p[k] as f64 * p[3] as f64 / 255.0 + background * (1.0 - p[3] as f64 / 255.0))
                        .round()
                })
                .collect();
            *v = (rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114).round();
        }
    }
    // Suzuki tracing needs a zero-valued perimeter even when the selected image reaches its edge.
    let mut mask = GrayImage::new(w + 2, h + 2);
    for y in 0..h {
        for x in 0..w {
            let mut selected = strength[(y * w + x) as usize] <= s.threshold as f64;
            if s.foreground == Foreground::Light {
                selected = !selected;
            }
            if s.invert {
                selected = !selected;
            }
            mask.put_pixel(x + 1, y + 1, image::Luma([if selected { 255 } else { 0 }]));
        }
    }
    let contours = find_contours::<i32>(&mask);
    if contours.is_empty() {
        let mode = match s.foreground {
            Foreground::Auto => "Automatic",
            Foreground::Dark => "Dark pixels",
            Foreground::Light => "Light pixels",
        };
        return Err(EngineError::selection(format!(
            "No artwork remains with {mode} at threshold {}. Use Reset image selection, adjust the threshold, or choose an image with visible shapes.",
            s.threshold
        )));
    }
    if contours.len() > 5000 {
        return Err(EngineError::input(
            "Too many small regions. Simplify the image or use a lower detail setting.",
        ));
    }
    let mut parts = Vec::new();
    for (i, contour) in contours.iter().enumerate() {
        if contour.border_type != BorderType::Outer || contour.points.len() < 3 {
            continue;
        }
        let ring = |c: &imageproc::contours::Contour<i32>| {
            c.points
                .iter()
                .map(|p| [(p.x - 1) as f64, (p.y - 1) as f64])
                .collect::<Vec<_>>()
        };
        let shell = region(&[ring(contour)]);
        let holes: Vec<_> = contours
            .iter()
            .filter(|c| {
                c.parent == Some(i) && c.border_type == BorderType::Hole && c.points.len() >= 3
            })
            .map(|c| region(&[ring(c)]))
            .collect();
        parts.push(shell.difference(&CrossSection::batch_union(&holes)));
    }
    let shape = CrossSection::batch_union(&parts);
    if shape.is_empty() {
        return Err(EngineError::selection(
            "Artwork is too thin to trace. Increase its resolution or line weight.",
        ));
    }
    let [x0, y0, x1, y1] = if s.crop_to_artwork || s.shape == Shape::Contour {
        bounds(&shape)
    } else {
        [0.0, 0.0, w as f64, h as f64]
    };
    let scale = ((s.width_mm - 2.0 * s.artwork_inset()) / (x1 - x0))
        .min((s.height_mm - 2.0 * s.artwork_inset()) / (y1 - y0));
    let shape = shape
        .scale(scale, -scale)
        .translate(
            s.width_mm / 2.0 - (x0 + x1) * scale / 2.0,
            s.height_mm / 2.0 + (y0 + y1) * scale / 2.0,
        )
        .simplify(s.simplify_mm());
    let parts = shape.decompose();
    let kept: Vec<_> = parts
        .iter()
        .filter(|p| p.area() >= s.min_area_mm2)
        .cloned()
        .collect();
    if kept.is_empty() {
        return Err(EngineError::selection(
            "All artwork was smaller than the minimum area. Reset image selection or reduce filtering.",
        ));
    }
    let mut notes = Vec::new();
    if kept.len() != parts.len() {
        notes.push(format!(
            "Removed {} tiny artwork regions below the area filter.",
            parts.len() - kept.len()
        ));
    }
    let shape = CrossSection::batch_union(&kept).offset(-0.01, JoinType::Miter, 2.0, 96);
    if shape.is_empty() {
        return Err(EngineError::selection(
            "Artwork is too thin after contact cleanup. Increase its line weight.",
        ));
    }
    if shape.difference(&offset(&offset(&shape, -0.2), 0.2)).area() > (shape.area() * 0.03).max(1.0)
    {
        notes.push(
            "Some fine features may be narrower than a 0.4 mm nozzle; inspect the sliced preview."
                .into(),
        );
    }
    Ok((shape, notes))
}
