#!/usr/bin/env bash
# Compile the shared engine and Manifold into local browser assets; no runtime CDN.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v cargo >/dev/null && [[ -f "$HOME/.cargo/env" ]]; then source "$HOME/.cargo/env"; fi
if ! command -v emcc >/dev/null; then
  relief_emsdk="${RELIEF_EMSDK:-$HOME/.local/share/relief-emsdk}"
  if [[ ! -f "$relief_emsdk/emsdk_env.sh" ]]; then
    printf 'Install Emscripten 4.0.15 and set RELIEF_EMSDK to its directory.\n' >&2
    exit 1
  fi
  source "$relief_emsdk/emsdk_env.sh" >/dev/null 2>&1
fi
if [[ -x .venv/bin/cmake ]]; then export PATH="$PWD/.venv/bin:$PATH"; fi
rustup target add wasm32-unknown-emscripten
cargo build --locked --release --bin relief-web --target wasm32-unknown-emscripten
mkdir -p web/public/engine
cp target/wasm32-unknown-emscripten/release/relief-web.js web/public/engine/relief-core.js
cp target/wasm32-unknown-emscripten/release/relief_web.wasm web/public/engine/relief_web.wasm
