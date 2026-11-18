/*! Validate untrusted project settings once at the engine boundary. The trusted wrapper
exposes read-only fields; all native and browser callers use the same parser. */
use crate::{EngineError, Result};
use serde::{Deserialize, Serialize};
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Shape {
    Rectangle,
    Contour,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FrameProfile {
    Flat,
    Rounded,
    Beaded,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BorderMaterial {
    Artwork,
    Background,
    Custom,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Foreground {
    Auto,
    Dark,
    Light,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Detail {
    Draft,
    Balanced,
    Fine,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Layout {
    Plaque,
    Tiles,
    Puzzle,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SplitMode {
    Size,
    Bed,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PuzzleStyle {
    Random,
    Regular,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Hanging {
    None,
    Loops,
    Keyholes,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct RawSettings {
    pub width_mm: f64,
    pub height_mm: f64,
    pub base_mm: f64,
    pub relief_mm: f64,
    pub shape: Shape,
    pub frame: bool,
    pub frame_width_mm: f64,
    pub frame_height_mm: f64,
    pub frame_profile: FrameProfile,
    pub corner_radius_mm: f64,
    pub margin_mm: f64,
    pub crop_to_artwork: bool,
    pub threshold: u32,
    pub foreground: Foreground,
    pub invert: bool,
    pub detail: Detail,
    pub min_area_mm2: f64,
    pub layout: Layout,
    pub columns: u32,
    pub rows: u32,
    pub split_mode: SplitMode,
    pub piece_size_mm: f64,
    pub puzzle_style: PuzzleStyle,
    pub puzzle_seed: u32,
    pub clearance_mm: f64,
    pub bed_width_mm: f64,
    pub bed_height_mm: f64,
    pub hanging: Hanging,
    pub background_color: String,
    pub artwork_color: String,
    pub border_material: BorderMaterial,
    pub border_color: String,
}
impl Default for RawSettings {
    fn default() -> Self {
        Self {
            width_mm: 180.0,
            height_mm: 180.0,
            base_mm: 2.4,
            relief_mm: 0.8,
            shape: Shape::Rectangle,
            frame: true,
            frame_width_mm: 4.0,
            frame_height_mm: 1.6,
            frame_profile: FrameProfile::Flat,
            corner_radius_mm: 0.0,
            margin_mm: 3.0,
            crop_to_artwork: true,
            threshold: 128,
            foreground: Foreground::Auto,
            invert: false,
            detail: Detail::Balanced,
            min_area_mm2: 0.6,
            layout: Layout::Plaque,
            columns: 0,
            rows: 0,
            split_mode: SplitMode::Size,
            piece_size_mm: 90.0,
            puzzle_style: PuzzleStyle::Random,
            puzzle_seed: 1,
            clearance_mm: 0.25,
            bed_width_mm: 230.0,
            bed_height_mm: 230.0,
            hanging: Hanging::None,
            background_color: "#fcfcfa".into(),
            artwork_color: "#252b28".into(),
            border_material: BorderMaterial::Artwork,
            border_color: "#c99b48".into(),
        }
    }
}
#[derive(Clone, Debug, Serialize)]
#[serde(transparent)]
pub struct Settings(RawSettings);
impl std::ops::Deref for Settings {
    type Target = RawSettings;
    fn deref(&self) -> &RawSettings {
        &self.0
    }
}
impl Settings {
    pub fn parse(json: &str) -> Result<Self> {
        let raw: RawSettings =
            serde_json::from_str(json).map_err(|e| EngineError::settings(e.to_string()))?;
        let s = Self(raw);
        if !(s.width_mm as f64).is_finite() || !(30.0..=1500.0).contains(&(s.width_mm as f64)) {
            return Err(EngineError::settings(
                "Width (mm): must be between 30 and 1500.",
            ));
        }
        if !(s.height_mm as f64).is_finite() || !(30.0..=1500.0).contains(&(s.height_mm as f64)) {
            return Err(EngineError::settings(
                "Height (mm): must be between 30 and 1500.",
            ));
        }
        if !(s.base_mm as f64).is_finite() || !(1.2..=12.0).contains(&(s.base_mm as f64)) {
            return Err(EngineError::settings(
                "Background thickness (mm): must be between 1.2 and 12.",
            ));
        }
        if !(s.relief_mm as f64).is_finite() || !(0.4..=8.0).contains(&(s.relief_mm as f64)) {
            return Err(EngineError::settings(
                "Image thickness (mm): must be between 0.4 and 8.",
            ));
        }
        if !(s.frame_width_mm as f64).is_finite()
            || !(0.5..=30.0).contains(&(s.frame_width_mm as f64))
        {
            return Err(EngineError::settings(
                "Border width (mm): must be between 0.5 and 30.",
            ));
        }
        if !(s.frame_height_mm as f64).is_finite()
            || !(0.4..=12.0).contains(&(s.frame_height_mm as f64))
        {
            return Err(EngineError::settings(
                "Border height (mm): must be between 0.4 and 12.",
            ));
        }
        if !(s.corner_radius_mm as f64).is_finite()
            || !(0.0..=100.0).contains(&(s.corner_radius_mm as f64))
        {
            return Err(EngineError::settings(
                "Corner radius (mm): must be between 0 and 100.",
            ));
        }
        if !(s.margin_mm as f64).is_finite() || !(0.0..=30.0).contains(&(s.margin_mm as f64)) {
            return Err(EngineError::settings(
                "Padding (mm): must be between 0 and 30.",
            ));
        }
        if !(s.threshold as f64).is_finite() || !(1.0..=254.0).contains(&(s.threshold as f64)) {
            return Err(EngineError::settings(
                "Threshold: must be between 1 and 254.",
            ));
        }
        if !(s.min_area_mm2 as f64).is_finite() || !(0.0..=20.0).contains(&(s.min_area_mm2 as f64))
        {
            return Err(EngineError::settings(
                "Min area mm2: must be between 0 and 20.",
            ));
        }
        if !(s.columns as f64).is_finite() || !(0.0..=12.0).contains(&(s.columns as f64)) {
            return Err(EngineError::settings("Columns: must be between 0 and 12."));
        }
        if !(s.rows as f64).is_finite() || !(0.0..=12.0).contains(&(s.rows as f64)) {
            return Err(EngineError::settings("Rows: must be between 0 and 12."));
        }
        if !(s.piece_size_mm as f64).is_finite()
            || !(30.0..=256.0).contains(&(s.piece_size_mm as f64))
        {
            return Err(EngineError::settings(
                "Max piece size (mm): must be between 30 and 256.",
            ));
        }
        if !(s.puzzle_seed as f64).is_finite()
            || !(0.0..=2147483647.0).contains(&(s.puzzle_seed as f64))
        {
            return Err(EngineError::settings(
                "Puzzle seed: must be between 0 and 2147483647.",
            ));
        }
        if !(s.clearance_mm as f64).is_finite() || !(0.0..=1.0).contains(&(s.clearance_mm as f64)) {
            return Err(EngineError::settings(
                "Clearance (mm): must be between 0 and 1.",
            ));
        }
        if !(s.bed_width_mm as f64).is_finite()
            || !(60.0..=256.0).contains(&(s.bed_width_mm as f64))
        {
            return Err(EngineError::settings(
                "Bed width (mm): must be between 60 and 256.",
            ));
        }
        if !(s.bed_height_mm as f64).is_finite()
            || !(60.0..=256.0).contains(&(s.bed_height_mm as f64))
        {
            return Err(EngineError::settings(
                "Bed height (mm): must be between 60 and 256.",
            ));
        }
        for color in [&s.background_color, &s.artwork_color, &s.border_color] {
            if color.len() != 7
                || !color.starts_with('#')
                || !color[1..].bytes().all(|b| b.is_ascii_hexdigit())
            {
                return Err(EngineError::settings("Filament colors must use #RRGGBB."));
            }
        }
        let error = if s.shape == Shape::Contour && s.layout != Layout::Plaque {
            Some("Image contour is a single piece. Choose Plaque or a rectangular shape.")
        } else if s.shape == Shape::Rectangle
            && s.corner_radius_mm > s.width_mm.min(s.height_mm) / 2.0
        {
            Some("Corner radius cannot exceed half the shorter side.")
        } else if s.width_mm.min(s.height_mm) - 2.0 * s.artwork_inset() < 10.0 {
            Some("Border width and padding must leave at least 10 mm for the artwork.")
        } else if (s.columns == 0) != (s.rows == 0) {
            Some("Set both rows and columns, or use 0 for both to split automatically.")
        } else if s.columns * s.rows > 64 {
            Some("A project can contain at most 64 pieces.")
        } else if s.layout == Layout::Plaque && (s.columns > 1 || s.rows > 1) {
            Some("Choose Tiles or Puzzle to use multiple rows or columns.")
        } else if s.layout != Layout::Plaque && s.columns == 1 && s.rows == 1 {
            Some("Tiles and Puzzle need at least two pieces. Increase the grid.")
        } else if s.hanging == Hanging::Keyholes && s.base_mm < 5.0 {
            Some("Rear keyholes need a backing at least 5 mm thick.")
        } else {
            None
        };
        if let Some(error) = error {
            return Err(EngineError::settings(error));
        }
        Ok(s)
    }
    pub fn resolved_border_color(&self) -> &str {
        match self.border_material {
            BorderMaterial::Artwork => &self.artwork_color,
            BorderMaterial::Background => &self.background_color,
            BorderMaterial::Custom => &self.border_color,
        }
    }
    pub fn artwork_inset(&self) -> f64 {
        if self.shape == Shape::Contour {
            return 0.0;
        }
        let inset = if self.frame { self.frame_width_mm } else { 0.0 } + self.margin_mm;
        inset + (self.corner_radius_mm - inset).max(0.0) * (1.0 - 1.0 / 2.0_f64.sqrt())
    }
    pub fn trace_resolution(&self) -> u32 {
        match self.detail {
            Detail::Draft => 384,
            Detail::Balanced => 768,
            Detail::Fine => 1280,
        }
    }
    pub fn simplify_mm(&self) -> f64 {
        match self.detail {
            Detail::Draft => 0.3,
            Detail::Balanced => 0.12,
            Detail::Fine => 0.05,
        }
    }
}
