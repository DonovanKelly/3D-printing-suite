/*! Shared native and browser engine. Settings, image interpretation, geometry,
validation, and print formats use one code path with millimeter coordinates. */
pub mod artwork;
pub mod exports;
pub mod geometry;
pub mod layout;
pub mod packing;
mod random;
pub mod settings;
pub mod solids;
use serde::Serialize;

pub type Result<T> = std::result::Result<T, EngineError>;
#[derive(Debug, Serialize)]
pub struct EngineError {
    pub detail: String,
    pub code: &'static str,
}
impl EngineError {
    pub fn input(message: impl Into<String>) -> Self {
        Self {
            detail: message.into(),
            code: "input",
        }
    }
    pub fn settings(message: impl Into<String>) -> Self {
        Self {
            detail: message.into(),
            code: "settings",
        }
    }
    pub fn selection(message: impl Into<String>) -> Self {
        Self {
            detail: message.into(),
            code: "image_selection",
        }
    }
}
impl std::fmt::Display for EngineError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.detail)
    }
}
impl std::error::Error for EngineError {}
#[cfg(target_os = "emscripten")]
pub mod wasm;
