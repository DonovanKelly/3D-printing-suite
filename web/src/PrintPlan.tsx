/** Summarize the last valid geometry and expose material colors and fabrication notes. */
import { Check, Download, LoaderCircle, TriangleAlert } from "lucide-react";
import type { Preview, Settings, Update } from "./types";
import { fileStem } from "./workspace";

export function PrintPlan({
  preview,
  settings,
  update,
  ready,
  busy,
  download,
  downloadName,
  plateDownloads,
  projectName,
  disabled,
  exportPack,
}: {
  preview: Preview | null;
  settings: Settings;
  update: Update;
  ready: boolean;
  busy: boolean;
  download: string;
  downloadName: string;
  plateDownloads: string[];
  projectName: string;
  disabled: boolean;
  exportPack: () => void;
}) {
  const manifest = preview?.manifest;
  return (
    <aside className="print-plan" aria-label="Print plan">
      <section>
        <h2>Print plan</h2>
        <p className="plan-subtitle" aria-live="polite">
          {ready
            ? "Ready to make"
            : busy
              ? "Building your preview…"
              : "Preview needs an update"}
        </p>
        <dl className="metrics">
          <div>
            <dt>Pieces</dt>
            <dd>{manifest?.piece_count ?? "—"}</dd>
          </div>
          <div>
            <dt>Print plates</dt>
            <dd>{manifest?.plate_count ?? "—"}</dd>
          </div>
          <div>
            <dt>Materials</dt>
            <dd>
              {manifest
                ? Math.max(...manifest.pieces.map((p) => p.material_parts))
                : "—"}
            </dd>
          </div>
          <div>
            <dt>Background</dt>
            <dd>{manifest ? `${manifest.settings.base_mm} mm` : "—"}</dd>
          </div>
          <div>
            <dt>Image thickness</dt>
            <dd>{manifest ? `${manifest.settings.relief_mm} mm` : "—"}</dd>
          </div>
          <div>
            <dt>Padding</dt>
            <dd>{manifest ? `${manifest.settings.margin_mm} mm` : "—"}</dd>
          </div>
        </dl>
        {manifest && manifest.piece_count > 1 && (
          <p className="hint grid-summary">
            {manifest.grid.columns} columns × {manifest.grid.rows} rows · view
            the Pieces tab to see the cuts separately.
          </p>
        )}
      </section>
      <section className="filament-section">
        <h2>Filament colors</h2>
        <label className="color-row">
          <input
            aria-label="Background color"
            type="color"
            disabled={disabled}
            value={settings.background_color}
            onChange={(event) => update("background_color", event.target.value)}
          />
          <span>Background</span>
          <small>{settings.background_color.toUpperCase()}</small>
        </label>
        <label className="color-row">
          <input
            aria-label="Artwork color"
            type="color"
            disabled={disabled}
            value={settings.artwork_color}
            onChange={(event) => update("artwork_color", event.target.value)}
          />
          <span>Image + border</span>
        </label>
        <p className="hint filament-hint">
          Background uses filament 1; image + border uses filament 2. Map them
          to your AMS trays in Bambu Studio.
        </p>
      </section>
      <div className="plan-bottom">
        <p className="hint export-hint">
          Each piece is a separate object with aligned background and image
          parts. Open the plate 3MFs as projects in Bambu Studio.
        </p>
        <button
          className="secondary-button"
          disabled={!ready || disabled}
          onClick={exportPack}
        >
          <Download size={16} /> Download full print pack
        </button>
        {download && (
          <a className="download-again" href={download} download={downloadName}>
            <Download size={16} /> Download{" "}
            {downloadName.endsWith(".3mf") ? "3MF" : "print pack"} again
          </a>
        )}
        {plateDownloads.length > 1 &&
          plateDownloads.map((url, i) => (
            <a key={url} className="download-again" href={url} download={`${fileStem(projectName)}-plate-${String(i + 1).padStart(2, "0")}.3mf`}>
              <Download size={16} /> Plate {i + 1} ·{" "}
              {manifest?.plates[i]?.pieces.length} pieces
            </a>
          ))}
        <div className={`fit-status ${ready ? "" : "pending"}`}>
          {ready ? (
            <Check size={21} />
          ) : busy ? (
            <LoaderCircle className="spin" size={21} />
          ) : (
            <TriangleAlert size={21} />
          )}
          <span>
            {ready
              ? "Fits your build plate"
              : busy
                ? "Checking geometry…"
                : "Check project settings"}
          </span>
        </div>
        {manifest && (
          <details className="print-notes">
            <summary>Before you print</summary>
            <p>
              Meshes are checked digitally. Physical fit and mounting strength
              have not been tested.
            </p>
            <ul>
              {manifest.warnings.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </aside>
  );
}
