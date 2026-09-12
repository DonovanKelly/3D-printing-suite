/** Artwork, layout, and fabrication controls grouped in the editor's left inspector. */
import { useRef, useState } from "react";
import {
  ChevronRight,
  Grid2X2,
  Puzzle,
  Square,
  Upload,
  Image as ImageIcon,
} from "lucide-react";
import type { Settings, Update } from "./types";

function Numeric({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <label className="field-row">
      <span>{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => {
          const next = event.target.valueAsNumber;
          if (Number.isFinite(next)) onChange(next);
        }}
      />
    </label>
  );
}

export function Controls({
  settings: s,
  update,
  file,
  chooseFile,
  disabled,
}: {
  settings: Settings;
  update: Update;
  file: File | null;
  chooseFile: (file: File | null) => void;
  disabled: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  return (
    <aside className="controls" aria-label="Project controls">
      <fieldset disabled={disabled}>
        <section className="control-section artwork-controls">
          <h2>
            <span>01</span> Artwork
          </h2>
          <button
            className={`upload-zone ${dragging ? "dragging" : ""}`}
            type="button"
            onClick={() => input.current?.click()}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              const next = event.dataTransfer.files[0];
              if (next) chooseFile(next);
            }}
          >
            {file ? <ImageIcon size={31} /> : <Upload size={31} />}
            <strong>{file ? file.name : "Drop an image or SVG"}</strong>
            <span>
              or <u>browse files</u>
            </span>
          </button>
          <input
            ref={input}
            className="visually-hidden"
            type="file"
            aria-label="Upload artwork"
            accept="image/png,image/jpeg,image/webp,image/svg+xml,.svg"
            onChange={(event) => {
              const next = event.target.files?.[0];
              if (next) chooseFile(next);
              event.target.value = "";
            }}
          />
          <button
            className="text-button sample-button"
            onClick={() => chooseFile(null)}
          >
            Use sample artwork
          </button>
          <label className="threshold">
            <span>Threshold</span>
            <div>
              <input
                type="range"
                min="1"
                max="254"
                value={s.threshold}
                onChange={(event) => update("threshold", +event.target.value)}
              />
              <output>{s.threshold}</output>
            </div>
          </label>
          <label className="field-row toggle-row">
            <span>Invert artwork</span>
            <input
              type="checkbox"
              role="switch"
              checked={s.invert}
              onChange={(event) => update("invert", event.target.checked)}
            />
          </label>
          <label className="field-row">
            <span>Detail</span>
            <select
              value={s.detail}
              onChange={(event) =>
                update("detail", event.target.value as Settings["detail"])
              }
            >
              <option value="draft">Draft</option>
              <option value="balanced">Balanced</option>
              <option value="fine">Fine</option>
            </select>
          </label>
        </section>
        <section className="control-section">
          <h2>
            <span>02</span> Format
          </h2>
          <div
            className="format-options"
            role="group"
            aria-label="Print format"
          >
            {(
              [
                { value: "plaque", label: "Plaque", Icon: Square },
                { value: "tiles", label: "Tiles", Icon: Grid2X2 },
                { value: "puzzle", label: "Puzzle", Icon: Puzzle },
              ] as const
            ).map(({ value, label, Icon }) => (
              <button
                key={value}
                aria-pressed={s.layout === value}
                onClick={() => {
                  update("layout", value);
                  update("rows", 0);
                  update("columns", 0);
                }}
              >
                <Icon size={23} />
                <span>{label}</span>
              </button>
            ))}
          </div>
          <p className="field-label">Size (mm)</p>
          <div className="size-fields">
            <Numeric
              label="Width"
              value={s.width_mm}
              min={30}
              max={1500}
              onChange={(value) => update("width_mm", value)}
            />
            <Numeric
              label="Height"
              value={s.height_mm}
              min={30}
              max={1500}
              onChange={(value) => update("height_mm", value)}
            />
          </div>
          <label className="field-row">
            <span>Frame</span>
            <select
              value={s.frame ? "raised" : "none"}
              onChange={(event) =>
                update("frame", event.target.value === "raised")
              }
            >
              <option value="raised">Raised border</option>
              <option value="none">No border</option>
            </select>
          </label>
          <label className="field-row">
            <span>Hanging</span>
            <select
              value={s.hanging}
              onChange={(event) => {
                const hanging = event.target.value as Settings["hanging"];
                update("hanging", hanging);
                if (hanging === "keyholes" && s.base_mm < 5)
                  update("base_mm", 5);
              }}
            >
              <option value="none">None</option>
              <option value="loops">Top loops</option>
              <option value="keyholes">Rear keyholes</option>
            </select>
          </label>
          {s.layout !== "plaque" && (
            <div className="layout-options">
              <label className="field-row">
                <span>Split</span>
                <select
                  aria-label="Split mode"
                  value={s.columns ? "manual" : "auto"}
                  onChange={(event) => {
                    const n = event.target.value === "auto" ? 0 : 2;
                    update("columns", n);
                    update("rows", n);
                  }}
                >
                  <option value="auto">Automatic</option>
                  <option value="manual">Custom grid</option>
                </select>
              </label>
              {!!s.columns && (
                <div className="size-fields">
                  <Numeric
                    label="Cols"
                    value={s.columns}
                    min={1}
                    max={12}
                    onChange={(value) => update("columns", value)}
                  />
                  <Numeric
                    label="Rows"
                    value={s.rows}
                    min={1}
                    max={12}
                    onChange={(value) => update("rows", value)}
                  />
                </div>
              )}
              <Numeric
                label="Clearance (mm)"
                value={s.clearance_mm}
                min={0}
                max={1}
                step={0.05}
                onChange={(value) => update("clearance_mm", value)}
              />
            </div>
          )}
        </section>
        <details className="print-settings">
          <summary>
            <ChevronRight size={18} /> Print settings
          </summary>
          <div className="advanced-fields">
            <Numeric
              label="Backing (mm)"
              value={s.base_mm}
              min={1.2}
              max={12}
              step={0.2}
              onChange={(v) => update("base_mm", v)}
            />
            <Numeric
              label="Relief (mm)"
              value={s.relief_mm}
              min={0.4}
              max={8}
              step={0.2}
              onChange={(v) => update("relief_mm", v)}
            />
            {s.frame && (
              <>
                <Numeric
                  label="Border width (mm)"
                  value={s.frame_width_mm}
                  min={1}
                  max={30}
                  step={0.5}
                  onChange={(v) => update("frame_width_mm", v)}
                />
                <Numeric
                  label="Border rise (mm)"
                  value={s.frame_height_mm}
                  min={0.4}
                  max={12}
                  step={0.2}
                  onChange={(v) => update("frame_height_mm", v)}
                />
              </>
            )}
            <Numeric
              label="Art margin (mm)"
              value={s.margin_mm}
              min={0}
              max={30}
              onChange={(v) => update("margin_mm", v)}
            />
            <Numeric
              label="Minimum area (mm²)"
              value={s.min_area_mm2}
              min={0}
              max={20}
              step={0.1}
              onChange={(v) => update("min_area_mm2", v)}
            />
            <Numeric
              label="Usable bed width"
              value={s.bed_width_mm}
              min={60}
              max={256}
              onChange={(v) => update("bed_width_mm", v)}
            />
            <Numeric
              label="Usable bed height"
              value={s.bed_height_mm}
              min={60}
              max={256}
              onChange={(v) => update("bed_height_mm", v)}
            />
            <p className="hint">
              Bed values are in mm. Leave space for your brim, prime tower, and
              excluded areas.
            </p>
          </div>
        </details>
      </fieldset>
    </aside>
  );
}
