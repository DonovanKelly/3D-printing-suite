# Legacy Python architecture (v1)

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
  Traced pixel contours use structural shell/hole repair: linework repair can
  turn a touching hole into a filled exterior, flooding a detailed image.
  If a boolean collapses a seam triangle to coincident vertices, weld it and
  remove only triangles with repeated vertex indices, then validate again.
  Do not remove valid skinny triangles from mounting recesses.
- A shared rounded rectangle outline clips all outside panel corners. Rounded
  border tops loft matching corner samples through quarter-circle height
  sections, then clip the closed border solid to the selected layout. Padding
  accounts for the curved corners so fitting never clips the source artwork.
- `shape=contour` fits the selected artwork into width/height image limits with
  no rectangular inset. It always trims source-canvas margins. `contours.py`
  fills exterior rings for the backing, preserving holes in the raised vector;
  round planar offsets add padding and then bezel width outward. Disconnected
  backings fail with a padding/shape recovery hint; no convex hull or largest-
  island shortcut is used. Contours require `layout=plaque` at the settings
  boundary, and actual expanded bounds (including mounting) must fit the bed.
- Contour rounded rims use nested inward offsets in height bands of at most
  0.1 mm, allowing topology changes at concave corners. The rectangular rounded
  profile keeps its existing loft. Beaded rims place bounded sphere caps along
  an offset contour and clip them to the rim prism; bead pitch grows if needed
  to bound complexity. Border height above relief gives a recessed appearance.
  Both profiles stay in the existing artwork material, touching only the base.
- Contour rear mounting searches down the actual centerline for one supported
  keyhole; rectangles retain paired keyholes. Top-loop anchors use actual shape
  bounds. Decorative solids are clipped when a loop cuts into the original
  footprint so the raised rim cannot refill the mounting hole. Preview framing,
  2D output, print notes, and material exports use actual contour bounds.
- Top hanging uses one loop centered on each top-row panel. A vertical section
  finds the panel's actual upper edge before adding its ring; attaching paired
  loops at the design's global top could disconnect them on large corner radii.
  The opening is cut after union so sloping backing cannot fill its 5 mm hole.
- A base occupies z=0..base thickness. Artwork and border occupy separate
  non-overlapping volumes above it. Each tile is a grouped, two-material 3MF
  with preserved relative coordinates, plus aligned STL parts. A single merged
  STL is also available for a height-based color change.
- Tiles and puzzles always require at least two pieces. Automatic splitting
  tries grids from fewest pieces upward and checks actual extents including
  tabs and hanging features. By piece size uses the smaller of the requested
  maximum (90 mm by default) and the usable bed; Largest panels uses the bed.
  Explicit grids override piece size but retain the bed check. Nominal cells
  must be at least 24 mm, and all layouts are limited to 64 pieces.
- Random puzzle seams transfer a shared curved strip and tab between neighbors,
  preserving total coverage and avoiding overlaps before clearance is applied.
  A local seeded generator varies tab direction, location, radius, and seam
  curvature; settings record the seed for reproduction. Regular mode retains
  alternating circular tabs. Rear keyhole placement searches within each
  nominal cell for sufficient material, away from random edge sockets.
- A shared packing module separates actual piece bounding boxes by 3 mm. It
  retains assembly row/column order when that fits one plate; otherwise stable
  height-sorted shelves distribute every piece exactly once across plates.
  One 3MF build item references each piece's component group, so the file has
  separate movable objects while each object's material parts stay aligned.
  Translations are shared by both materials; plates do not change Z placement.
  The usable footprint defaults to 230 mm square; packing is not a guarantee
  of slicer placement with brims, exclusion zones, and prime towers.
- Local API requests are bounded and serialized during generation. No cloud
  uploads, credentials, paid calls, or printer commands are implicit. The
  service binds to loopback by default and is intended for a trusted local user.
- Numeric fields retain a local draft until blur or Enter, with Escape/empty
  blur restoring the applied value. An unapplied draft disables downloads.
  This avoids sending incomplete numbers (for example the first `1` in `180`)
  through geometry validation. Committed invalid settings still fail at the
  shared Python boundary, with the affected control named in the response.
- Completed exports are self-contained, with settings, SVG, assembly map,
  geometry checks, and print instructions. CLI output uses a new directory;
  browser generation uses unique directories with failed work cleaned up.
  Single-plate export returns a direct 3MF URL, including multi-piece plates.
  Larger jobs return one URL per plate and a full ZIP. Piece/plate downloads
  validate the export UUID and a bounded filename and serve only saved files.
  The separate-pieces preview and labeled SVG share the same layout calculation.

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
[Bambu Studio 3MF importer](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/Format/bbs_3mf.cpp),
[P1 series specifications](https://bambulab.com/en-us/p1p),
[Bambu print-volume limitations](https://wiki.bambulab.com/en/knowledge-sharing/print-volume-limitations),
[Replicate API](https://replicate.com/docs/reference/http).
