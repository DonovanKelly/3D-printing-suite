/** Coordinate debounced geometry previews and explicit exports, rejecting stale responses. */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Preview, Settings, Update } from "./types";

class ServiceError extends Error {
  constructor(
    message: string,
    readonly code = "",
  ) {
    super(message);
  }
}

async function failure(response: Response): Promise<ServiceError> {
  try {
    const data = await response.json();
    return new ServiceError(
      typeof data.detail === "string"
        ? data.detail
        : "Check the project settings.",
      typeof data.code === "string" ? data.code : "",
    );
  } catch {
    return new ServiceError(`The local service returned ${response.status}.`);
  }
}

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
  const [plateDownloads, setPlateDownloads] = useState<string[]>([]);
  const [revision, setRevision] = useState(0);
  const source = useRef(0);

  useEffect(() => {
    if (settings) return;
    fetch("/api/defaults")
      .then(async (response) => {
        if (!response.ok) throw await failure(response);
        setSettings(await response.json());
      })
      .catch((error) => {
        setError(error.message);
        setStatus("error");
      });
  }, [revision]);

  useEffect(() => {
    if (!settings) return;
    let canceled = false;
    setStatus("building");
    setError("");
    setErrorCode("");
    setDownload("");
    setPlateDownloads([]);
    const timer = window.setTimeout(async () => {
      const form = new FormData();
      form.set("settings", JSON.stringify(settings));
      if (file) form.set("image", file);
      try {
        let response: Response;
        // A superseded request may still be finishing in the local geometry worker.
        // Wait for that bounded worker instead of racing two model generations.
        do {
          response = await fetch("/api/preview", {
            method: "POST",
            body: form,
          });
          if (canceled) return;
          if (response.status === 409)
            await new Promise((resolve) => setTimeout(resolve, 500));
        } while (response.status === 409 && !canceled);
        if (canceled) return;
        if (!response.ok) throw await failure(response);
        const next: Preview = await response.json();
        if (!canceled) {
          setPreview(next);
          setStatus("ready");
        }
      } catch (error) {
        if (!canceled) {
          setError(
            error instanceof Error
              ? error.message
              : "The local service is unavailable.",
          );
          setStatus("error");
          setErrorCode(error instanceof ServiceError ? error.code : "");
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
    setDownload("");
    setPlateDownloads([]);
    setSettings((current) =>
      current ? { ...current, [key]: value } : current,
    );
  }, []);

  function resetImageSelection() {
    source.current += 1;
    setStatus("building");
    setError("");
    setErrorCode("");
    setDownload("");
    setPlateDownloads([]);
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
      const response = await fetch(`/api/export/${preview.id}`, {
        method: "POST",
      });
      if (!response.ok) throw await failure(response);
      const result = await response.json();
      const url = format === "3mf" ? result.model_url : result.download_url;
      if (!url)
        throw new Error(
          "This layout needs multiple plates. Download its print pack instead.",
        );
      if (version === source.current) {
        setDownload(url);
        setPlateDownloads(result.plate_urls ?? []);
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
    plateDownloads,
    update,
    chooseFile,
    resetImageSelection,
    exportPack,
    retry: () => setRevision((value) => value + 1),
  };
}
