#!/usr/bin/env bash
# Run every required regression layer against this checkout; fail on any failing check.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
relief_python="${RELIEF_TEST_PYTHON:-$repo_root/.venv/bin/python}"
if [[ ! -x "$relief_python" ]]; then
  printf 'Create .venv and install requirements-dev.lock plus this project first.\n' >&2
  exit 1
fi
export RELIEF_TEST_PYTHON="$relief_python"
if ! command -v cargo >/dev/null && [[ -f "$HOME/.cargo/env" ]]; then source "$HOME/.cargo/env"; fi
export PATH="$repo_root/.venv/bin:$PATH"
cargo fmt --all --check
cargo clippy --all-targets -- -D warnings
cargo test --locked --release
cargo build --locked --release --bin relief-native
mkdir -p output/verification
"$relief_python" -m ruff check .
"$relief_python" -m pytest --junitxml=output/verification/python.xml
npm --prefix web run test:types
npm --prefix web run build
npm --prefix web run test:e2e
