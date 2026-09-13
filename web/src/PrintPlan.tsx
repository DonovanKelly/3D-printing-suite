/** Summarize the last valid geometry and expose material colors and fabrication notes. */
import { Check, Download, LoaderCircle, TriangleAlert } from "lucide-react";
import type { Preview, Settings, Update } from "./types";

export function PrintPlan({
  preview,
  settings,
  update,
  ready,
  busy,
  download,
  disabled,
  exportPack,
}: {
  preview: Preview | null;
  settings: Settings;
  update: Update;
  ready: boolean;
  busy: boolean;
  download: string;
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
            the Assembly tab for piece labels.
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
          Assign these parts to your AMS slots in Bambu Studio.
        </p>
      </section>
      <div className="plan-bottom">
        <p className="hint export-hint">
          3MF keeps the image and background as separate, aligned color parts.
        </p>
        <button
          className="secondary-button"
          disabled={!ready || disabled}
          onClick={exportPack}
        >
          <Download size={16} /> Download full print pack
        </button>
        {download && (
          <a className="download-again" href={download} download>
            <Download size={16} /> Download{" "}
            {download.endsWith(".3mf") ? "3MF" : "print pack"} again
          </a>
        )}
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
