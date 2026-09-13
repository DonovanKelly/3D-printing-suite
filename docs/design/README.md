# Workbench design

`workbench-concept.png` is the initial built-in Image Gen concept. It is a
visual implementation reference, not a screenshot of functioning software.

Brief: a complete 1536×1024 local image-to-two-color-relief editor named Relief
Studio. Header and export action; project title and Relief/Assembly/Vector tabs;
artwork and format controls on the left; large live geometry canvas in the
middle; print plan and filament colors on the right; local-processing footer.
The prompt specified no marketing page, unrelated navigation, or fake metrics.

Tokens: canvas #f5f4f0, panels #fcfcfa, ink #252b28, accent #285f49,
dividers #dedfd8; 8px control radii; clean sans-serif type, 14px controls,
18px section titles, 26px project heading. Outline icons use a consistent 1.7px
stroke. Sidebar controls stack; repeated numeric/select fields share primitives.

Primary allowed copy: Relief Studio, 3D printing suite, Bambu Lab P1S, Export
print pack, Alpine study, Image to two-color relief, Relief, Assembly, Vector,
Artwork, Drop an image or SVG, browse files, Use sample artwork, Threshold,
Invert artwork, Detail, Balanced, Format, Plaque, Tiles, Puzzle, Size (mm),
Width, Height, Frame, Raised border, Hanging, None, Print settings, 3D preview,
Print plan, Ready to make, Pieces, Materials, Base, Relief, Filament colors,
Background, Artwork + frame, Assign these parts to your AMS slots in Bambu
Studio, Fits your build plate, Drag to orbit · Scroll to zoom, Local processing,
Millimeters.

The central artwork is intentionally live, code-native CAD geometry derived
from an original SVG example, rather than the concept's raster depiction.
Functional states add necessary progress/errors, rebuild/export feedback,
layout settings, and print limitations. At narrow widths the canvas comes first
and the same panels follow. The printer label is static until profiles exist.

The image was selected autonomously under the user's request to get started,
without a separate design-approval step.

## Visual verification

The implementation was compared directly with `workbench-concept.png` using
`view_image` on the concept and the latest browser screenshots. Evidence:
[desktop](workbench-rendered.png) and [mobile](workbench-mobile.png).

Playwright CLI drove real Chromium with software WebGL because no Browser/IAB
automation connector was available in this workspace. The desktop was captured
at the concept's native 1536×1024 dimensions; 820×1180 tablet and 390×844 mobile
viewports were also checked. All three had no horizontal overflow. The desktop
footer remains inside the viewport and long inspectors scroll independently.

| Comparison | Evidence and result |
| --- | --- |
| Layout | Header/project rows and 335 px sidebars match the concept's three-column hierarchy; canvas stays dominant. |
| Typography | Locally bundled Inter; deliberate 14 px controls, 18 px section titles, and 25 px project title. Native control defaults were replaced. |
| Palette | Off-white panels, warm gray canvas, charcoal text, and forest-green selected/export states retained. No added gradients or tint overlays. |
| Spacing | Reduced conversion-control gaps after first render and fixed footer overflow; section dividers and control groups now track the reference. |
| Icons | Consistent outline layer/upload/format/zoom/reset icons; buttons have accessible labels and selected states. |
| Geometry | Corrected the initial camera roll and lighting. The visible model is actual export geometry with a true 2.4 mm base and 0.8 mm artwork. |
| Responsiveness | Mobile puts the preview before controls and print plan; tablet retains a control rail. No clipped controls or sideways scrolling. |

Above-the-fold copy was compared with the allowed list. Primary labels, tab
order, section names, and export text match. Intentional functional additions
are `Before you print`, progress/errors, automatic/custom splitting, adjustable
fabrication fields, and the successful-download link. Printer and unit labels
are static rather than misleading dropdowns. The helper `Upload artwork` is
an accessible file-input label, not extra visible copy.

The central sample is an original geometric alpine SVG, not a reconstruction
of the generated concept's detailed raster art. PLA texture is not simulated;
the model has accurate geometry, lighting, and shadows. The canvas uses a
screen-aligned dot grid. These are intentional differences from the concept.
The interface was faithfully verified against the selected layout/design with
these differences recorded; no known material UI mismatch remains.

## Functional verification

Browser checks covered SVG upload, sample reset, dimensions, threshold/inversion,
Relief/Assembly/Vector switching, automatic 540 mm puzzle splitting, loops,
rear keyholes with automatic backing increase, and downloading a real ZIP.
Invalid dimensions block export and identify that the previous valid preview
is still visible. The assembly map uses front-view labels with contrast-backed
text, which remains readable on both artwork colors.

