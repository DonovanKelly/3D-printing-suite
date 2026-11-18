/*! Preserve the closed-SVG white-backing import boundary and its two recoveries.
Automatic alpha selection sees an opaque silhouette; dark selection or removing
the display-only backing must recover the same holes, islands, and valid solids.
Thin closed rims can disconnect during tracing; a stronger rim must recover. */
use relief_core::{artwork, geometry, layout, settings::Settings};
use serde_json::json;

const BACKED: &str = include_str!("../../../tests/fixtures/white-backed-icon.svg");

#[test]
fn closed_but_subpixel_rim_rejects_disconnected_contours_and_recovers() {
    let outline = [
        (50.0, 10.0),
        (90.0, 30.0),
        (90.0, 70.0),
        (50.0, 90.0),
        (10.0, 70.0),
        (10.0, 30.0),
    ];
    let source = |width: f64| {
        let path = |scale: f64| {
            outline
                .iter()
                .map(|(x, y)| {
                    format!(
                        "{},{}",
                        50.0 + (x - 50.0) * scale,
                        50.0 + (y - 50.0) * scale
                    )
                })
                .collect::<Vec<_>>()
                .join("L")
        };
        format!(
            r#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path fill-rule="evenodd" d="M{}Z M{}Z"/><circle cx="50" cy="50" r="4"/></svg>"#,
            path(1.0),
            path(1.0 - width / 40.0)
        )
    };
    let settings = || {
        Settings::parse(r#"{"shape":"contour","frame":false,"margin_mm":0,"detail":"draft"}"#)
            .unwrap()
    };
    let rejected = geometry::build(source(0.35).as_bytes(), settings())
        .err()
        .unwrap();
    assert!(rejected.detail.contains("disconnected islands"));
    let recovered = geometry::build(source(2.0).as_bytes(), settings()).unwrap();
    assert_eq!(recovered.vector.decompose().len(), 2);
    assert_eq!(recovered.vector.num_contour(), 3);
    assert_eq!(recovered.pieces.len(), 1);
    recovered.pieces[0].base.validate().unwrap();
    recovered.pieces[0]
        .artwork
        .as_ref()
        .unwrap()
        .validate()
        .unwrap();
    recovered.pieces[0].combined.validate().unwrap();
}

#[test]
fn opaque_backing_recovers_with_dark_selection_or_transparent_cutouts() {
    let doc = roxmltree::Document::parse(BACKED).unwrap();
    let backing = doc
        .descendants()
        .find(|n| n.attribute("id") == Some("white-backing"))
        .unwrap();
    let mut cutout = BACKED.to_owned();
    cutout.replace_range(backing.range(), "");

    for detail in ["draft", "balanced", "fine"] {
        let mut values = json!({
            "width_mm":100,"height_mm":100,"shape":"contour",
            "frame":false,"margin_mm":0,"min_area_mm2":0,"detail":detail
        });
        let parse = |v: &serde_json::Value| Settings::parse(&v.to_string()).unwrap();
        let filled = geometry::build(BACKED.as_bytes(), parse(&values)).unwrap();
        assert_eq!(filled.vector.num_contour(), 1);
        assert!(
            filled
                .vector
                .intersection(&layout::circle(25.0, 50.0, 0.1))
                .area()
                > 0.01
        );

        values["foreground"] = json!("dark");
        let dark = geometry::build(BACKED.as_bytes(), parse(&values)).unwrap();
        values["foreground"] = json!("auto");
        let automatic = geometry::build(cutout.as_bytes(), parse(&values)).unwrap();

        for project in [&dark, &automatic] {
            assert_eq!(project.vector.decompose().len(), 2);
            assert_eq!(
                project
                    .vector
                    .to_polygons()
                    .iter()
                    .filter(|r| artwork::signed_area(r) < 0.0)
                    .count(),
                1
            );
            assert!(
                project
                    .vector
                    .intersection(&layout::circle(25.0, 50.0, 0.1))
                    .is_empty()
            );
            assert!(
                project
                    .vector
                    .intersection(&layout::circle(50.0, 50.0, 0.1))
                    .area()
                    > 0.01
            );
            assert!(project.vector.area() < filled.vector.area() * 0.6);
            let piece = &project.pieces[0];
            piece.base.validate().unwrap();
            piece.artwork.as_ref().unwrap().validate().unwrap();
            piece.combined.validate().unwrap();
            assert_eq!(piece.extents, filled.pieces[0].extents);
        }
        assert!(dark.vector.difference(&automatic.vector).area() < 0.001);
        assert!(automatic.vector.difference(&dark.vector).area() < 0.001);
    }
}
