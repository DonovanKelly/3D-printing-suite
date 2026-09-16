/*! Regress selection, resource bounds, complementary seams, mounting, and recovery
at the shared native/Wasm API rather than through UI-only validation. */
use relief_core::{artwork, geometry, layout, settings::Settings};
use serde_json::{Value, json};
fn settings(value: Value) -> Settings {
    Settings::parse(&value.to_string()).unwrap()
}
const GOLD: &[u8] = include_bytes!("../../../tests/fixtures/gold-cutout.svg");
const ICON: &[u8] = include_bytes!("../../../tests/fixtures/contour-icon.svg");
fn covers(shape: &manifold_csg::CrossSection, x: f64, y: f64) -> bool {
    shape.intersection(&layout::circle(x, y, 0.01)).area() > 0.0001
}
#[test]
fn svg_color_opacity_contrast_and_manual_boundaries() {
    let base = json!({"detail":"draft","crop_to_artwork":false,"frame":false,"margin_mm":0,"width_mm":100,"height_mm":140});
    for color in ["#000000", "#ffffff", "#958714", "#fefefe", "#808080"] {
        for opacity in [1.0, 0.2, 0.01] {
            for threshold in [1, 128, 254] {
                let svg = String::from_utf8_lossy(GOLD)
                    .replace("#958714", color)
                    .replace("<path ", &format!("<path opacity=\"{opacity}\" "));
                let mut values = base.clone();
                values["threshold"] = json!(threshold);
                let traced = artwork::trace(svg.as_bytes(), &settings(values)).unwrap();
                let shape = traced.relief();
                assert!(covers(shape, 12.0, 70.0));
                assert!(!covers(shape, 30.0, 70.0));
                assert!(covers(shape, 50.0, 70.0));
            }
        }
    }
    for (fill, background) in [
        ("#fefefe", "#ffffff"),
        ("#141414", "#121212"),
        ("#958714", "#978916"),
    ] {
        for threshold in [1, 128, 254] {
            let svg = String::from_utf8_lossy(GOLD)
                .replace("#958714", fill)
                .replace(
                    "<path ",
                    &format!("<rect width=\"100\" height=\"140\" fill=\"{background}\"/><path "),
                );
            let mut values = base.clone();
            values["threshold"] = json!(threshold);
            let traced = artwork::trace(svg.as_bytes(), &settings(values)).unwrap();
            let shape = traced.relief();
            assert!(covers(shape, 12.0, 70.0));
            assert!(!covers(shape, 30.0, 70.0));
            assert!(covers(shape, 50.0, 70.0));
        }
    }
    for foreground in ["dark", "light"] {
        for threshold in [1, 64, 125, 126, 127, 128, 254] {
            for invert in [false, true] {
                let s = settings(
                    json!({"foreground":foreground,"threshold":threshold,"invert":invert,"detail":"draft"}),
                );
                let result = artwork::trace(GOLD, &s);
                let empty = !invert
                    && if foreground == "dark" {
                        threshold < 126
                    } else {
                        threshold >= 126
                    };
                assert_eq!(result.is_err(), empty, "{foreground}/{threshold}/{invert}");
                if let Err(e) = result {
                    assert_eq!(e.code, "image_selection");
                }
                assert!(artwork::trace(GOLD, &Settings::parse("{}").unwrap()).is_ok());
            }
        }
    }
}
#[test]
fn complementary_random_seams_preserve_clearance_and_outer_size() {
    for seed in [0, 1, 17, 42, 123456, 2147483647] {
        let mut v = json!({"layout":"puzzle","puzzle_seed":seed,"clearance_mm":0});
        let tiles = layout::partition(&settings(v.clone()), 4, 3).unwrap();
        let union = manifold_csg::CrossSection::batch_union(
            &tiles.iter().map(|t| t.shape.clone()).collect::<Vec<_>>(),
        );
        assert!((union.area() - 180.0 * 180.0).abs() < 1e-6);
        for (i, a) in tiles.iter().enumerate() {
            for b in &tiles[i + 1..] {
                assert!(a.shape.intersection(&b.shape).area() < 1e-6);
            }
        }
        v["clearance_mm"] = json!(0.3);
        let tiles = layout::partition(&settings(v), 4, 3).unwrap();
        for (i, a) in tiles.iter().enumerate() {
            for b in &tiles[i + 1..] {
                assert!(
                    artwork::offset(&a.shape, 0.298)
                        .intersection(&b.shape)
                        .area()
                        < 1e-6
                );
            }
        }
    }
}
#[test]
fn mounts_contour_islands_and_exclusion_zone_recover() {
    let islands=br#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="25" cy="50" r="20"/><circle cx="75" cy="50" r="20"/></svg>"#;
    let mut v =
        json!({"shape":"contour","width_mm":120,"height_mm":180,"frame":false,"margin_mm":0});
    assert!(
        geometry::build(islands, settings(v.clone()))
            .err()
            .unwrap()
            .detail
            .contains("disconnected islands")
    );
    v["margin_mm"] = json!(9);
    assert!(geometry::build(islands, settings(v)).is_ok());
    let narrow=br#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 180"><rect x="46" y="10" width="8" height="160"/></svg>"#;
    let mut v = json!({"shape":"contour","width_mm":120,"height_mm":180,"frame":false,"margin_mm":0,"hanging":"keyholes","base_mm":5});
    assert!(
        geometry::build(narrow, settings(v.clone()))
            .err()
            .unwrap()
            .detail
            .contains("too narrow")
    );
    v["margin_mm"] = json!(5);
    assert!(geometry::build(narrow, settings(v)).is_ok());
    let p = geometry::build(
        GOLD,
        settings(json!({"width_mm":250,"height_mm":250,"bed_width_mm":256,"bed_height_mm":256})),
    )
    .unwrap();
    assert!(
        relief_core::exports::manifest(&p)
            .unwrap_err()
            .detail
            .contains("exclusion zone")
    );
    let p = geometry::build(GOLD, settings(json!({"width_mm":230,"height_mm":230}))).unwrap();
    assert!(relief_core::exports::manifest(&p).is_ok());
}
#[test]
fn input_limits_and_svg_resources_fail_before_geometry_and_recover() {
    let s = Settings::parse("{}").unwrap();
    for data in [
        Vec::new(),
        vec![0; artwork::MAX_INPUT_BYTES + 1],
        b"not an image".to_vec(),
    ] {
        assert!(artwork::load_image(&data, &s).is_err());
    }
    for body in [
        "<script/>",
        "<image href=\"data:image/png;base64,abc\"/>",
        "<use href=\"https://example.invalid/image\"/>",
        "<style>@import 'x';</style>",
        "<path fill=\"url(https://example.invalid/x)\"/>",
    ] {
        let svg = format!(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 100 100\">{body}</svg>"
        );
        assert!(artwork::load_image(svg.as_bytes(), &s).is_err());
    }
    for svg in [
        "<svg/>",
        "<svg viewBox=\"0 0 0 1\"/>",
        "<svg viewBox=\"0 0 10000 1\"/>",
    ] {
        assert!(artwork::load_image(svg.as_bytes(), &s).is_err());
    }
    assert!(geometry::build(GOLD, s).is_ok());
}
#[test]
fn extreme_beads_and_rounded_loops_remain_closed() {
    for shape in ["rectangle", "contour"] {
        for (width, height) in [(0.5, 0.4), (0.5, 12.0), (12.0, 0.4), (12.0, 12.0)] {
            let p=geometry::build(ICON,settings(json!({"shape":shape,"width_mm":100,"height_mm":150,"frame_profile":"beaded","frame_width_mm":width,"frame_height_mm":height,"detail":"fine"}))).unwrap();
            let piece = &p.pieces[0];
            assert!(
                (piece.combined.volume()
                    - piece.base.volume()
                    - piece.artwork.as_ref().unwrap().volume())
                .abs()
                    < 0.1
            );
        }
    }
    for radius in [0, 45, 90] {
        for profile in ["flat", "rounded"] {
            let p = geometry::build(
                artwork::SAMPLE,
                settings(
                    json!({"hanging":"loops","corner_radius_mm":radius,"frame_profile":profile}),
                ),
            )
            .unwrap();
            let piece = &p.pieces[0];
            assert!((piece.extents[1] - 189.0).abs() < 1e-4);
            assert_eq!(piece.tile.shape.num_contour(), 2);
        }
    }
}

