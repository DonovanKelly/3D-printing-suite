# 3D Printing Suite

Build tools that turn images into two-color printable reliefs, framed wall art,
build-plate-sized panels, and interlocking puzzles. The initial target is PLA on
a Bambu Lab P1S with AMS. Keep colors configurable.

## Working agreement

- The three-phase feature development workflow does not apply to this project.
- Work in small, useful increments. Validate, commit, and push each completed
  increment frequently; do not leave durable work only in the workspace.
- Keep project rules, source, tests, design decisions, and reproducible examples
  in Git. Preserve credentials and private workspace guidance outside Git.
- Put generated review/print packs in the configured shared output directory
  when shared storage is available. Never overwrite a user's source artwork.
- Use millimeters throughout geometry and exports. Preserve holes and material
  alignment. Validate closed meshes, positive volume, and actual piece extents.
- A computational check is not a physical print test. State fit, mounting, and
  slicer limitations explicitly. Never send jobs to a printer automatically.
- Keep image preparation independent of geometry. Optional cloud providers
  must be explicit; local import and export must work without an API key.
- Run `bash scripts/check.sh` before publishing application changes. It includes
  Rust tests/Clippy, Python reference and export tests, Ruff, TypeScript checks,
  the production Wasm build, and real browser
  regression tests. For documentation-only changes, use relevant narrow checks.
- Preserve each reproduced user-reported failure in the regression suite. Test
  both the failure boundary and recovery; do not weaken or skip a case to pass.
  Private SVGs use `RELIEF_TEST_ARTWORK` and stay outside Git. See `docs/testing.md`.
- Keep source module comments focused on purpose/invariants.

## Structure

- `crates/relief-core`: shared Rust image, geometry, exports, native CLI, and Wasm engine.
- `src/relief_studio`: frozen Python reference pipeline, legacy CLI, and local API.
- `web`: React/TypeScript workbench and live geometry preview.
- `examples`: original sample artwork and reproducible project settings.
- `docs`: design, usage, print workflow, and follow-up decisions.

The browser worker and native CLI share the same Rust geometry pipeline. Keep printer and
project settings validated at that boundary. Generated packs belong outside
Git; source artwork deliberately included as examples belongs in Git.