35 Python tests cover topology, settings, imports, material separation, bed
limits, grouped 3MF, the local API, and large-mesh reloads with importer vertex
welding. Every one of the starter collection's 26 grouped 3MFs and 26 combined
STLs was independently reloaded and checked. The built wheel was installed to
an isolated target and its bundled UI/sample/API were smoke-tested.

Known validation limits: no Bambu Studio session or physical printer was
available here. The Dockerfile change was inspected but the full Dev Container
image was not rebuilt. The frontend build reports a large Three.js bundle;
Python test dependencies emit two deprecation warnings. Neither prevents the
checks or local operation.

## SVG extrusion control update

The user's follow-up makes SVG extrusion the primary task. Within the existing
visual system, the inspector now puts Image thickness, Background thickness,
and Padding ahead of optional finishing and partition controls. Conversion
controls move into Image selection. Border & hanging exposes width, height,
rounded top edges, outside corner radius, loops, and rear keyholes. Print
format follows these controls. These requested label/order changes supersede
the initial concept's inspector copy; header, canvas, palette, typography,
three-column layout, and responsive structure are retained.

The primary action is Download 3MF for a single piece; multi-piece layouts keep
Export print pack. A secondary full-pack action remains available in the print
plan. The print plan also shows the applied padding and uses Background/Image
thickness labels matching the inspector. Long border options were shortened
after screenshot inspection to fit their select control.

Latest desktop and mobile screenshots above use the original repository sample
and were checked with view_image against the original concept. Private uploaded
artwork and its review screenshots remain in shared outputs, outside Git.
Desktop 1536×1024, tablet 820×1180, and mobile 390×844 have no horizontal overflow.
The image/background controls are visible in the initial desktop viewport;
finishing controls remain accessible in the independently scrolling inspector.

Browser verification used the actual uploaded transparent, gold-filled SVG:
automatic extrusion, thickness/padding/color edits, a rounded frame, a plain
backing, top loops, rear keyholes (automatically increasing backing to 5 mm),
custom four-piece tiles/puzzles, and assembly view. Both single-piece 3MFs and
full ZIP packs were downloaded through the UI and independently reloaded with
Trimesh; named material colors and z ranges matched the selected settings.
An oversized 400 mm plaque blocked export and recovered after correction.
The only browser console error came from that intentionally invalid HTTP 422.

62 Python tests, Ruff, and the TypeScript/Vite build pass. Tests cover transparent
SVG fill colors, negative-space holes and islands, padding with/without source
margins, rounded border surfaces, rounded tiled/puzzle geometry, optional
mounting, bounded direct 3MF downloads, and material heights/colors. The physical
printing and slicer-validation limits above still apply.

## Size-controlled puzzles and arranged plates

The original Automatic splitter minimized build-plate count, so the 180 mm
sample stayed as one piece even when Tiles or Puzzle was selected. Earlier
browser checks selected a custom grid and did not catch that default-path bug.
Tiles and Puzzle now always split, defaulting to a 90 mm maximum piece size.
The sample produces four tiles or nine random puzzle pieces.

Print format now exposes By piece size, Largest panels, and Custom grid.
Puzzle adds Random/Regular patterns, a reproducible seed, and Shuffle pattern.
The new Pieces tab opens automatically for multi-piece formats and shows actual
meshes with visible separation. The print plan distinguishes piece count from
plate count. One plate downloads directly as a 3MF containing separate objects;
multiple plates download as a ZIP, with individual plate links available after
export. These requested additions supersede the earlier export labels above.

The [puzzle desktop](puzzle-workbench.png) and [mobile](puzzle-mobile.png)
screenshots were inspected with view_image against the original concept.
They retain its typography, palette, dominant live canvas, and inspector
structure. Four preview tabs and the longer multiple-plate download label fit
390 px mobile and 820 px tablet viewports without horizontal overflow. Desktop
inspectors scroll independently, including long plate-download lists.

Playwright drove the sample through default tiles/puzzles, 90 → 60 mm piece
size, seed shuffle, Regular mode, Largest panels, rejected 1 × 1 custom grid,
and recovery to Plaque. Actual UI downloads contained four tiles, nine puzzle
pieces, sixteen smaller puzzle pieces, and a 360 × 180 mm puzzle with 36 pieces
on three plates. Independent XML inspection and Trimesh reload verified separate
build objects, closed positive-volume material meshes, bed bounds, and exactly
one occurrence of every piece across each pack's plate files. The single invalid
grid request produced the expected HTTP 422 console error.

82 Python tests, Ruff, and the TypeScript/Vite build pass. New tests cover the
default sample regression, bounded piece sizes, seeded seam topology/clearance,
reproducibility, measured packing gaps, aligned material transforms, and bounded
plate-download routes. The Bambu Studio and physical-print checks remain pending
on the target machine; a valid 3MF roundtrip does not establish physical fit.
