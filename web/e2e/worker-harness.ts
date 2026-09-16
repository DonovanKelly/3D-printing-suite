/** Observe and fault-inject the real worker transport without adding production test hooks. */
import type { Page } from "@playwright/test";
import type { EngineRequest, EngineResponse } from "../src/engine";

declare global {
  interface Window {
    engineTest: {
      requests: EngineRequest[];
      responses: (EngineResponse & { operation: string })[];
      holdNext: boolean;
      held: boolean;
      failNext: boolean;
      release(): void;
    };
  }
}
export async function observeWorker(page: Page) {
  await page.addInitScript(() => {
    const NativeWorker = window.Worker;
    const state: Window["engineTest"] = {
      requests: [], responses: [], holdNext: false, held: false, failNext: false,
      release() {},
    };
    window.engineTest = state;
    class ObservedWorker extends EventTarget {
      private inner: Worker;
      private operations = new Map<number, string>();
      constructor(url: string | URL, options?: WorkerOptions) {
        super();
        this.inner = new NativeWorker(url, options);
        this.inner.addEventListener("message", (event) => {
          const operation = this.operations.get(event.data.id) || "";
          const deliver = () => {
            state.responses.push({ ...event.data, operation });
            this.dispatchEvent(new MessageEvent("message", { data: event.data }));
          };
          if (operation === "build" && state.holdNext) {
            state.holdNext = false; state.held = true;
            state.release = () => { state.held = false; deliver(); };
          } else deliver();
        });
        for (const type of ["error", "messageerror"])
          this.inner.addEventListener(type, () => this.dispatchEvent(new Event(type)));
      }
      postMessage(request: EngineRequest, transfer: Transferable[]) {
        this.operations.set(request.id, request.operation);
        state.requests.push({ ...request, image: undefined });
        if (request.operation === "build" && state.failNext) {
          state.failNext = false;
          setTimeout(() => {
            state.responses.push({ id: request.id, operation: "build", ok: false, error: { code: "worker", detail: "Temporary worker failure" } });
            this.dispatchEvent(new Event("error", { cancelable: true }));
          }, 10);
          return;
        }
        this.inner.postMessage(request, transfer);
      }
      terminate() { this.inner.terminate(); }
    }
    window.Worker = ObservedWorker as unknown as typeof Worker;
  });
}
export async function nextBuild(page: Page, action: () => Promise<unknown>, status = 200) {
  const cursor = await page.evaluate(() => window.engineTest.responses.length);
  await action();
  await page.waitForFunction(({ cursor, status }) => window.engineTest.responses.slice(cursor).some(
    (r) => r.operation === "build" && (r.ok ? 200 : r.error?.code === "worker" ? 500 : 422) === status,
  ), { cursor, status }, { timeout: 120_000 });
  return page.evaluate(({ cursor, status }) => {
    const result = window.engineTest.responses.slice(cursor).find(
      (r) => r.operation === "build" && (r.ok ? 200 : r.error?.code === "worker" ? 500 : 422) === status,
    )!;
    return result.ok ? result.value : result.error;
  }, { cursor, status });
}
