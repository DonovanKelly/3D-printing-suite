# Relief Studio · 3D Printing Suite

Turn a local image into two-color printable wall art. Upload PNG, JPEG, WebP,
or a self-contained SVG, tune its black-and-white conversion, then make a raised
plaque, large tiled panels, or an interlocking puzzle. A browser workbench and
CLI share the same geometry engine.

Implemented: threshold/inversion, preserved negative-space holes, configurable
dimensions and colors, raised borders, top hanging loops, rear keyhole recesses,
size-controlled tiling, repeatable random puzzles, adjustable puzzle clearance,
orbitable assembled/separated 3D previews, assembly map, vector preview, rounded
corners and border edges, and arranged plate 3MF/aligned STL export. The web app
is the primary interface.

## Run locally

Requires Python 3.12+, Node 22.12+, and Cairo. The Dev Container includes Python,
Node, and Cairo. For another Debian/Ubuntu environment, install `libcairo2`;
on macOS install Cairo with `brew install cairo` and use Python 3.12 or later.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
npm --prefix web ci
npm --prefix web run build
relief serve
```

Open [the local workbench](http://127.0.0.1:8000). In a remote workspace,
forward port 8000 through your workspace tooling before opening that address
on another machine. The default server is loopback-only and has no multi-user
authentication. Do not expose it publicly. No image leaves the local service.

For frontend development, leave the Python server on port 8000 and run
`npm --prefix web run dev`; Vite on port 5173 proxies `/api` to Python. Override
ports in isolated workspaces as needed. The server serves the compiled frontend
from the Python package, so a wheel built after the frontend includes the UI.

### Managed workspace development site

The Dev Container installs dependencies on creation and starts a supervised
preview on port 8000 whenever the container starts. The Compose command and
DevPod startup hook both use the same idempotent service controller. Dioikeo registers the
workspace's friendly `.local` HTTPS address; use the URL shown by its connections
view. The preview serves the UI and API together, rebuilds frontend assets after
edits (reload the browser to see them), and restarts a failed server automatically.
Restart after Python changes. No Mac port forwarding is needed.

```sh
bash scripts/workspace-preview.sh status
bash scripts/workspace-preview.sh restart
bash scripts/workspace-preview.sh stop
bash scripts/workspace-preview.sh start
```

The service runs as the workspace user. Its control socket and bounded logs live
under `~/.local/state/relief-preview-*`, and exports go to
`/shared/relief-studio/projects` when shared storage is mounted. Otherwise they
use this checkout's `output/projects`. `RELIEF_PREVIEW_PORT` and
`RELIEF_OUTPUT_ROOT` can override these defaults before the first start.
`RELIEF_PUBLIC_ORIGIN` defaults to the managed user's friendly HTTPS `.local`
URL; it permits browser generation through the proxy while rejecting other
origins. Set it explicitly if your workspace uses a different URL. Keep
this unauthenticated development service on the trusted local OrbStack network.
The supervisor is pinned in the project virtual environment, so service startup
does not depend on a package installed in a container's replaceable filesystem.
For an existing workspace, run `setup` once if its dependencies are missing,
then run `start`.

`requirements-dev.lock` records the tested Python environment; use
`pip install -r requirements-dev.lock` then `pip install -e . --no-deps` for those
versions. `web/package-lock.json` locks the frontend dependencies.

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
   includes STLs, settings, and an assembly map. Assign the named parts to your
   chosen AMS slots in Bambu
   Studio; the file's display colors do not automatically select slots.

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
The browser retains only four recent previews in memory; it writes a persistent
pack only when a download/export button is pressed. Restarting clears previews,
but exported folders remain under `output/projects` or the `--output-root`
directory. User images are not copied into exported packs.

To send exports to a mounted shared directory, run
`relief serve --output-root /shared/relief-studio/projects` or pass a new shared
directory to the CLI. The starter collection includes a portable `index.html`,
which can be opened directly on another computer, plus a ZIP of the collection.

## Print with Bambu Studio and AMS

Every pack includes arranged **plate 3MFs** and a grouped **3MF** for each piece,
plus **background.stl**, **artwork.stl** when present, and a boolean-unioned
**combined.stl** per piece. The pack also includes traced SVG, separated and
assembly maps, project settings, a manifest, and `PRINTING.md`.

1. Import a plate's 3MF as models. Keep each named `rNN-cNN` puzzle piece as a
   separate object; do not merge the entire plate into one object. Within each
   piece, assign **Background** and **Artwork + frame** to your chosen AMS
   filaments. Display colors are hints; automatic AMS slot selection is not
   embedded. Open additional plate files separately when the pack has more
   than one. The app also offers individual plate links after export.
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
  extents. 3MF is independently reloaded in tests, but Bambu Studio import and
  a physical print still need confirmation on the target machine.
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
The Gitea workflow runs the same checks on pushes/PRs when a runner is configured.

Read [architecture and extension decisions](docs/architecture.md) and
[the design/visual verification record](docs/design/README.md). Source artwork
and sample settings are versioned; generated print packs and compiled assets
are excluded from Git. The project uses frequent validated commits and pushes;
the three-phase feature development workflow does not apply.
