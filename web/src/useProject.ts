/** Coordinate debounced geometry previews and explicit exports, rejecting stale responses. */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Preview, Settings, Update } from "./types";

async function detail(response: Response): Promise<string> {
  try {
    const data = await response.json();
    return typeof data.detail === "string"
      ? data.detail
      : "Check the project settings.";
  } catch {
    return `The local service returned ${response.status}.`;
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
  const [exporting, setExporting] = useState(false);
  const [download, setDownload] = useState("");
  const [revision, setRevision] = useState(0);
  const source = useRef(0);

  useEffect(() => {
    if (settings) return;
    fetch("/api/defaults")
      .then(async (response) => {
        if (!response.ok) throw new Error(await detail(response));
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
    setDownload("");
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
        if (!response.ok) throw new Error(await detail(response));
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
    setSettings((current) =>
      current ? { ...current, [key]: value } : current,
    );
  }, []);

  function chooseFile(next: File | null) {
    if (next && next.size > 12 * 1024 * 1024) {
      setError("Choose a file smaller than 12 MiB.");
      return;
    }
    source.current += 1;
    setFile(next);
    setRevision((value) => value + 1);
    setStatus("building");
    setDownload("");
  }

  async function exportPack() {
    if (!preview || status !== "ready" || exporting) return;
    const version = source.current;
    setExporting(true);
    setError("");
    try {
      const response = await fetch(`/api/export/${preview.id}`, {
        method: "POST",
      });
      if (!response.ok) throw new Error(await detail(response));
      const result = await response.json();
      if (version === source.current) {
        setDownload(result.download_url);
        const link = document.createElement("a");
        link.href = result.download_url;
        link.download = "print-pack.zip";
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
    exporting,
    download,
    update,
    chooseFile,
    exportPack,
    retry: () => setRevision((value) => value + 1),
  };
}
