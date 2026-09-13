/** Compose the local maker workbench, including valid-preview and export states. */
import { useState } from "react";
import {
  Download,
  Layers,
  LoaderCircle,
  Printer,
  TriangleAlert,
} from "lucide-react";
import { Controls } from "./Controls";
import { PrintPlan } from "./PrintPlan";
import { useProject } from "./useProject";
import { Viewer } from "./Viewer";
import type { View } from "./types";

export default function App() {
  const project = useProject();
  const [view, setView] = useState<View>("relief");
  const { settings, preview, file, status, error, exporting, download } =
    project;
  const ready = status === "ready";
  const singlePiece = preview?.manifest.piece_count === 1;
  const title = file ? file.name.replace(/\.[^.]+$/, "") : "Alpine study";
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <Layers size={30} />
          <span>Relief Studio</span>
          <small>3D printing suite</small>
        </div>
        <div className="header-actions">
          <span className="printer">
            <Printer size={19} /> Bambu Lab P1S
          </span>
          <button
            className="primary-button"
            disabled={!ready || exporting}
            onClick={() => project.exportPack(singlePiece ? "3mf" : "pack")}
          >
            {exporting ? (
              <LoaderCircle size={19} className="spin" />
            ) : (
              <Download size={19} />
            )}
            <span>
              {exporting
                ? "Preparing download…"
                : singlePiece
                  ? "Download 3MF"
                  : "Export print pack"}
            </span>
          </button>
        </div>
      </header>
      <div className="project-bar">
        <div className="project-title">
          <h1 title={title}>{title}</h1>
          <span>Image to two-color relief</span>
        </div>
        <nav className="view-tabs" aria-label="Preview mode">
          {(["relief", "assembly", "vector"] as const).map((tab) => (
            <button
              key={tab}
              aria-pressed={view === tab}
              onClick={() => setView(tab)}
            >
              {tab[0].toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </div>
      <main className="workbench">
        {settings ? (
          <Controls
            settings={settings}
            update={project.update}
            file={file}
            chooseFile={project.chooseFile}
            disabled={exporting}
          />
        ) : (
          <aside />
        )}
        <section
          className="preview-pane"
          aria-label="Artwork preview"
          aria-busy={status === "building"}
        >
          <div className="canvas-heading">
            <span>
              {view === "relief"
                ? "3D preview"
                : view === "assembly"
                  ? "Assembly map"
                  : "Vector preview"}
            </span>
            <span>
              {preview
                ? `${preview.manifest.settings.width_mm} × ${preview.manifest.settings.height_mm} mm`
                : ""}
            </span>
          </div>
          {preview && <Viewer preview={preview} view={view} />}
          {!preview && !error && (
            <div className="canvas-empty">
              <LoaderCircle size={28} className="spin" />
              <p>Building your first relief…</p>
            </div>
          )}
          {status === "building" && preview && (
            <div className="building-state" role="status">
              <LoaderCircle size={15} className="spin" /> Updating preview…
            </div>
          )}
          {error && (
            <div className="error-message" role="alert">
              <TriangleAlert size={21} />
              <div>
                <strong>
                  {status === "error"
                    ? "This project needs an adjustment"
                    : "Could not complete that action"}
                </strong>
                <p>{error}</p>
                {status === "error" && preview && (
                  <p className="hint">
                    The canvas still shows your previous valid preview.
                  </p>
                )}
                <button className="text-button" onClick={project.retry}>
                  Rebuild preview
                </button>
              </div>
            </div>
          )}
        </section>
        {settings ? (
          <PrintPlan
            settings={settings}
            preview={preview}
            update={project.update}
            ready={ready}
            busy={status === "building"}
            download={download}
            disabled={exporting}
            exportPack={() => project.exportPack("pack")}
          />
        ) : (
          <aside />
        )}
      </main>
      <footer className="status-bar">
        <span>
          <i /> Local processing
        </span>
        <span>Millimeters</span>
      </footer>
    </div>
  );
}
