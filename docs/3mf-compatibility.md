# 3MF and Bambu Studio compatibility

Open exported 3MFs as **projects** in Bambu Studio. Background uses logical
filament 1; artwork uses filament 2. The border either joins the background or
artwork part, or uses a separate Border part on logical filament 3. The project starts with installed
P1S / 0.4 mm nozzle / 0.20 mm Standard / Generic PLA profiles. Check those choices
against your hardware and map the filaments to actual AMS trays before printing.
Geometry-only import does not retain the supplied project settings.

Plate groups are centered on the P1S's 256 mm bed and shifted together when
needed to clear its front-left 18 × 28 mm exclusion rectangle by 5 mm. Manifest
plate origins match the exported positions; assembly maps retain their original
coordinates. A layout that cannot clear the exclusion zone is rejected with a
size-reduction message. The default 230 mm usable bed fits this constraint.
Brims and prime towers still need clearance in the sliced preview.

## Why the old export failed

The old ZIP contained valid core geometry and base-material display colors,
but no Bambu project configuration. Studio reported:

> The 3mf file has invalid config, load geometry data only

That message describes configuration import, not a broken mesh. Core display
colors alone do not assign Bambu project filaments. The exporter now includes
the following layers:

| Archive part | Purpose |
| --- | --- |
| `[Content_Types].xml`, `_rels/.rels` | OPC content types and relationship to the root model. Explicit XML/JSON content types cover the extra configuration parts. |
| `3D/3dmodel.model` | Millimeter coordinates, outward-wound closed meshes, two or three base materials, one component group/build item per piece, and plate placement transforms. |
| `Metadata/model_settings.config` | Piece names, mesh component IDs, `normal_part` types, filament numbers 1/2/3, and plate instance membership. |
| `Metadata/project_settings.config` | Two or three configurable filament colors, PLA profiles, and **one** physical nozzle. |

Studio only reads project settings when the model's `Application` metadata
starts with `BambuStudio-` followed by a parseable version. We use
`BambuStudio-02.00.00.00` as the compatibility marker for the supported project
layout and identify Relief Studio as the actual generator in `Description`.
This marker alone is insufficient: the configuration parts must exist and
reference the actual mesh objects. No painting, printer connection, toolpath,
or physical AMS tray assignment is embedded.

Preset names and `inherits_group` resolve Studio's installed system profiles;
`different_settings_to_system` retains the selected colors while allowing
the installed printer/material settings to supply their current defaults.
The export does not copy machine start/end G-code into the project. Projects
still require installed Bambu profiles and a slicer review before printing.

## Verification

Always-on Python tests inspect both piece and plate packages, colors, nozzle
count, part IDs, plate references, and geometry. Coverage includes plaques,
tiles, puzzles, identical display colors that must remain distinct filaments,
and a background-only piece. Rust export checks cover independent border parts,
all border profiles, contour shapes, hanging, and interior puzzle/tile pieces
without a border. Every part retains its logical filament index, even when a
piece has no artwork or border. Palette, preset, and inheritance arrays are sized
consistently; there is still one physical nozzle. Pairwise material intersections
have no volume, and their volumes sum to the unchanged combined mesh.
The browser tests inspect a downloaded three-filament project and saved-workspace
round trips. Actual AMS tray mapping and a fresh three-color desktop slicer/print
check remain manual steps. The legacy API tests check two-color downloads.

To also run the real Bambu Studio import/export regression:

```sh
RELIEF_TEST_BAMBU=/absolute/path/to/bambu-studio bash scripts/check.sh
```

For an extracted Linux AppImage, use its `AppRun` path so the bundled libraries
are found. The regression uses temporary configuration/output directories and
never connects to a printer. It reproduces the old one-filament import, imports
the corrected export, saves it through Studio, and checks the saved colors,
part assignments, mesh-repair counts, and each material's bounds and volume.
It covers both a plaque and a puzzle plate. Bambu's saved Production-extension
subfiles are read by `(path, objectid)`; treating an entire subfile as one mesh
would combine different material parts and give incorrect bounds.

The desktop open flow was also checked in Bambu Studio 2.8.2.61 on Linux with
the installed P1S profile. The original warning was reproduced, then the
corrected project opened with two colored Generic PLA entries and named parts.
The 90 mm Alpine sample sliced successfully with both filaments and one filament
change. This was a computational slicer check, not a physical print.

The command-line check does not exercise desktop dialogs, actual AMS mapping,
or physical printing. Desktop import must also be checked when changing the
format marker or project settings.

## Primary references

- [3MF Consortium Core specification](https://github.com/3MFConsortium/spec_core/blob/master/3MF%20Core%20Specification.md): package relationships, mesh rules, materials, components and build transforms.
- [Bambu Studio 2.8.2 importer/exporter](https://github.com/bambulab/BambuStudio/blob/v02.08.02.61/src/libslic3r/Format/bbs_3mf.cpp): `_handle_end_metadata`, `_load_model_from_file`, `_generate_volumes_new`, and `_add_model_config_file_to_archive` define version gating and part metadata.
- [Bambu Studio desktop import](https://github.com/bambulab/BambuStudio/blob/v02.08.02.61/src/slic3r/GUI/Plater.cpp): `check_project_config` and the geometry-only fallback explain the reported warning.
- [Bambu Studio preset resolution](https://github.com/bambulab/BambuStudio/blob/v02.08.02.61/src/libslic3r/PresetBundle.cpp): `load_config_file_config` splits project settings into printer, process and filament profiles.
