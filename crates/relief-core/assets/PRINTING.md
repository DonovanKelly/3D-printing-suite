1. Open plates/plate-01.3mf as a PROJECT in Bambu Studio. Open additional plate
   files separately. Each named piece is a separate object; its background,
   artwork, and optional third-color border remain grouped with their relative
   heights intact. Plates have at least 3 mm between bounding boxes and avoid
   the P1S front-left exclusion zone. Brims and prime towers still need space.
2. The project uses P1S / 0.4 mm nozzle / 0.20 mm Standard and Generic PLA
   filaments. Background = filament 1; Artwork = filament 2. The border joins
   the chosen background/artwork material, or uses filament 3 for a third color.
   See the logical filament list above, check the profiles, and map the logical
   filaments to actual AMS trays in Studio. An absent border adds no third slot.
3. If your slicer loses grouping, import background.stl, artwork.stl and
   border.stl (when present) TOGETHER as one object with multiple parts. Preserve
   shared coordinates; do not drop raised parts to the bed independently.
   combined.stl is a single-material fallback without color assignments.
   Inspect the sliced layer preview. STL is unitless; import in millimeters.
4. Lay the flat back on the bed. Inspect the first layer, small features, top
   surfaces, brim, and prime tower. Slice every piece before printing.
5. Use assembly.svg/preview.png as a FRONT view. Row 01 is the top; labels are
   on the map, not embossed on parts. pieces.svg shows separated pieces. Saved
   puzzle_seed and puzzle_style reproduce the cut pattern. Tabs and loops are
   included in size-based splitting; a custom grid overrides maximum piece size.
6. Width/height constrain the image in contour mode: padding, bezel, and hanging
   expand the finished piece. Use manifest.json for actual piece extents.

Material volumes touch without overlapping. combined.stl is a boolean union.
Puzzle fit has NOT been physically calibrated. Print a small fit pair first.
Tabs align pieces in-plane and do not replace individual panel mounting.
Hanging features are experimental and not load-rated. Rear keyholes may need
bridging/support tuning. Do not rely on top-row loops to hold a large assembly.

Reproduce with project.json and the same source image. The source is not copied
into the pack; manifest.json records its SHA-256. No printer jobs are generated.
