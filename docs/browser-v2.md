# Browser engine v2

## Contract and implementation

The reference is the Python engine at commit `9d79cce`. React and Three.js keep
their current controls and preview contract. A single Web Worker owns the current
Rust project and returns preview DTOs or export bytes. Settings changes replace
pending generation; stale previews and exports cannot become current. The worker
can be restarted after a trap without reloading the page.

Rust owns bounded image decoding, SVG rendering, selection, tracing, polygon
operations, layouts, solids, validation, packing, and all print-pack formats.
Manifold remains the solid kernel through its Rust bindings, compiled together
with Rust using Emscripten. This avoids a second implementation of 3D booleans.
Raster/SVG renderers may differ at antialiased edges; compatibility is measured
in millimeters, area, volume, topology, material alignment, and layout decisions,
not identical triangle ordering. SVG is an input/derived artifact, never an
intermediate product workflow. No uploaded source is fetched or transmitted.

The same Rust library also powers a native CLI. Python stays available as the
frozen reference and legacy CLI, with its existing tests intact. Browser runtime
assets are static, locally bundled, and cached for offline use after first load.
There are no cloud services, printer operations, or runtime API requirements.

## Verification gates

1. Capture a reproducible Python corpus before implementing the Rust pipeline:
   plaques, raster and SVG selection, holes, profiles, contours, mounting,
   tiles, regular/random puzzles, clearance, packing, invalid settings.
2. Run native Rust comparisons and independently inspect exported meshes using
   Trimesh and XML/ZIP readers. Check closed edges, winding, positive volume,
   holes, dimensions, material separation, packing, and Bambu project metadata.
3. Run the complete existing browser interactions on the static worker engine,
   preserving failure and recovery assertions while replacing HTTP observation
   with the engine's transport-independent completion events.
4. Verify offline generation/downloads, no API/image uploads, worker recovery,
   stale request handling, responsive rendering, and bounded inputs.
5. Run `bash scripts/check.sh`, preserve review artifacts in shared storage,
   and publish the implementation branch for review.

Computational validation does not calibrate puzzle fit or rate mounting strength.
AMS tray mapping and final slicer inspection remain user operations.
