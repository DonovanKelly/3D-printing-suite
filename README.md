# Relief Studio · 3D Printing Suite

Turn a local image into two-color printable wall art. Upload PNG, JPEG, WebP,
or a self-contained SVG, tune its black-and-white conversion, then make a raised
plaque, large tiled panels, or an interlocking puzzle. A browser workbench and
CLI share the same geometry engine.

Implemented: threshold/inversion, preserved negative-space holes, configurable
dimensions and colors, raised borders, top hanging loops, rear keyhole recesses,
automatic or manual tiling, adjustable puzzle clearance, orbitable 3D preview,
assembly map, vector preview, and grouped 3MF/aligned STL export.

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

`requirements-dev.lock` records the tested Python environment; use
`pip install -r requirements-dev.lock` then `pip install -e . --no-deps` for those
versions. `web/package-lock.json` locks the frontend dependencies.

## Generate files without a browser

```sh
# No image argument uses the original alpine example.
relief generate --output output/plaque

relief generate photo.png --width 540 --height 540 --layout puzzle \
  --output output/my-wall-art

relief generate drawing.svg --settings examples/rear-keyholes.json \
  --output output/keyhole-plaque

python scripts/build_starter_pack.py output/starter-collection
```

Output directories must be new: existing files are never replaced. Use
`--settings project.json` to reuse exported settings with the same source image.
The browser retains only four recent previews in memory; it writes a persistent
pack only when **Export print pack** is pressed. Restarting clears previews,
but exported folders remain under `output/projects` or the `--output-root`
directory. User images are not copied into exported packs.

To send exports to a mounted shared directory, run
`relief serve --output-root /shared/relief-studio/projects` or pass a new shared
directory to the CLI. The starter collection includes a portable `index.html`,
which can be opened directly on another computer, plus a ZIP of the collection.

## Print with Bambu Studio and AMS

Every piece includes a grouped **3MF**, **background.stl**, **artwork.stl** when
present, and a boolean-unioned **combined.stl**. The pack also includes traced
SVG, assembly SVG/PNG, project settings, a manifest, and `PRINTING.md`.

1. Import a piece's 3MF as a model. Assign **Background** and **Artwork + frame**
   to your chosen AMS filaments. Display colors are hints; automatic AMS slot
   selection is not embedded.
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
python -m pytest
ruff check .
npm --prefix web run build
python -m build --wheel
```

Read [architecture and extension decisions](docs/architecture.md) and
[the design/visual verification record](docs/design/README.md). Source artwork
and sample settings are versioned; generated print packs and compiled assets
are excluded from Git. The project uses frequent validated commits and pushes;
the three-phase feature development workflow does not apply.
