/** Coordinate debounced geometry previews and explicit exports, rejecting stale responses. */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Preview, Settings, Update } from "./types";

import { WorkerEngine, EngineError } from "./engine";

export function useProject() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [status, setStatus] = useState<
    "loading" | "building" | "ready" | "error"
  >("loading");
  const [error, setError] = useState("");
  const [errorCode, setErrorCode] = useState("");
  const [exporting, setExporting] = useState(false);
  const [download, setDownload] = useState("");
  const [downloadName, setDownloadName] = useState("print-pack.zip");
  const [plateDownloads, setPlateDownloads] = useState<string[]>([]);
  const [revision, setRevision] = useState(0);
  const source = useRef(0);
  const engine = useRef<WorkerEngine | null>(null);
  const urls = useRef<string[]>([]);
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
    if (settings) return;
    let canceled = false;
    engine.current!.defaults()
      .then((next) => { if (!canceled) setSettings(next); })
      .catch((error) => {
        if (!canceled) { setError(error.message); setStatus("error"); }
      });
    return () => { canceled = true; };
  }, [revision]);

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
        if (!canceled) {
          setPreview(next);
          setStatus("ready");
        }
      } catch (error) {
        if (!canceled) {
          setError(
            error instanceof Error
              ? error.message
              : "The browser geometry engine is unavailable.",
          );
          setStatus("error");
          setErrorCode(error instanceof EngineError ? error.code : "");
        }
      }
    }, 550);
    return () => {
      canceled = true;
      clearTimeout(timer);
    };
  }, [settings, file, revision]);

  const update: Update = useCallback((key, value) => {
    source.current += 1;
    setStatus("building");
    clearDownloads();
    setSettings((current) =>
      current ? { ...current, [key]: value } : current,
    );
  }, []);

  function resetImageSelection() {
    source.current += 1;
    setStatus("building");
    setError("");
    setErrorCode("");
    clearDownloads();
    setSettings((current) =>
      current
        ? {
            ...current,
            foreground: "auto",
            threshold: 128,
            invert: false,
            min_area_mm2: 0.6,
          }
        : current,
    );
  }

  function chooseFile(next: File | null) {
    if (next && next.size > 12 * 1024 * 1024) {
      setError("Choose a file smaller than 12 MiB.");
      setErrorCode("");
      return;
    }
    setFile(next);
    setRevision((value) => value + 1);
    // Selection belongs to the source image. Keep dimensions and fabrication
    // settings, but do not carry an incompatible threshold into a new upload.
    resetImageSelection();
  }

  async function exportPack(format: "3mf" | "pack" = "pack") {
    if (!preview || status !== "ready" || exporting) return;
    const version = source.current;
    setExporting(true);
    setError("");
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
      if (version === source.current) {
        setDownload(url);
        setDownloadName(format === "3mf" ? "relief.3mf" : "print-pack.zip");
        setPlateDownloads(plateUrls);
        const link = document.createElement("a");
        link.href = url;
        link.download = format === "3mf" ? "relief.3mf" : "print-pack.zip";
        link.click();
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  }

  return {
    settings,
    file,
    preview,
    status,
    error,
    errorCode,
    exporting,
    download,
    downloadName,
    plateDownloads,
    update,
    chooseFile,
    resetImageSelection,
    exportPack,
    retry: () => setRevision((value) => value + 1),
  };
}
