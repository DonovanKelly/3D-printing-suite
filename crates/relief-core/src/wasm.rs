/*! Small owned-buffer C ABI for the serialized browser worker. Buffers stay alive
until the next request; JavaScript copies them before that boundary. A failed build
invalidates exports, and no filesystem or JavaScript geometry implementation is used. */
use crate::{
    EngineError, Result, artwork, exports,
    geometry::{self, Project},
    settings::Settings,
};
use serde_json::{Value, json};
use std::cell::RefCell;
#[derive(Default)]
struct Engine {
    project: Option<Project>,
    id: u64,
    response: Vec<u8>,
    files: Vec<Vec<u8>>,
}
thread_local! {static ENGINE:RefCell<Engine>=RefCell::new(Engine::default());}
impl Engine {
    fn request(&mut self, request: Value, image: &[u8]) -> Result<Value> {
        match request["operation"].as_str() {
            Some("defaults") => Ok(serde_json::to_value(Settings::parse("{}")?).unwrap()),
            Some("build") => {
                self.project = None;
                self.files.clear();
                let s = Settings::parse(&request["settings"].to_string())?;
                let data = if request["sample"] == true {
                    artwork::SAMPLE
                } else {
                    image
                };
                let project = geometry::build(data, s)?;
                self.id += 1;
                let preview = exports::preview(&project, &self.id.to_string())?;
                self.project = Some(project);
                Ok(preview)
            }
            Some("export") => {
                let project = self
                    .project
                    .as_ref()
                    .filter(|_| request["previewId"].as_str() == Some(&self.id.to_string()))
                    .ok_or_else(|| {
                        EngineError::input("This preview expired. Rebuild it before exporting.")
                    })?;
                let output = exports::export(project)?;
                self.files = vec![output.pack];
                self.files.extend(output.plates);
                Ok(json!({"plate_count":self.files.len()-1}))
            }
            _ => Err(EngineError::input("Unknown engine operation.")),
        }
    }
}
#[unsafe(no_mangle)]
pub extern "C" fn relief_alloc(length: usize) -> *mut u8 {
    Box::into_raw(vec![0u8; length].into_boxed_slice()) as *mut u8
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn relief_free(pointer: *mut u8, length: usize) {
    if !pointer.is_null() {
        unsafe {
            drop(Box::from_raw(std::ptr::slice_from_raw_parts_mut(
                pointer, length,
            )));
        }
    }
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn relief_request(
    request: *const u8,
    length: usize,
    image: *const u8,
    image_length: usize,
) {
    let request = unsafe { std::slice::from_raw_parts(request, length) };
    let image = unsafe { std::slice::from_raw_parts(image, image_length) };
    ENGINE.with(|state| {
        let mut state = state.borrow_mut();
        let result = serde_json::from_slice(request)
            .map_err(|e| EngineError::input(e.to_string()))
            .and_then(|request| state.request(request, image));
        state.response = serde_json::to_vec(&match result {
            Ok(value) => json!({"ok":true,"value":value}),
            Err(error) => json!({"ok":false,"error":error}),
        })
        .unwrap();
    });
}
#[unsafe(no_mangle)]
pub extern "C" fn relief_response_ptr() -> *const u8 {
    ENGINE.with(|s| s.borrow().response.as_ptr())
}
#[unsafe(no_mangle)]
pub extern "C" fn relief_response_len() -> usize {
    ENGINE.with(|s| s.borrow().response.len())
}
#[unsafe(no_mangle)]
pub extern "C" fn relief_file_ptr(index: usize) -> *const u8 {
    ENGINE.with(|s| {
        s.borrow()
            .files
            .get(index)
            .map_or(std::ptr::null(), |b| b.as_ptr())
    })
}
#[unsafe(no_mangle)]
pub extern "C" fn relief_file_len(index: usize) -> usize {
    ENGINE.with(|s| s.borrow().files.get(index).map_or(0, |b| b.len()))
}
#[unsafe(no_mangle)]
pub extern "C" fn relief_clear_files() {
    ENGINE.with(|s| s.borrow_mut().files.clear());
}
