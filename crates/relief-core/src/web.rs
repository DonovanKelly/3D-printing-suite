/*! Emscripten module entrypoint; the worker calls the exported owned-buffer ABI. */
fn main() {
    #[cfg(target_os = "emscripten")]
    let _ = relief_core::wasm::relief_response_len();
}
