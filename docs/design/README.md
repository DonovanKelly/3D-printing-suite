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

Verification evidence and intentional deviations will be recorded here after
browser testing. The image was selected autonomously under the user's request
to get started, without a separate design-approval step.
