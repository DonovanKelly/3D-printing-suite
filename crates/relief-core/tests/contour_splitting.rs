/*! Exercise silhouette cuts through concavities, empty cells, and negative origins.
Every fragment must remain a connected, closed print with a unique assembly ID;
zero-clearance cuts reconstruct the original materials without adding a frame. */
use manifold_csg::CrossSection;
use relief_core::{artwork, exports, geometry, layout, packing, settings::Settings};
use serde_json::{Value, json};
use std::collections::HashSet;

const FORK: &[u8] = include_bytes!("../../../tests/fixtures/contour-fork.svg");
const ICON: &[u8] = include_bytes!("../../../tests/fixtures/contour-icon.svg");

fn settings(v: Value) -> Settings {
    Settings::parse(&v.to_string()).unwrap()
}
fn union(p: &geometry::Project) -> CrossSection {
    CrossSection::batch_union(
        &p.pieces
            .iter()
            .map(|p| p.tile.shape.clone())
            .collect::<Vec<_>>(),
    )
}
fn validate(p: &geometry::Project, limit: f64) {
    let names: HashSet<_> = p.pieces.iter().map(|p| p.tile.name()).collect();
    assert_eq!(names.len(), p.pieces.len());
    for piece in &p.pieces {
        assert_eq!(piece.tile.shape.decompose().len(), 1);
        for mesh in [
            Some(&piece.base),
            piece.artwork.as_ref(),
            piece.border.as_ref(),
            Some(&piece.combined),
        ]
        .into_iter()
        .flatten()
        {
            mesh.validate().unwrap();
            assert!(mesh.volume() > 0.0);
        }
        assert!(piece.extents[0] <= limit + 1e-4 && piece.extents[1] <= limit + 1e-4);
        let materials = piece.base.volume()
            + piece.artwork.as_ref().map_or(0.0, |m| m.volume())
            + piece.border.as_ref().map_or(0.0, |m| m.volume());
        assert!((piece.combined.volume() - materials).abs() < 0.1);
    }
    let separated = packing::separated(p).0;
    for places in std::iter::once(separated).chain(packing::plates(p)) {
        for (i, a) in places.iter().enumerate() {
            for b in &places[i + 1..] {
                let ea = p.pieces[a.piece].extents;
                let eb = p.pieces[b.piece].extents;
                assert!(
                    a.x + ea[0] + 2.999 <= b.x
                        || b.x + eb[0] + 2.999 <= a.x
                        || a.y + ea[1] + 2.999 <= b.y
                        || b.y + eb[1] + 2.999 <= a.y
                );
            }
        }
    }
    let manifest = exports::manifest(p).unwrap();
    let placed: Vec<_> = manifest["plates"]
        .as_array()
        .unwrap()
        .iter()
        .flat_map(|plate| plate["pieces"].as_array().unwrap().iter())
        .map(|p| p["id"].as_str().unwrap())
        .collect();
    assert_eq!(placed.len(), names.len());
    assert_eq!(
        placed.into_iter().collect::<HashSet<_>>(),
        names.iter().map(String::as_str).collect()
    );
}

#[test]
fn contour_cuts_reconstruct_all_materials_across_profiles_and_layouts() {
    for profile in ["flat", "rounded", "beaded"] {
        let mut v = json!({"shape":"contour","width_mm":160,"height_mm":160,"margin_mm":3,"frame_width_mm":5,"frame_profile":profile,"border_material":"custom","detail":"draft","clearance_mm":0});
        let whole = geometry::build(FORK, settings(v.clone())).unwrap();
        for layout in ["tiles", "puzzle"] {
            v["layout"] = json!(layout);
            v["columns"] = json!(2);
            v["rows"] = json!(2);
            let split = geometry::build(FORK, settings(v.clone())).unwrap();
            validate(&split, 230.0);
            assert!(union(&whole).difference(&union(&split)).area() < 1e-5);
            assert!(union(&split).difference(&union(&whole)).area() < 1e-5);
            for (i, a) in split.pieces.iter().enumerate() {
                for b in &split.pieces[i + 1..] {
                    assert!(a.tile.shape.intersection(&b.tile.shape).area() < 1e-6);
                }
            }
            let volumes = |p: &geometry::Project| -> [f64; 3] {
                [
                    p.pieces.iter().map(|p| p.base.volume()).sum(),
                    p.pieces
                        .iter()
                        .map(|p| p.artwork.as_ref().map_or(0.0, |m| m.volume()))
                        .sum(),
                    p.pieces
                        .iter()
                        .map(|p| p.border.as_ref().map_or(0.0, |m| m.volume()))
                        .sum(),
                ]
            };
            for (a, b) in volumes(&whole).into_iter().zip(volumes(&split)) {
                assert!((a - b).abs() < 0.2, "{profile}/{layout}: {a} != {b}");
            }
        }
    }
}

#[test]
fn concavities_get_unique_fragments_and_empty_cells_are_omitted() {
    let v = json!({"shape":"contour","layout":"tiles","columns":1,"rows":2,"frame":false,"margin_mm":0,"clearance_mm":0,"detail":"draft"});
    let p = geometry::build(FORK, settings(v.clone())).unwrap();
    validate(&p, 230.0);
    assert_eq!(
        p.pieces.iter().map(|p| p.tile.name()).collect::<Vec<_>>(),
        ["r01-c01-p01", "r01-c01-p02", "r02-c01"]
    );
    let mut v = v;
    v["columns"] = json!(3);
    v["rows"] = json!(3);
    let p = geometry::build(FORK, settings(v)).unwrap();
    validate(&p, 230.0);
    assert_eq!(p.pieces.len(), 7);
    assert!(
        !p.pieces
            .iter()
            .any(|p| p.tile.row < 2 && p.tile.column == 1)
    );
}

