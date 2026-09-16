/** Own a bounded worker queue. Superseded builds are discarded before dispatch;
 * every error settles its caller, and traps restart the worker for explicit retry. */
import type { Preview, Settings } from "./types";
export type EngineRequest = {
  id: number;
  operation: "defaults" | "build" | "export";
  settings?: Settings;
  image?: ArrayBuffer;
  sample?: boolean;
  previewId?: string;
};
export type EngineResponse = {
  id: number;
  ok: boolean;
  // The Rust JSON boundary validates operation-specific payloads before responding.
  value?: any;
  error?: { code: string; detail: string };
};
export class EngineError extends Error {
  constructor(message: string, readonly code = "") { super(message); }
}
type Pending = {
  request: EngineRequest;
  resolve(value: any): void;
  reject(error: EngineError): void;
};
export class WorkerEngine {
  private worker: Worker | null = null;
  private nextId = 0;
  private buildVersion = 0;
  private active: Pending | null = null;
  private pending: Pending[] = [];
  private timer: ReturnType<typeof setTimeout> | undefined;
  private start() {
    if (this.worker) return this.worker;
    const worker = new Worker(new URL("./engine.worker.ts", import.meta.url), { type: "module" });
    worker.addEventListener("message", ({ data }: MessageEvent<EngineResponse>) => {
      if (!this.active || data.id !== this.active.request.id) return;
      const active = this.active;
      this.active = null;
      clearTimeout(this.timer);
      if (data.ok) active.resolve(data.value);
      else {
        active.reject(new EngineError(data.error?.detail || "Geometry generation failed.", data.error?.code));
        if (data.error?.code === "worker") this.reset();
      }
      this.dispatch();
    });
    worker.addEventListener("error", (event) => {
      event.preventDefault();
      this.fail("The geometry worker stopped. Rebuild the preview to try again.");
    });
    worker.addEventListener("messageerror", () => this.fail("Could not read the geometry worker response. Rebuild the preview."));
    this.worker = worker;
    return worker;
  }
  private reset() { this.worker?.terminate(); this.worker = null; }
  private fail(message: string) {
    clearTimeout(this.timer);
    this.active?.reject(new EngineError(message, "worker"));
    this.active = null;
    for (const pending of this.pending) pending.reject(new EngineError(message, "worker"));
    this.pending = [];
    this.reset();
  }
  private dispatch() {
    if (this.active || this.pending.length === 0) return;
    const active = this.pending.shift()!;
    this.active = active;
    try {
      const worker = this.start();
      this.timer = setTimeout(() => this.fail("Generation exceeded the browser time limit. Try draft detail, simpler artwork, or fewer pieces."), 180_000);
      const image = active.request.image;
      worker.postMessage(active.request, image ? [image] : []);
    } catch (error) {
      this.fail(error instanceof Error ? error.message : "Could not start the geometry worker.");
    }
  }
  private call<T>(request: Omit<EngineRequest, "id">): Promise<T> {
    if (request.operation === "build") {
      this.pending = this.pending.filter((pending) => {
        if (pending.request.operation !== "build") return true;
        pending.reject(new EngineError("Superseded preview.", "superseded"));
        return false;
      });
    }
    return new Promise((resolve, reject) => {
      this.pending.push({ request: { ...request, id: ++this.nextId }, resolve, reject });
      this.dispatch();
    });
  }
  defaults() { return this.call<Settings>({ operation: "defaults" }); }
  async build(settings: Settings, file: File | null) {
    const version = ++this.buildVersion;
    const image = file ? await file.arrayBuffer() : undefined;
    if (version !== this.buildVersion) throw new EngineError("Superseded preview.", "superseded");
    return this.call<Preview>({ operation: "build", settings, image, sample: file === null });
  }
  export(previewId: string) { return this.call<{ files: ArrayBuffer[] }>({ operation: "export", previewId }); }
  dispose() { this.fail("The workbench was closed."); }
}
