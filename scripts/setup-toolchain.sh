#!/usr/bin/env bash
# Install pinned Rust and Emscripten tools for native/Wasm builds, never browser runtime.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v cargo >/dev/null; then
  if [[ -f "$HOME/.cargo/env" ]]; then
    source "$HOME/.cargo/env"
  else
    relief_installer="$(mktemp)"
    trap 'rm -f "$relief_installer"' EXIT
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o "$relief_installer"
    sh "$relief_installer" -y --profile minimal --default-toolchain 1.98.1
    source "$HOME/.cargo/env"
  fi
fi
rustup toolchain install 1.98.1 --profile minimal --component rustfmt --component clippy
rustup target add wasm32-unknown-emscripten --toolchain 1.98.1
relief_emsdk="${RELIEF_EMSDK:-$HOME/.local/share/relief-emsdk}"
if [[ ! -d "$relief_emsdk" ]]; then
  mkdir -p "$(dirname "$relief_emsdk")"
  git clone --depth 1 --branch 4.0.15 https://github.com/emscripten-core/emsdk.git "$relief_emsdk"
fi
"$relief_emsdk/emsdk" install 4.0.15
"$relief_emsdk/emsdk" activate 4.0.15
printf 'Build tools ready. CMake, a C++ compiler, Git, and Node must also be on PATH.\n'