#[test]
fn oversized_contour_recovers_with_size_bed_and_manual_cuts() {
    let mut v = json!({"shape":"contour","width_mm":540,"height_mm":540,"detail":"draft"});
    assert!(
        geometry::build(ICON, settings(v.clone()))
            .err()
            .unwrap()
            .detail
            .contains("Choose Tiles or Puzzle")
    );
    for layout in ["tiles", "puzzle"] {
        v["layout"] = json!(layout);
        for mode in ["size", "bed"] {
            v["split_mode"] = json!(mode);
            v["piece_size_mm"] = json!(150);
            let p = geometry::build(ICON, settings(v.clone())).unwrap();
            assert!(p.pieces.len() > 1);
            validate(&p, if mode == "size" { 150.0 } else { 230.0 });
        }
    }
    v["columns"] = json!(1);
    v["rows"] = json!(2);
    assert!(
        geometry::build(ICON, settings(v.clone()))
            .err()
            .unwrap()
            .detail
            .contains("exceeds")
    );
    v["columns"] = json!(4);
    v["rows"] = json!(4);
    let p = geometry::build(ICON, settings(v)).unwrap();
    validate(&p, 230.0);
}

#[test]
fn contour_clearance_preserves_boundary_and_inversion_keeps_cuts() {
    for style in ["regular", "random"] {
        let mut v = json!({"shape":"contour","layout":"puzzle","columns":2,"rows":2,"clearance_mm":0.3,"puzzle_style":style,"detail":"draft"});
        let p = geometry::build(ICON, settings(v.clone())).unwrap();
        for (i, a) in p.pieces.iter().enumerate() {
            for b in &p.pieces[i + 1..] {
                assert!(
                    artwork::offset(&a.tile.shape, 0.298)
                        .intersection(&b.tile.shape)
                        .area()
                        < 1e-6
                );
            }
        }
        v["invert"] = json!(true);
        let inverted = geometry::build(ICON, settings(v.clone())).unwrap();
        assert!(union(&p).difference(&union(&inverted)).area() < 1e-6);
        assert!(p.vector.intersection(&inverted.vector).area() < 1e-6);
        v["clearance_mm"] = json!(0);
        let no_gap = geometry::build(ICON, settings(v)).unwrap();
        assert!(union(&p).difference(&union(&no_gap)).area() < 1e-6);
        assert!(union(&p).area() < union(&no_gap).area());
        assert_eq!(
            artwork::bounds(&union(&p)),
            artwork::bounds(&union(&no_gap))
        );
    }
}

#[test]
fn mounts_and_fragment_limit_fail_explicitly_and_recover() {
    let mut v = json!({"shape":"contour","layout":"tiles","columns":2,"rows":2,"hanging":"loops","detail":"draft"});
    let p = geometry::build(FORK, settings(v.clone())).unwrap();
    validate(&p, 230.0);
    assert_eq!(
        p.pieces
            .iter()
            .filter(|p| p.tile.shape.num_contour() > 1)
            .count(),
        2
    );
    v["hanging"] = json!("keyholes");
    v["base_mm"] = json!(5);
    let p = geometry::build(FORK, settings(v.clone())).unwrap();
    validate(&p, 230.0);
    v["width_mm"] = json!(50);
    v["height_mm"] = json!(50);
    v["frame"] = json!(false);
    v["margin_mm"] = json!(0);
    assert!(
        geometry::build(FORK, settings(v.clone()))
            .err()
            .unwrap()
            .detail
            .contains("too narrow")
    );
    v["hanging"] = json!("none");
    assert!(geometry::build(FORK, settings(v)).is_ok());

    let islands: Vec<_> = (0..65)
        .map(|i| {
            layout::rect(
                (i % 9) as f64 * 10.0,
                (i / 9) as f64 * 10.0,
                (i % 9) as f64 * 10.0 + 5.0,
                (i / 9) as f64 * 10.0 + 5.0,
            )
        })
        .collect();
    let s = settings(json!({"shape":"contour","layout":"tiles","columns":2,"rows":1}));
    assert!(
        layout::choose_outline(&s, &CrossSection::batch_union(&islands))
            .err()
            .unwrap()
            .detail
            .contains("64 pieces")
    );
    assert!(layout::choose_outline(&s, &layout::rect(0.0, 0.0, 90.0, 90.0)).is_ok());
}

#[test]
fn thin_silhouettes_split_along_their_long_axis_and_islands_stay_printable() {
    let narrow = br#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 400"><rect x="5" y="0" width="10" height="400"/></svg>"#;
    let s = settings(
        json!({"shape":"contour","layout":"tiles","width_mm":100,"height_mm":400,"frame":false,"margin_mm":0,"split_mode":"bed","detail":"draft"}),
    );
    let p = geometry::build(narrow, s).unwrap();
    assert_eq!((p.columns, p.rows, p.pieces.len()), (1, 2, 2));
    validate(&p, 230.0);

    let islands = br#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="25" cy="50" r="20"/><circle cx="75" cy="50" r="20"/></svg>"#;
    let mut v = json!({"shape":"contour","frame":false,"margin_mm":0,"detail":"draft"});
    assert!(
        geometry::build(islands, settings(v.clone()))
            .err()
            .unwrap()
            .detail
            .contains("disconnected islands")
    );
    v["layout"] = json!("tiles");
    v["columns"] = json!(2);
    v["rows"] = json!(1);
    let p = geometry::build(islands, settings(v)).unwrap();
    assert_eq!(p.pieces.len(), 2);
    validate(&p, 230.0);
}
