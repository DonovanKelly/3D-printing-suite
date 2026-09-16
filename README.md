# Relief Studio · 3D Printing Suite

Turn a local image into two-color printable wall art. Upload PNG, JPEG, WebP,
or a self-contained SVG, tune its black-and-white conversion, then make a raised
plaque, large tiled panels, or an interlocking puzzle. A browser workbench and
native Rust CLI share the same geometry engine.

**Image contour** makes a single icon-shaped print with an optional flat,
rounded, or beaded bezel. Padding and bezel width expand outward around the
image; no rectangular backing is required.

Implemented: threshold/inversion, preserved negative-space holes, configurable
dimensions and colors, raised borders, top hanging loops, rear keyhole recesses,
size-controlled tiling, repeatable random puzzles, adjustable puzzle clearance,
orbitable assembled/separated 3D previews, assembly map, vector preview, rounded
corners and border edges, and arranged plate 3MF/aligned STL export. The web app
is the primary interface.

## Version 2: entirely in your browser

The workbench runs a Rust geometry engine and Manifold in a WebAssembly worker.
Images, previews, and print packs stay in browser memory. No Python HTTP server,
cloud account, API key, or upload endpoint is used. After the first successful
load on localhost or HTTPS, the application caches its assets for offline reloads.
Keep downloaded print packs: imported images and the current project are not saved
across page reloads. Browser storage eviction can remove the offline cache.

### Build and run

Build requirements: Node 22.12+, Rust 1.98.1, Emscripten 4.0.15, CMake, Git, and a
C++ compiler. On Debian/Ubuntu install `build-essential cmake`; on macOS install
Xcode command-line tools and CMake. The setup script installs the pinned Rust and
Emscripten toolchains into your home directory. Building needs internet access
on first use to fetch dependencies; the built application needs none.

```sh
bash scripts/setup-toolchain.sh
npm --prefix web ci
npm --prefix web run build
npm --prefix web start
```

