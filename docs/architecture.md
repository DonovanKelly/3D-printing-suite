# Relief Studio: first delivery

The working product is a local browser workbench plus a scriptable CLI. It
creates raised 2.5D artwork, not reconstructed full 3D objects. Both entrypoints
call one deterministic image → planar geometry → partition → extrusion → export
pipeline. Python owns geometry; React and Three.js render actual output meshes.

## Decisions

- Pillow handles raster orientation and transparency; CairoSVG renders a
  restricted self-contained SVG input. OpenCV traces a bounded-resolution
  binary mask, including nested holes. SVG input is normalized through the same
  trace so colors, strokes, and transforms work consistently. Analytic SVG
  curve preservation is a future improvement.
- Automatic SVG selection uses opacity for transparent canvases and contrast
  against the perimeter color for opaque canvases. Bright artwork is therefore
  extruded without manually darkening it. Explicit dark/light pixel selection
  remains available. Fitting trims empty margins by default and preserves the
  image's proportions within the requested padding and border.
- Shapely owns polygon topology, clipping, frames, and complementary puzzle
  edges. Manifold normalizes and extrudes contours; Trimesh validates and exports
  meshes. Manifold performs necessary solid unions
  and rear mounting recess subtraction. Every exported solid must be closed
  and have positive volume.
  A 0.01 mm artwork inset separates point-only contacts. Validation also checks
  a vertex-welded copy, matching the normalization performed by common importers.
  If a boolean collapses a seam triangle to coincident vertices, weld it and
  remove only triangles with repeated vertex indices, then validate again.
  Do not remove valid skinny triangles from mounting recesses.
- A shared rounded rectangle outline clips all outside panel corners. Rounded
  border tops loft matching corner samples through quarter-circle height
  sections, then clip the closed border solid to the selected layout. Padding
  accounts for the curved corners so fitting never clips the source artwork.
- A base occupies z=0..base thickness. Artwork and border occupy separate
  non-overlapping volumes above it. Each tile is a grouped, two-material 3MF
  with preserved relative coordinates, plus aligned STL parts. A single merged
  STL is also available for a height-based color change.
- Automatic tiling tries grids from fewest pieces upward and checks actual
  extents including tabs and hanging features. A user-selected usable footprint
  defaults to 230 mm square; it is not a guarantee of slicer placement with
  brims, exclusion zones, and prime towers.
- Local API requests are bounded and serialized during generation. No cloud
  uploads, credentials, paid calls, or printer commands are implicit. The
  service binds to loopback by default and is intended for a trusted local user.
- Completed exports are self-contained, with settings, SVG, assembly map,
  geometry checks, and print instructions. CLI output uses a new directory;
  browser generation uses unique directories with failed work cleaned up.
  Single-piece export also returns a direct 3MF URL. Piece downloads validate
  both the export UUID and a bounded piece filename and serve only saved files.

## Scope and validation

Deliver import, threshold/inversion, a raised border, optional top loops or rear
keyhole recesses, rectangular and jigsaw partitions, selectable colors, live
preview, and downloadable print packs. Test topology, hollow regions, layout
coverage and clearance, actual build plate limits, mesh volume/winding, export
units/components, malformed input, and an end-to-end browser download.

Print fit remains experimental until a calibration pair is printed. Puzzle
edges align pieces in-plane; they are not a load-rated wall attachment. Rear
keyholes require sufficient backing thickness and may need support depending
on slicer bridging. The suite exports geometry, not sliced printer jobs.

## Later extensions

1. Replicate provider adapter with explicit model/version, model-specific input
   schema, cost confirmation, cancellation, and persistent local output. Do not
   assume every image model emits printable SVG. Stylize first, then trace.
2. Analytic SVG import, manual cleanup, minimum-feature visualization.
3. Additional frame profiles, connector-only wall panels, calibrated mounting hardware.
4. Project library and richer image generation variants.

References: [Trimesh extrusion](https://trimesh.org/trimesh.creation.html),
[Manifold booleans](https://trimesh.org/trimesh.boolean.html),
[3MF core specification](https://github.com/3MFConsortium/spec_core),
[P1 series specifications](https://bambulab.com/en-us/p1p),
[Bambu print-volume limitations](https://wiki.bambulab.com/en/knowledge-sharing/print-volume-limitations),
[Replicate API](https://replicate.com/docs/reference/http).
