/** Run the Rust/Manifold module in one serialized worker and transfer export buffers. */
import type { EngineRequest, EngineResponse } from "./engine";

type Module = {
  HEAPU8: Uint8Array;
  _relief_alloc(length: number): number;
  _relief_free(pointer: number, length: number): void;
  _relief_request(request: number, length: number, image: number, imageLength: number): void;
  _relief_response_ptr(): number;
  _relief_response_len(): number;
  _relief_file_ptr(index: number): number;
  _relief_file_len(index: number): number;
  _relief_clear_files(): void;
};
const root = new URL(/* @vite-ignore */ "../engine/", import.meta.url);
let module: Promise<Module> | undefined;
function load() {
  return (module ??= import(/* @vite-ignore */ new URL("relief-core.js", root).href)
    .then(({ default: create }) => create({
      locateFile: (file: string) => new URL(file, root).href,
    })));
}
let queue = Promise.resolve();
self.onmessage = ({ data }: MessageEvent<EngineRequest>) => {
  queue = queue.then(async () => {
    let response: EngineResponse;
    try {
      const engine = await load();
      const { image, ...request } = data;
      const json = new TextEncoder().encode(JSON.stringify(request));
      const bytes = image ? new Uint8Array(image) : new Uint8Array();
      const pointer = engine._relief_alloc(json.length);
      const source = engine._relief_alloc(bytes.length);
      try {
        engine.HEAPU8.set(json, pointer);
        engine.HEAPU8.set(bytes, source);
        engine._relief_request(pointer, json.length, source, bytes.length);
        const start = engine._relief_response_ptr();
        response = { id: data.id, ...JSON.parse(new TextDecoder().decode(
          engine.HEAPU8.subarray(start, start + engine._relief_response_len()),
        )) };
        if (response.ok && data.operation === "export") {
          const files: ArrayBuffer[] = [];
          for (let i = 0; i <= response.value.plate_count; i += 1) {
            const start = engine._relief_file_ptr(i);
            files.push(engine.HEAPU8.slice(start, start + engine._relief_file_len(i)).buffer);
          }
          engine._relief_clear_files();
          response.value = { files };
          self.postMessage(response, { transfer: files });
          return;
        }
      } finally {
        engine._relief_free(pointer, json.length);
        engine._relief_free(source, bytes.length);
      }
    } catch (error) {
      response = {
        id: data.id, ok: false,
        error: { code: "worker", detail: error instanceof Error ? error.message : "The geometry worker stopped." },
      };
    }
    self.postMessage(response);
  });
};
