/*! Keep border material selection validated at the shared native/Wasm boundary,
including the original default and empty border/artwork combinations. */
use relief_core::{
    artwork, exports, geometry,
    settings::{BorderMaterial, Settings},
};
use serde_json::json;

#[test]
fn border_settings_default_validate_and_resolve_linked_colors() {
    let defaults = Settings::parse("{}").unwrap();
    assert_eq!(defaults.border_material, BorderMaterial::Artwork);
    assert_eq!(defaults.resolved_border_color(), defaults.artwork_color);
    for (mode, color) in [
        ("artwork", "#223344"),
        ("background", "#aabbcc"),
        ("custom", "#ab1234"),
    ] {
        let value = json!({"border_material": mode, "artwork_color":"#223344", "background_color":"#aabbcc", "border_color":"#ab1234"});
        let settings = Settings::parse(&value.to_string()).unwrap();
        assert_eq!(settings.resolved_border_color(), color);
    }
    for invalid in [
        json!({"border_material":"fourth"}),
        json!({"border_color":"red"}),
        json!({"border_color":"#12345g"}),
        json!({"border_material":null}),
    ] {
        assert_eq!(
            Settings::parse(&invalid.to_string()).unwrap_err().code,
            "settings"
        );
        assert!(Settings::parse("{}").is_ok());
    }
}

#[test]
fn disabling_border_omits_the_third_material_without_losing_the_choice() {
    let settings = Settings::parse(
        r##"{"frame":false,"border_material":"custom","border_color":"#aabbcc","detail":"draft"}"##,
    )
    .unwrap();
    let project = geometry::build(artwork::SAMPLE, settings).unwrap();
    assert!(project.pieces.iter().all(|piece| piece.border.is_none()));
    assert_eq!(
        exports::bambu_settings(&project)["filament_colour"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    assert_eq!(project.settings.border_color, "#aabbcc");
}

#[test]
fn a_border_only_contour_keeps_filament_three_when_artwork_is_empty() {
    let image = br#"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40"/></svg>"#;
    for mode in ["artwork", "background", "custom"] {
        let settings = Settings::parse(
            &json!({"shape":"contour","invert":true,"border_material":mode,"detail":"draft"})
                .to_string(),
        )
        .unwrap();
        let project = geometry::build(image, settings).unwrap();
        let piece = &project.pieces[0];
        assert_eq!(piece.artwork.is_none(), mode != "artwork");
        assert_eq!(piece.border.is_some(), mode == "custom");
        let volume = piece.base.volume()
            + piece.artwork.as_ref().map_or(0.0, |m| m.volume())
            + piece.border.as_ref().map_or(0.0, |m| m.volume());
        assert!((volume - piece.combined.volume()).abs() < 0.01);
        assert_eq!(
            exports::bambu_settings(&project)["filament_colour"]
                .as_array()
                .unwrap()
                .len(),
            if mode == "custom" { 3 } else { 2 }
        );
    }
}
