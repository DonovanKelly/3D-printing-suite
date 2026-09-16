/** Compose the local workbench, editable project identity, and workspace file controls. */
import { useEffect, useRef, useState } from "react";
import {
  Download,
  Layers,
  LoaderCircle,
  Printer,
  TriangleAlert,
  FolderOpen,
  Save,
  Pencil,
} from "lucide-react";
import { Controls } from "./Controls";
import { PrintPlan } from "./PrintPlan";
import { useProject } from "./useProject";
import { Viewer } from "./Viewer";
import { NumericEditing } from "./Numeric";
import { projectName, WORKSPACE_EXTENSION } from "./workspace";

export default function App() {
  const project = useProject();
  const workspaceInput = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(false);
  const { settings, preview, file, status, error, exporting, download, name, view, setView } =
    project;
  const busy = exporting || project.workspaceBusy;
  const ready = status === "ready" && !editing && !busy;
  const singlePlate = preview?.manifest.plate_count === 1;
  useEffect(() => {
    const save = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (!editing && !busy) void project.saveWorkspace();
      }
    };
    window.addEventListener("keydown", save);
    return () => window.removeEventListener("keydown", save);
  }, [project.saveWorkspace, editing, busy]);
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
            onClick={() => project.exportPack(singlePlate ? "3mf" : "pack")}
          >
            {exporting ? (
              <LoaderCircle size={19} className="spin" />
            ) : (
              <Download size={19} />
            )}
            <span>
              {exporting
                ? "Preparing download…"
                : singlePlate
                  ? "Download 3MF"
                  : `Download ${preview?.manifest.plate_count ?? "print"} plates (ZIP)`}
            </span>
          </button>
        </div>
      </header>
      <div className="project-bar">
        <div className="project-title">
          <h1>
            <input
              aria-label="Project name"
              title="Edit project name and download filenames"
              value={name}
              maxLength={120}
              disabled={!settings || busy}
              onChange={(event) => project.rename(event.target.value)}
              onBlur={(event) => project.rename(projectName(event.target.value), event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter") event.currentTarget.blur(); }}
            />
          </h1>
          <Pencil size={15} aria-hidden="true" />
        </div>
        <nav className="view-tabs" aria-label="Preview mode">
          {(["relief", "pieces", "assembly", "vector"] as const).map((tab) => (
            <button
              key={tab}
              disabled={!settings || busy}
              aria-pressed={view === tab}
              onClick={() => setView(tab)}
            >
              {tab[0].toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </div>
      <section className="workspace-bar" aria-label="Workspace files">
        <div className="workspace-actions">
          <button disabled={!settings || busy || editing} onClick={() => workspaceInput.current?.click()}>
            <FolderOpen size={17} /> Open workspace
          </button>
          <input
            ref={workspaceInput}
            className="visually-hidden"
            type="file"
            aria-label="Open workspace file"
            accept={`${WORKSPACE_EXTENSION},.json,application/json`}
            disabled={!settings || busy || editing}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) void project.openWorkspace(file);
            }}
          />
          <button disabled={!settings || busy || editing} onClick={() => project.saveWorkspace()} title="Save workspace (Ctrl/Cmd+S)">
            <Save size={17} /> Save workspace
          </button>
        </div>
        <div className="workspace-recovery">
          <label>
            <input type="checkbox" checked={project.restoreOnReturn} disabled={!settings || busy}
              onChange={(event) => void project.toggleRestore(event.target.checked)} />
            Restore on return
          </label>
          <span role="status" className="workspace-status">
            {project.recoveryStatus || (project.dirty ? "Changes not saved to file" : "Artwork + settings stay on your device")}
          </span>
        </div>
        {project.workspaceError && <p className="workspace-error" role="alert">{project.workspaceError}</p>}
        {project.workspaceMessage && <p className="workspace-message" role="status">{project.workspaceMessage}</p>}
      </section>
      <main className="workbench">
        {settings ? (
          <NumericEditing.Provider value={setEditing}>
            <Controls
              settings={settings}
              update={project.update}
              file={file}
              chooseFile={project.chooseFile}
              resetImageSelection={project.resetImageSelection}
              disabled={busy}
            />
          </NumericEditing.Provider>
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
                : view === "pieces"
                  ? "Separate pieces · gaps for viewing"
                  : view === "assembly"
                    ? "Assembly map"
                    : "Vector preview"}
            </span>
            <span>
              {preview
                ? preview.manifest.settings.shape === "contour"
                  ? `${preview.manifest.pieces[0].extents_mm
                      .slice(0, 2)
                      .map((v) => v.toFixed(1))
                      .join(" × ")} mm · finished`
                  : `${preview.manifest.settings.width_mm} × ${preview.manifest.settings.height_mm} mm`
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
          {editing && preview && (
            <div className="building-state" role="status">
              Press Enter or leave the field to apply your edit.
            </div>
          )}
          {!editing && status === "building" && preview && (
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
                <button
                  className="text-button"
                  onClick={
                    project.errorCode === "image_selection"
                      ? project.resetImageSelection
                      : project.retry
                  }
                >
                  {project.errorCode === "image_selection"
                    ? "Reset image selection"
                    : "Rebuild preview"}
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
            download={editing ? "" : download}
            downloadName={project.downloadName}
            plateDownloads={editing ? [] : project.plateDownloads}
            projectName={name}
            disabled={busy}
            exportPack={() => project.exportPack("pack")}
          />
        ) : (
          <aside />
        )}
      </main>
      <footer className="status-bar">
        <span>
          <i /> Runs in your browser
        </span>
        <span>Millimeters</span>
      </footer>
    </div>
  );
}
