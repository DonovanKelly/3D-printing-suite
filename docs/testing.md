# Regression checks

Run the complete suite from the repository:

```sh
bash scripts/check.sh
```

It runs Ruff, all Python tests, TypeScript checks for browser tests, the production
frontend build, and Playwright tests in real Chromium at desktop and mobile
sizes. A failed check returns a nonzero exit status. Tests do not retry failures
into a pass. The suite does not contact a printer or an image-generation service.

Install the normal development dependencies first. Install the browser once:

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
| Image selection | Transparent SVG fills in black, white, gold, and gray; faint opacity; opaque low-contrast images; fractional viewport edges; nested holes and islands; threshold endpoints; dark/light selection and inversion; every trace detail. Blank input remains an explicit error. |
| Fabrication | 54 combinations of plaque/tiles/puzzle, no/flat/rounded border, no/loop/keyhole mounting, portrait/landscape dimensions, border width/height, backing/relief thickness, padding, radius, and random seed. Closed positive volumes, connected backing, aligned materials, and bed bounds are checked. |
| Partitions and exports | Default sample splitting, piece-size limits including tabs/loops, seed reproducibility, complementary seams, clearance, plate gaps, every piece exactly once, separate 3MF build objects, material transforms, independent 3MF/STL reloads, and bounded download paths. |
| Local API | Invalid settings/uploads, unsupported SVG resources, local-origin boundaries, empty-selection recovery, successful exports after errors, and multiple-plate downloads. |
| Real browser | Fresh imports reset incompatible selection without changing geometry; empty selections offer recovery; numeric drafts and cancellation; invalid-export blocking; borders/loops; tiles/puzzles/size/shuffle; actual 3MF/ZIP downloads; out-of-order responses; busy-worker retry; server-error recovery; preview modes; desktop/mobile overflow. |

The browser suite starts its own local Python server on port 8011 and uses a
temporary export directory. It refuses to reuse an existing server, so it cannot
attach to a user's live workbench. Set `RELIEF_TEST_PORT` if that port is occupied.
Each test gets a fresh browser context; one worker matches the local API's
serialized geometry queue. The compiled frontend must exist when running only
`npm --prefix web run test:e2e`; the full script builds it automatically.

Reports are written to `output/verification/python.xml` and
`output/verification/browser.json`. Failed browser cases retain screenshots and
Playwright traces under `output/verification/browser-artifacts`; intentional
recovery screenshots and downloaded files are also kept there. These outputs
are ignored by Git. To inspect a trace:

```sh
npm --prefix web exec -- playwright show-trace /absolute/path/to/trace.zip
```

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
detail, tiles, and puzzles. Reports and failure screenshots from these runs may
contain private artwork; preserve them in shared storage, outside Git.

## Continuous integration and regression policy

`.gitea/workflows/checks.yaml` runs the same command on pushes and pull requests
using Python 3.12 and Node 22. Remote execution requires Repository Actions to
be enabled and an `ubuntu-latest` runner to be available. Adding the workflow
does not itself configure that server-side runner. Local pass results and a
remote CI result must be reported separately.

For a reported bug, reproduce it first, preserve a small synthetic regression
fixture or use the optional private-input path, and add the failing interaction
or geometry invariant to this suite. Keep failure/recovery cases; do not relax
assertions or skip a regression just to make the run pass.

Tests cannot prove arbitrary inputs are printable or establish physical joint
fit, mounting strength, fine-feature printability, AMS slot assignment, or Bambu
Studio behavior. A settings error that safely blocks an impossible print is
expected; losing valid artwork or exporting a stale preview is a regression.

References: [Playwright test-owned servers](https://playwright.dev/docs/test-webserver),
[Gitea Actions setup](https://docs.gitea.com/usage/actions/quickstart/).
