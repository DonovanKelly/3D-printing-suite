/** Keep extrusion, backing, and border controls visible; image cleanup and printer tuning are secondary. */
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
import { Numeric } from "./Numeric";

export function Controls({
  settings: s,
  update,
  file,
  chooseFile,
  resetImageSelection,
  disabled,
}: {
  settings: Settings;
  update: Update;
  file: File | null;
  chooseFile: (file: File | null) => void;
  resetImageSelection: () => void;
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
            {file ? <ImageIcon size={25} /> : <Upload size={25} />}
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
          <details className="print-settings image-settings">
            <summary>
              <ChevronRight size={18} /> Image selection
            </summary>
            <label className="field-row">
              <span>Foreground</span>
              <select
                aria-label="Foreground"
                value={s.foreground}
                onChange={(event) =>
                  update(
                    "foreground",
                    event.target.value as Settings["foreground"],
                  )
                }
              >
                <option value="auto">Automatic</option>
                <option value="dark">Dark pixels</option>
                <option value="light">Light pixels</option>
              </select>
            </label>
            <p className="hint control-hint">
              SVG shapes extrude automatically, including light-colored shapes
              on transparency. Dark/light modes use brightness and may select
              nothing at some thresholds.
            </p>
            <button className="text-button" onClick={resetImageSelection}>
              Reset image selection
            </button>
            <label className="threshold">
              <span>Threshold</span>
              <div>
                <input
                  aria-label="Threshold"
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
                aria-label="Detail"
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
          </details>
        </section>
        <section className="control-section">
          <h2>
            <span>02</span> Image &amp; background
          </h2>
          <p className="hint control-hint">
            Type a value, then press Enter or leave the field to apply.
          </p>
          <div className="size-fields">
            <Numeric
              label="Width (mm)"
              value={s.width_mm}
              min={30}
              max={1500}
              onChange={(value) => update("width_mm", value)}
            />
            <Numeric
              label="Height (mm)"
              value={s.height_mm}
              min={30}
              max={1500}
              onChange={(value) => update("height_mm", value)}
            />
          </div>
          <Numeric
            label="Image thickness (mm)"
            value={s.relief_mm}
            min={0.4}
            max={8}
            step={0.2}
            onChange={(value) => update("relief_mm", value)}
          />
          <Numeric
            label="Background thickness (mm)"
            value={s.base_mm}
            min={s.hanging === "keyholes" ? 5 : 1.2}
            max={12}
            step={0.2}
            onChange={(value) => update("base_mm", value)}
          />
          <Numeric
            label="Padding (mm)"
            value={s.margin_mm}
            min={0}
            max={30}
            step={0.5}
            onChange={(value) => update("margin_mm", value)}
          />
          <p className="hint control-hint">
            Image thickness is the height above the background. Padding adds
            space inside the border.
          </p>
          <label className="field-row toggle-row">
            <span>Trim empty image space</span>
            <input
              type="checkbox"
              role="switch"
              checked={s.crop_to_artwork}
              onChange={(event) =>
                update("crop_to_artwork", event.target.checked)
              }
            />
          </label>
          <p className="hint">
            Your image keeps its proportions. Extra space may remain on two
            sides.
          </p>
        </section>
        <section className="control-section">
          <h2>
            <span>03</span> Border &amp; hanging
          </h2>
          <label className="field-row">
            <span>Border</span>
            <select
              aria-label="Border"
              value={s.frame ? s.frame_profile : "none"}
              onChange={(event) => {
                update("frame", event.target.value !== "none");
                if (event.target.value !== "none")
                  update(
                    "frame_profile",
                    event.target.value as Settings["frame_profile"],
                  );
              }}
            >
              <option value="none">No border</option>
              <option value="flat">Raised · flat</option>
              <option value="rounded">Raised · rounded</option>
            </select>
          </label>
          <Numeric
            label="Border width (mm)"
            value={s.frame ? s.frame_width_mm : 0}
            min={0}
            max={30}
            step={0.5}
            onChange={(value) => {
              update("frame", value !== 0);
              if (value !== 0) update("frame_width_mm", value);
            }}
          />
          <p className="hint control-hint">
            Width is the raised rim around the artwork. 0 removes the border;
            Padding controls the gap inside it.
          </p>
          {s.frame && (
            <>
              <Numeric
                label="Border height (mm)"
                value={s.frame_height_mm}
                min={0.4}
                max={12}
                step={0.2}
                onChange={(value) => update("frame_height_mm", value)}
              />
              <p className="hint control-hint">
                Border height is measured above the background. It shares the
                image color.
              </p>
            </>
          )}
          <Numeric
            label="Corner radius (mm)"
            value={s.corner_radius_mm}
            min={0}
            max={Math.min(100, s.width_mm / 2, s.height_mm / 2)}
            step={1}
            onChange={(value) => update("corner_radius_mm", value)}
          />
          <p className="hint control-hint">
            0 makes square corners. Rounded corners apply to the outside of the
            whole design.
          </p>
          <label className="field-row">
            <span>Hanging</span>
            <select
              aria-label="Hanging"
              value={s.hanging}
              onChange={(event) => {
                const hanging = event.target.value as Settings["hanging"];
                update("hanging", hanging);
                if (hanging === "keyholes" && s.base_mm < 5)
                  update("base_mm", 5);
              }}
            >
              <option value="none">None</option>
              <option value="loops">Top loop · centered</option>
              <option value="keyholes">Rear keyholes</option>
            </select>
          </label>
          {s.hanging === "loops" && (
            <p className="hint control-hint">
              {s.layout === "plaque"
                ? "One centered loop with a 5 mm opening. Adds up to 9 mm above the backing."
                : "One centered loop on each top-row panel, following its upper edge."}
            </p>
          )}
          {s.hanging === "keyholes" && (
            <p className="hint control-hint">
              Recesses on the back for screw heads. Requires a background at
              least 5 mm thick.
            </p>
          )}
        </section>
        <section className="control-section">
          <h2>
            <span>04</span> Print format
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
          {s.layout !== "plaque" && (
            <div className="layout-options">
              <label className="field-row">
                <span>Split</span>
                <select
                  aria-label="Split"
                  value={s.columns ? "manual" : s.split_mode}
                  onChange={(event) => {
                    const n = event.target.value === "manual" ? 2 : 0;
                    update("columns", n);
                    update("rows", n);
                    if (!n)
                      update(
                        "split_mode",
                        event.target.value as Settings["split_mode"],
                      );
                  }}
                >
                  <option value="size">By piece size</option>
                  <option value="bed">Largest panels</option>
                  <option value="manual">Custom grid</option>
                </select>
              </label>
              {!s.columns && s.split_mode === "size" && (
                <>
                  <Numeric
                    label="Max piece size (mm)"
                    value={s.piece_size_mm}
                    min={30}
                    max={256}
                    onChange={(value) => update("piece_size_mm", value)}
                  />
                  <p className="hint control-hint">
                    Includes tabs and loops. Smaller sizes make more pieces.
                  </p>
                </>
              )}
              {!s.columns && s.split_mode === "bed" && (
                <p className="hint control-hint">
                  Make the fewest panels that fit your bed, with at least two
                  pieces.
                </p>
              )}
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
              {s.layout === "puzzle" && (
                <>
                  <label className="field-row">
                    <span>Cut pattern</span>
                    <select
                      aria-label="Cut pattern"
                      value={s.puzzle_style}
                      onChange={(event) =>
                        update(
                          "puzzle_style",
                          event.target.value as Settings["puzzle_style"],
                        )
                      }
                    >
                      <option value="random">Random</option>
                      <option value="regular">Regular</option>
                    </select>
                  </label>
                  {s.puzzle_style === "random" && (
                    <>
                      <Numeric
                        label="Pattern seed"
                        value={s.puzzle_seed}
                        min={0}
                        max={2147483647}
                        onChange={(value) => update("puzzle_seed", value)}
                      />
                      <button
                        className="secondary-button"
                        onClick={() =>
                          update(
                            "puzzle_seed",
                            (s.puzzle_seed + 1) % 2147483648,
                          )
                        }
                      >
                        Shuffle pattern
                      </button>
                      <p className="hint">
                        Same seed and settings recreate the same cuts.
                      </p>
                    </>
                  )}
                </>
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
            <ChevronRight size={18} /> Printer &amp; detail limits
          </summary>
          <div className="advanced-fields">
            <Numeric
              label="Minimum area (mm²)"
              value={s.min_area_mm2}
              min={0}
              max={20}
              step={0.1}
              onChange={(value) => update("min_area_mm2", value)}
            />
            <Numeric
              label="Usable bed width"
              value={s.bed_width_mm}
              min={60}
              max={256}
              onChange={(value) => update("bed_width_mm", value)}
            />
            <Numeric
              label="Usable bed height"
              value={s.bed_height_mm}
              min={60}
              max={256}
              onChange={(value) => update("bed_height_mm", value)}
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