#[test]
fn touching_pixel_contours_do_not_fill_negative_space() {
    let data = include_bytes!("../../../tests/fixtures/pixel-contacts.png");
    let traced = artwork::trace(data,&settings(json!({"shape":"contour","width_mm":90,"height_mm":90,"min_area_mm2":0,"frame":false,"margin_mm":0}))).unwrap();
    let region = traced.relief();
    let gray = image::load_from_memory(data).unwrap().to_luma8();
    let foreground = gray.pixels().filter(|p| p[0] < 128).count() as f64;
    assert!(region.area() > 0.0);
    assert!(region.area() < foreground * (90.0_f64 / 29.0).powi(2));
}

#[test]
fn contour_inversion_keeps_the_silhouette_and_reverses_only_its_interior() {
    let black = String::from_utf8_lossy(ICON).replace("#b78e45", "#000000");
    let mut png = std::io::Cursor::new(Vec::new());
    artwork::render_svg(black.as_bytes(), 384)
        .unwrap()
        .write_to(&mut png, image::ImageFormat::Png)
        .unwrap();
    for source in [ICON, artwork::SAMPLE, png.get_ref().as_slice()] {
        let mut values = json!({"shape":"contour","width_mm":120,"height_mm":180,"frame":false,"margin_mm":0,"min_area_mm2":0,"detail":"draft"});
        let normal = geometry::build(source, settings(values.clone())).unwrap();
        values["invert"] = json!(true);
        let inverted = geometry::build(source, settings(values.clone())).unwrap();
        let outline = &normal.pieces[0].tile.shape;
        let inverted_outline = &inverted.pieces[0].tile.shape;
        assert!(outline.difference(inverted_outline).area() < 1e-7);
        assert!(inverted_outline.difference(outline).area() < 1e-7);
        assert!(normal.vector.intersection(&inverted.vector).area() < 1e-7);
        assert!(
            outline
                .difference(&normal.vector.union(&inverted.vector))
                .area()
                < 1e-7
        );
        assert!(inverted.vector.difference(outline).area() < 1e-7);
        assert!((normal.pieces[0].base.volume() - inverted.pieces[0].base.volume()).abs() < 1e-5);
        assert!(!inverted.vector.is_empty());
        if source == ICON {
            assert!(covers(&normal.vector, 60.0, 170.0));
            assert!(!covers(&inverted.vector, 60.0, 170.0));
            assert!(!covers(&normal.vector, 60.0, 150.0));
            assert!(covers(&inverted.vector, 60.0, 150.0));
            assert!(covers(&normal.vector, 60.0, 52.0));
            assert!(!covers(&inverted.vector, 60.0, 52.0));
        }
        values["invert"] = json!(false);
        let restored = geometry::build(source, settings(values)).unwrap();
        assert!(
            (normal.pieces[0].combined.volume() - restored.pieces[0].combined.volume()).abs()
                < 1e-5
        );
    }
}

