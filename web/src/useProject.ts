/** Coordinate local project documents, optional recovery, and geometry generation.
 * Document imports replace state atomically; source revisions reject stale
 * worker exports, while name/tab edits avoid unnecessary geometry rebuilds. */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Preview, Settings, Update, View } from "./types";
import { WorkerEngine, EngineError } from "./engine";
import {
  downloadBlob, fileStem, MAX_ARTWORK_BYTES, parseWorkspace, projectName,
  serializeWorkspace, WORKSPACE_EXTENSION, type Workspace,
} from "./workspace";
import { readRecovery, writeRecovery } from "./workspaceStorage";

export function useProject() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [savedWorkspace, setSavedWorkspace] = useState<Workspace | null>(null);
  const [restoreOnReturn, setRestoreOnReturn] = useState(false);
  const [recoveryStatus, setRecoveryStatus] = useState("");
  const [workspaceError, setWorkspaceError] = useState("");
  const [workspaceMessage, setWorkspaceMessage] = useState("");
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [status, setStatus] = useState<"loading" | "building" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [errorCode, setErrorCode] = useState("");
  const [exporting, setExporting] = useState(false);
  const [download, setDownload] = useState("");
  const [downloadFormat, setDownloadFormat] = useState<"3mf" | "pack">("pack");
  const [plateDownloads, setPlateDownloads] = useState<string[]>([]);
  const [revision, setRevision] = useState(0);
  const source = useRef(0);
  const recoveryVersion = useRef(0);
  const engine = useRef<WorkerEngine | null>(null);
  const defaults = useRef<Settings | null>(null);
  const urls = useRef<string[]>([]);
  const settings = workspace?.settings ?? null;
  const file = workspace?.file ?? null;
  const name = workspace?.name ?? "Alpine study";
  const view = workspace?.view ?? "relief";
  const dirty = workspace !== savedWorkspace;
  const downloadName = `${fileStem(name)}${downloadFormat === "3mf" ? ".3mf" : "-print-pack.zip"}`;
  const clearDownloads = useCallback(() => {
    urls.current.forEach((url) => URL.revokeObjectURL(url));
    urls.current = [];
    setDownload("");
    setPlateDownloads([]);
  }, []);

  useEffect(() => {
    const worker = new WorkerEngine();
    engine.current = worker;
    return () => { worker.dispose(); clearDownloads(); };
  }, [clearDownloads]);

  useEffect(() => {
    if (workspace) return;
    let canceled = false;
    void (async () => {
      try {
        const settings = await engine.current!.defaults();
        defaults.current = settings;
        let restored: Workspace | null = null;
        try { restored = await readRecovery(settings); }
        catch {
          if (!canceled) setWorkspaceError("Could not restore browser storage. You can still open and save workspace files.");
        }
        if (canceled) return;
        const next = restored ?? { name: "Alpine study", settings, file: null, view: "relief" as const };
        setWorkspace(next);
        setSavedWorkspace(restored ? null : next);
        setRestoreOnReturn(Boolean(restored));
        if (restored) setWorkspaceMessage("Restored your last workspace from this browser.");
      } catch (error) {
        if (!canceled) { setError((error as Error).message); setStatus("error"); }
      }
    })();
    return () => { canceled = true; };
  }, [revision]);

  useEffect(() => {
    if (!workspace || !restoreOnReturn) return;
    let canceled = false;
    const version = ++recoveryVersion.current;
    setRecoveryStatus("Saving in this browser…");
    writeRecovery(workspace).then(() => {
      if (!canceled && version === recoveryVersion.current) setRecoveryStatus("Saved in this browser");
    }).catch(() => {
      if (!canceled && version === recoveryVersion.current)
        setRecoveryStatus("Browser save failed. Save a workspace file to keep your work.");
    });
    return () => { canceled = true; };
  }, [workspace, restoreOnReturn]);

  useEffect(() => {
    if (!dirty || (restoreOnReturn && recoveryStatus === "Saved in this browser")) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, restoreOnReturn, recoveryStatus]);

  useEffect(() => {
    if (!settings) return;
    let canceled = false;
    setStatus("building");
    setError("");
    setErrorCode("");
    clearDownloads();
    const timer = window.setTimeout(async () => {
      try {
        const next = await engine.current!.build(settings, file);
        if (!canceled) { setPreview(next); setStatus("ready"); }
      } catch (error) {
        if (!canceled) {
          setError(error instanceof Error ? error.message : "The browser geometry engine is unavailable.");
          setStatus("error");
          setErrorCode(error instanceof EngineError ? error.code : "");
        }
      }
    }, 550);
    return () => { canceled = true; clearTimeout(timer); };
  }, [settings, file, revision]);

  const invalidate = useCallback(() => {
    source.current += 1;
    setStatus("building");
    clearDownloads();
  }, [clearDownloads]);

  const update: Update = useCallback((key, value) => {
    invalidate();
    setWorkspace((current) => current ? {
      ...current,
      settings: { ...current.settings, [key]: value },
      view: key === "layout" ? value === "plaque" ? "relief" : "pieces" : current.view,
    } : current);
  }, [invalidate]);

  function resetImageSelection() {
    invalidate();
    setError("");
    setErrorCode("");
    setWorkspace((current) => current ? {
      ...current,
      settings: { ...current.settings, foreground: "auto", threshold: 128, invert: false, min_area_mm2: 0.6 },
    } : current);
  }

  function chooseFile(next: File | null) {
    if (workspaceBusy || exporting) return;
    if (next && next.size > MAX_ARTWORK_BYTES) {
      setError("Choose a file smaller than 12 MiB."); setErrorCode(""); return;
    }
    setWorkspace((current) => {
      if (!current) return current;
      const previousName = current.file ? current.file.name.replace(/\.[^.]+$/, "") : "Alpine study";
      return {
        ...current, file: next,
        name: current.name === projectName(previousName)
          ? projectName(next ? next.name.replace(/\.[^.]+$/, "") : "Alpine study") : current.name,
      };
    });
    setRevision((value) => value + 1);
    // Selection belongs to its image; keep fabrication settings on a fresh upload.
    resetImageSelection();
  }

  function rename(value: string, previousValue?: string) {
    // Disabling a focused field during import can deliver its blur after the
    // document swap. Only normalize the value that still belongs to this project.
    setWorkspace((current) => current && current.name !== value &&
      (previousValue === undefined || current.name === previousValue)
      ? { ...current, name: value } : current);
  }

  function setView(value: View) {
    setWorkspace((current) => current && current.view !== value ? { ...current, view: value } : current);
  }

  async function toggleRestore(enabled: boolean) {
    setRestoreOnReturn(enabled);
    if (enabled) return;
    const version = ++recoveryVersion.current;
    setRecoveryStatus("Removing browser copy…");
    try {
      await writeRecovery(null);
      if (version === recoveryVersion.current) setRecoveryStatus("Browser copy removed");
    } catch {
      if (version === recoveryVersion.current)
        setRecoveryStatus("Could not remove the browser copy. Try again or clear this site's storage in browser settings.");
    }
  }

  async function saveWorkspace() {
    if (!workspace || workspaceBusy) return;
    setWorkspaceBusy(true); setWorkspaceError(""); setWorkspaceMessage("");
    try {
      const document = await serializeWorkspace(workspace);
      downloadBlob(new Blob([document], { type: "application/json" }), `${fileStem(workspace.name)}${WORKSPACE_EXTENSION}`);
      setSavedWorkspace(workspace);
      setWorkspaceMessage("Workspace file downloaded.");
    } catch {
      setWorkspaceError("Could not save this workspace. Your current work is still open; try again.");
    } finally { setWorkspaceBusy(false); }
  }

  async function openWorkspace(document: File) {
    if (!defaults.current || workspaceBusy || exporting) return;
    setWorkspaceBusy(true); setWorkspaceError(""); setWorkspaceMessage("");
    try {
      const next = await parseWorkspace(document, defaults.current);
      if (dirty && !window.confirm("Replace this workspace? Save a workspace file first if you want to keep your current changes.")) return;
      invalidate();
      setPreview(null);
      setWorkspace(next);
      setSavedWorkspace(next);
      setWorkspaceMessage("Workspace opened.");
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "Could not open this workspace.");
    } finally { setWorkspaceBusy(false); }
  }

  async function exportPack(format: "3mf" | "pack" = "pack") {
    if (!preview || status !== "ready" || exporting || workspaceBusy) return;
    const version = source.current;
    setExporting(true); setError("");
    try {
      const result = await engine.current!.export(preview.id);
      if (version !== source.current) return;
      clearDownloads();
      const [pack, ...plates] = result.files;
      const blobUrl = (data: ArrayBuffer, type: string) => {
        const url = URL.createObjectURL(new Blob([data], { type }));
        urls.current.push(url);
        return url;
      };
      const packUrl = blobUrl(pack, "application/zip");
      const plateUrls = plates.map((data) => blobUrl(data, "model/3mf"));
      const url = format === "3mf" ? plateUrls[0] : packUrl;
      setDownload(url); setDownloadFormat(format); setPlateDownloads(plateUrls);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${fileStem(name)}${format === "3mf" ? ".3mf" : "-print-pack.zip"}`;
      link.click();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Export failed.");
    } finally { setExporting(false); }
  }

  return {
    settings, file, name, view, preview, status, error, errorCode, exporting,
    download, downloadName, plateDownloads, update, chooseFile, resetImageSelection,
    exportPack, rename, setView, dirty, restoreOnReturn, toggleRestore, recoveryStatus,
    workspaceError, workspaceMessage, workspaceBusy, saveWorkspace, openWorkspace,
    retry: () => setRevision((value) => value + 1),
  };
}