Open [the local workbench](http://127.0.0.1:8000). `web/dist` is a complete static
site that can also be served by any static host with WebAssembly MIME support.
Use localhost or HTTPS for offline caching; opening `index.html` through `file://`
does not support browser module workers. The supplied Node server serves static
files only and binds to loopback by default.

For UI development, build Wasm once with `npm --prefix web run build:wasm`, then
run `npm --prefix web run dev`. Rebuild Wasm after Rust changes. Service-worker
caching is enabled in production builds, not the Vite development server.

### Native engine and Python reference

The same Rust core builds natively, including for macOS:

```sh
cargo build --locked --release --bin relief-native
./target/release/relief-native --input artwork.svg --settings examples/plaque.json \
  --output print-pack.zip
```

Omit `--input` for the built-in sample; `--preview` prints the browser preview
DTO, and `--defaults` prints settings. Output paths must be new files. The legacy
Python `relief` CLI remains available for reference and existing scripts. Its
installation requires Python 3.12+ and Cairo:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install -e . --no-deps
. .venv/bin/activate
```

### Managed workspace development site

The development container starts a supervised static workbench on port 8000.
It uses the workspace's configured friendly HTTPS address. Frontend edits rebuild
automatically. Close all workbench tabs and reopen to activate a newer offline
cache, or use the Vite dev server for immediate reloads. Run the full build after
Rust changes.

```sh
bash scripts/workspace-preview.sh status
bash scripts/workspace-preview.sh restart
bash scripts/workspace-preview.sh stop
bash scripts/workspace-preview.sh start
```

`RELIEF_PREVIEW_PORT` overrides the port. Downloads go to the browser's download
location; no server export directory is used. Python/Supervisor manages this
development process only; the application itself can run on any static host.
Run `setup` once if development dependencies are missing.

`Cargo.lock`, `web/package-lock.json`, and `requirements-dev.lock` pin the Rust,
frontend, and Python reference dependencies. The full verification command is
`bash scripts/check.sh`; see [testing](docs/testing.md).

## From SVG to two-color 3MF

1. Upload your SVG. **Automatic** foreground selection uses its filled shapes
   and transparent holes regardless of fill color. For an opaque SVG, it uses
   contrast against the perimeter color. Photos use dark pixels by default.
   **Image selection** contains dark/light selection, threshold, inversion,
   and trace detail when you need them. New imports start with Automatic
   selection, threshold 128, and inversion off; geometry and colors are kept.
   Dark/light modes can intentionally select no pixels at some thresholds.
   **Reset image selection** recovers from an empty selection without changing
   your dimensions, border, or hanging settings. Automatic SVG selection also
   normalizes faint opacity and low contrast.
2. Under **Image & background**, set finished width/height, **Image thickness**
   (height above the backing), **Background thickness**, and **Padding** (the
   minimum space inside the border). **Trim empty image space** starts enabled;
   disable it to retain the source canvas margins. Aspect ratio is preserved,
   so two sides may have extra space. Rounded corners can add more inset to
   keep the complete artwork inside the backing. Numeric edits apply on Enter
   or when you leave the field; Escape cancels. Clearing a field temporarily
   is allowed, and leaving it empty restores its previous value. Downloads
   wait until the edit is applied and the new preview is ready.
3. Choose the two **Filament colors**. Background and Image + border remain
   separate aligned material parts in the 3MF.
4. Optionally choose no border, a raised flat border, or a raised border with
   rounded top edges. **Border width** stays visible: 0 removes the border,
   and 0.5–30 mm adds or adjusts its rim. Width and height are independent;
   border height is above the background. Padding controls the gap inside the
   rim. **Corner radius** rounds the outside corners of the design,
   including its backing. Set it to 0 for square corners.
5. Choose **None**, **Top loop · centered**, or **Rear keyholes** for hanging.
   A plaque has one centered loop with a 5 mm opening. Tiles/puzzles have one
   loop on each top-row panel, attached to that panel's actual upper edge even
   with rounded corners. A loop adds up to 9 mm above the backing; allow for it
   within the usable bed height. Rear keyholes automatically raise backing
   thickness to 5 mm when necessary.
   **Print format** chooses a single plaque, tiles, or a puzzle; a multi-piece
   layout clips the same outside border across its panels.
6. When the pieces fit on one plate, click **Download 3MF**. For multiple plates,
   **Download N plates (ZIP)** contains a 3MF for each arranged plate, plus each
   individual piece. **Download full print pack** is always available and
   includes STLs, settings, and an assembly map. Open the 3MF as a project in
   Bambu Studio: Background uses filament 1 and Artwork + frame uses filament 2.
   Map those filaments to your actual AMS trays before printing.

## Make a contour-shaped icon

1. Use the built-in Alpine crest or upload an image, then choose
   **Image & background → Backing shape → Image contour**. The sample has a
   closed curved outline, so it works even with no bezel and zero padding.
   The backing follows the outside of the selected artwork. Enclosed holes get
   background beneath them; the raised image keeps its cutouts and interior details.
2. **Width / Height** limit the image itself in this mode, preserving its aspect
   ratio and centering it. Empty canvas margins are trimmed automatically.
   **Padding** expands the backing around the image; **Border width** expands it
   further. Changing either leaves the image size unchanged. The canvas heading
   reports the actual finished size, including the optional loop.
3. Choose **No border**, **Raised · flat**, **Raised · rounded**, or **Raised · beaded**.
   For a recessed appearance, set **Border height** above **Image thickness**;
   for example 3 mm border with 0.8 mm image thickness. Beads scale with rim
   width and height. Rounded contour tops approximate a curved profile with
   height bands no taller than 0.1 mm; inspect the sliced surface finish.
4. **Hanging** can be None, a centered top loop with a 5 mm opening, or a single
   rear keyhole placed down the centerline where enough backing supports it.
   Rear keyholes need a 5 mm backing and sufficient local width. Increase the
   image size or padding when a narrow icon cannot accommodate the recess.
5. Download a 3MF or full print pack. Contour mode is one piece; Tiles/Puzzle
   are disabled. Bezel, padding, and loop must all fit the usable plate. Reduce
   the image dimensions if the app reports overflow.

Disconnected shapes need enough padding or bezel width to join into one backing;
otherwise the app reports the islands instead of silently dropping them. Select
Rectangle when a common rectangular backing is more appropriate. Rectangular
corner radius and source-canvas margin controls do not affect contour mode.
Mounting strength and Bambu Studio import still require physical/slicer checks.

```sh
relief generate icon.svg --shape contour --width 120 --height 180 \
  --margin 3 --frame-width 6 --frame-height 3 --frame-profile rounded \
  --hanging loops --output output/contour-icon
```

## Make tiles or a random puzzle

Choose **Tiles** or **Puzzle** under **Print format**. Both now split even artwork
that already fits the printer: the 180 mm sample defaults to four tiles or nine
puzzle pieces. **Pieces** opens automatically and shows the cuts with visible
gaps; **Relief** and **Assembly** show how the finished artwork fits together.

- **By piece size** sets a maximum width and height in millimeters, including
  puzzle tabs and hanging loops. The default is 90 mm; choosing 60 mm makes a
  16-piece sample puzzle. Actual pieces can be smaller, especially at corners.
- **Largest panels** makes the fewest panels that fit your usable build plate,
  with at least two pieces. Use this for large wall art and fewer assembly steps.
- **Custom grid** sets the row/column count and overrides Max piece size.
  Actual pieces must still fit the usable bed. A 1 × 1 grid is rejected; use
  Plaque for a single object.
- **Random** varies the tab direction, position, size, and curved seams of a
  jigsaw grid. **Shuffle pattern** changes the seed; the same seed, artwork, and
  settings reproduce the cuts. **Regular** uses alternating tabs on straight
  grid seams. **Clearance** controls the joint gap, independently of piece size.

The print plan reports both pieces and plates. Plate exports place pieces with
a 3 mm gap between their bounding boxes. Every piece is a separate 3MF object,
with aligned background/artwork parts inside it. Open `plates/plate-01.3mf` from
the pack to see its pieces together on a plate. An individual file under
`pieces/` intentionally contains only that one piece. `pieces.svg` labels the
separated set; `assembly.svg` labels their final positions.

## Generate files without a browser

```sh
# No image argument uses the original alpine example.
relief generate --output output/plaque

relief generate photo.png --width 540 --height 540 --layout puzzle \
  --split-mode bed --output output/my-wall-art

relief generate --layout puzzle --piece-size 90 --puzzle-style random \
  --puzzle-seed 1 --output output/random-puzzle

relief generate drawing.svg --settings examples/rear-keyholes.json \
  --output output/keyhole-plaque

python scripts/build_starter_pack.py output/starter-collection
```

Output directories must be new: existing files are never replaced. Use
`--settings project.json` to reuse exported settings with the same source image.
The browser retains its current project in worker memory and creates download
bytes only on an explicit export. Reloading clears the source and preview; keep
downloaded packs in durable storage. Source images are not copied into packs.
Choose a shared directory through your browser's download dialog or pass a new
shared output path to the native CLI. The legacy starter collection includes a
portable review `index.html` and ZIP; it is separate from the interactive app.

## Print with Bambu Studio and AMS

Every pack includes arranged **plate 3MFs** and a grouped **3MF** for each piece,
plus **background.stl**, **artwork.stl** when present, and a boolean-unioned
**combined.stl** per piece. The pack also includes traced SVG, separated and
assembly maps, project settings, a manifest, and `PRINTING.md`.

1. **Open a plate's 3MF as a project** in Bambu Studio. The project starts with
   P1S / 0.4 mm nozzle / 0.20 mm Standard and two Generic PLA filaments in your
   chosen colors: **Background = filament 1**, **Artwork + frame = filament 2**.
   Check the printer, nozzle and material profiles, then map the two filaments
   to your actual AMS trays. Keep each named `rNN-cNN` puzzle piece as a separate
   object. Open additional plate files separately; the app also offers individual
   plate links after export. Geometry-only import discards project settings.
   See [3MF compatibility](docs/3mf-compatibility.md) for the format and checks.
2. If your slicer loses the grouping, import its background and artwork STLs
   **together as one object with multiple parts**. Keep their coordinates;
   moving the artwork to the bed independently destroys the height alignment.
3. Or use combined.stl with a filament change at the first layer above the base.
   Defaults use a 2.4 mm base and 0.8 mm raised art, compatible with 0.2 mm layers.
4. Slice and inspect the build plate, fine details, color assignments, brims,
   and prime tower. Print the small fit pairs before a large assembly.

The P1S's advertised build volume is 256 × 256 × 256 mm. The suite defaults to
an adjustable **230 × 230 mm usable footprint**. It checks actual piece extents,
including tabs and loops; your slicer still decides placement and toolpath fit.
[Bambu specifications](https://bambulab.com/en-us/p1p).

## Current limits

- This is **2.5D relief**, not full 3D reconstruction of a photograph. Photos are
  thresholded; semantic restyling into bold line art is not implemented. Replicate
  is documented as the next optional image-preparation provider; no paid calls
  are made or API credentials required.
- SVG is rendered and retraced at 384/768/1280 pixels, so original Bézier curves
  are not preserved analytically. External resources, scripts, embedded images,
  and stylesheet imports are rejected. Very thin details can be filtered away.
  Artwork is inset by 0.01 mm to separate point-only contacts before extrusion.
- Files are limited to 12 MiB/24 megapixels; layouts to 64 pieces and 1.5 m per
  side. One geometry operation runs at a time. This is a local single-user tool.
- Puzzle joints are complementary in-plane alignment features. **Physical fit
  has not been calibrated**, and they do not secure a large assembly to a wall.
  Use independent mounting for panels. Loops/keyholes are experimental and not
  load-rated. Rear keyholes require at least a 5 mm backing and may need support
  or bridging adjustments. No hardware screw size is assumed to be compatible.
- Export meshes are checked for closure, winding, positive volume, and bed
  extents. The v1 Bambu project format had desktop import/save checks; v2 retains that
  metadata and passes independent package/mesh checks. A fresh v2 desktop slicer
  and physical print test remain to be performed, including actual AMS mapping.
- The app does not persist browser projects across reloads; exported settings
  can be reused through the CLI. It does not slice or send jobs to a printer.

## Development

```sh
bash scripts/check.sh
python -m build --wheel
```

The complete [regression suite](docs/testing.md) includes real desktop/mobile
browser flows and accepts private SVG inputs without committing them. Install
Chromium once with `npm --prefix web exec -- playwright install chromium`.
All verification runs locally through `bash scripts/check.sh`; this repository
does not use hosted CI/CD workflows.

Read [architecture and extension decisions](docs/architecture.md) and
[the design/visual verification record](docs/design/README.md). Source artwork
and sample settings are versioned; generated print packs and compiled assets
are excluded from Git. The project uses frequent validated commits and pushes;
the three-phase feature development workflow does not apply.