#[test]
fn contour_inversion_preserves_empty_relief_and_island_recovery() {
    let solid = br#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="30"/></svg>"#;
    let mut values = json!({"shape":"contour","frame":false,"margin_mm":0,"invert":true});
    let inverted = geometry::build(solid, settings(values.clone())).unwrap();
    assert!(inverted.vector.is_empty());
    assert!(inverted.pieces[0].artwork.is_none());
    assert!(
        inverted
            .warnings
            .iter()
            .any(|s| s.contains("no enclosed negative space"))
    );
    assert!(relief_core::exports::export(&inverted).is_ok());
    values["invert"] = json!(false);
    let restored = geometry::build(solid, settings(values.clone())).unwrap();
    assert!(restored.pieces[0].artwork.is_some());
    assert_eq!(
        restored.pieces[0].base.vertices,
        inverted.pieces[0].base.vertices
    );

    let islands = br#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="25" cy="50" r="20"/><circle cx="75" cy="50" r="20"/></svg>"#;
    for invert in [true, false] {
        values["invert"] = json!(invert);
        values["margin_mm"] = json!(0);
        assert!(
            geometry::build(islands, settings(values.clone()))
                .err()
                .unwrap()
                .detail
                .contains("disconnected islands")
        );
        values["margin_mm"] = json!(12);
        assert!(geometry::build(islands, settings(values.clone())).is_ok());
    }
}
