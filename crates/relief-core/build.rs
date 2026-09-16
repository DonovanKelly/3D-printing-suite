/*! Link Rust and Manifold with the same WebAssembly exception and memory ABI. */
fn main() {
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("emscripten") {
        for arg in [
            "-fwasm-exceptions",
            "-sALLOW_MEMORY_GROWTH=1",
            "-sMAXIMUM_MEMORY=2147483648",
            "-sSTACK_SIZE=33554432",
            "-sINITIAL_MEMORY=67108864",
            "-sMODULARIZE=1",
            "-sEXPORT_ES6=1",
            "-sENVIRONMENT=web,worker,node",
            "-sFILESYSTEM=0",
            "-sEXPORTED_FUNCTIONS=_relief_alloc,_relief_free,_relief_request,_relief_response_ptr,_relief_response_len,_relief_file_ptr,_relief_file_len,_relief_clear_files",
            "-sEXPORTED_RUNTIME_METHODS=HEAPU8",
            "--no-entry",
        ] {
            println!("cargo:rustc-link-arg={arg}");
        }
    }
}
