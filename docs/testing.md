# Regression checks

Run the complete suite from the repository:

```sh
bash scripts/check.sh
```

It runs Rust formatting/Clippy/native tests, Ruff, all Python reference and Rust
export-comparison tests, TypeScript checks, the production Wasm/frontend build,
and Playwright tests in real Chromium at desktop and mobile
sizes. A failed check returns a nonzero exit status. Tests do not retry failures
into a pass. The suite does not contact a printer or an image-generation service.

Install the build toolchains with `bash scripts/setup-toolchain.sh` and the
Python reference dependencies first. Install the browser once:

```sh
npm --prefix web ci
npm --prefix web exec -- playwright install chromium
```

On Linux, `playwright install --with-deps chromium` also installs required system
libraries. The Python environment must contain this project and the dependencies
in `requirements-dev.lock`. The default interpreter is `.venv/bin/python`;
`RELIEF_TEST_PYTHON` overrides it with an absolute path.

## Coverage

| Layer | Failure cases covered |
| --- | --- |
| Image selection | Transparent SVG fills in black, white, gold, and gray; faint opacity; opaque low-contrast images; fractional viewport edges; nested holes and islands; threshold endpoints; dark/light selection and inversion; every trace detail. Touching pixel contours cannot flood negative space during repair. Blank input remains an explicit error. |
| Fabrication | 54 combinations of plaque/tiles/puzzle, no/flat/rounded border, no/loop/keyhole mounting, portrait/landscape dimensions, border width/height, backing/relief thickness, padding, radius, and random seed. Closed positive volumes, connected backing, aligned materials, and bed bounds are checked. |
| Contour icons | Built-in Alpine crest with zero padding/no bezel at every detail, decorative bezels and mounts, direct browser selection and sample-button recovery after disconnected artwork. Synthetic concave icon with image holes; no/flat/rounded/beaded bezel and every mount; outward padding/width without image resizing; disconnected-island rejection and recovery; narrow rear mount rejection and recovery; bezel/loop bed overflow; single-piece validation; independent 3MF/STL reload and actual preview bounds. Optional private sources exercise each contour bezel. |
| Partitions and exports | Default sample splitting, piece-size limits including tabs/loops, seed reproducibility, complementary seams, clearance, plate gaps, every piece exactly once, separate 3MF build objects, material transforms, independent 3MF/STL reloads, and bounded download paths. |
| Local API | Invalid settings/uploads, unsupported SVG resources, local-origin boundaries, empty-selection recovery, successful exports after errors, and multiple-plate downloads. |
| Real browser | Fresh imports reset incompatible selection without changing geometry; empty selections offer recovery; numeric drafts and cancellation; invalid-export blocking; borders/loops; tiles/puzzles/size/shuffle; actual 3MF/ZIP downloads; out-of-order responses; serialized-worker queue; worker-error recovery; offline reload/import/download; 64-piece overflow/recovery; preview modes; desktop/mobile overflow. |
| Workspace files | Editable/sanitized filenames; exact artwork/settings/tab round trips into a fresh offline tab; corrupt, oversized, and future-version documents preserve current work; replacement cancellation; optional reload/new-tab recovery and removal; unavailable browser storage; import with a focused name; unfinished settings save/open/repair. |

The browser suite starts its own Node static server on port 8011. It has no
geometry/upload/export endpoints; downloads are browser Blob bytes. It refuses to reuse an existing server, so it cannot
attach to a user's live workbench. Set `RELIEF_TEST_PORT` if that port is occupied.
Each test gets a fresh browser context and its own serialized Wasm worker. The compiled frontend must exist when running only
`npm --prefix web run test:e2e`; the full script builds it automatically.

Reports are written to `output/verification/python.xml` and
`output/verification/browser.json`. Failed browser cases retain screenshots and
Playwright traces under `output/verification/browser-artifacts`; intentional
recovery screenshots and downloaded files are also kept there. These outputs
are ignored by Git. To inspect a trace:

```sh
npm --prefix web exec -- playwright show-trace /absolute/path/to/trace.zip
```

## Rust compatibility reference

`tests/fixtures/reference-v1.json` freezes 33 cases from Python commit `9d79cce`.
`tests/test_rust_engine.py` compares native results and independently reopens all
STLs and 3MFs. It requires `cargo build --release --bin relief-native` first;
`check.sh` performs this automatically. Reference regeneration is explicit:
`.venv/bin/python scripts/reference_corpus.py`. Do not regenerate it to hide a
port regression. Native tests in `crates/relief-core/tests` exercise additional
selection, resource, mounting, and seam invariants.

## Bambu Studio import

Set `RELIEF_TEST_BAMBU` to an absolute Bambu Studio executable or extracted
AppImage `AppRun` path to enable real import/save checks in the same suite.
They exercise the original geometry-only failure and corrected two-filament
projects, including per-part mesh integrity and placement after saving in Studio.
Without this optional executable, package/configuration and independent mesh
tests still run. See [3MF compatibility](3mf-compatibility.md) for the format
contract and desktop verification procedure.

## Private source artwork

The committed gold cutout fixture is original synthetic artwork. User uploads
are not copied into Git. Exercise your own SVGs in both Python and browser tests:

```sh
RELIEF_TEST_ARTWORK=/absolute/path/to/drawing.svg bash scripts/check.sh
```

Multiple paths may be separated with the platform's path separator (`:` on
Linux/macOS). Optional private tests are skipped when no path is supplied; the
public regression suite still runs in full. Private tests cover import after
incompatible selection, extrusion, border changes, rounded hanging, inversion,
detail, tiles, puzzles, and contour bezels with hanging. Reports and failure
screenshots from these runs may contain private artwork; preserve them in shared storage, outside Git.

## Local regression policy

All verification runs locally with `bash scripts/check.sh`; this repository
does not use hosted CI/CD workflows. Report the command and its result with
each change.

For a reported bug, reproduce it first, preserve a small synthetic regression
fixture or use the optional private-input path, and add the failing interaction
or geometry invariant to this suite. Keep failure/recovery cases; do not relax
assertions or skip a regression just to make the run pass.

Tests cannot prove arbitrary inputs are printable or establish physical joint
fit, mounting strength, fine-feature printability, AMS slot assignment, or Bambu
Studio behavior. A settings error that safely blocks an impossible print is
expected; losing valid artwork or exporting a stale preview is a regression.

Reference: [Playwright test-owned servers](https://playwright.dev/docs/test-webserver).
