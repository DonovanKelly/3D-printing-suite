/** Precache the exact build, including Wasm and fonts, without any runtime CDN. */
import type { Plugin } from "vite";
import { readdir, readFile, writeFile } from "node:fs/promises";
import { join, relative } from "node:path";
import { createHash } from "node:crypto";
export function offline(): Plugin {
  let outDir = "";
  return {
    name: "relief-offline",
    configResolved(config) { outDir = join(config.root, config.build.outDir); },
    async closeBundle() {
      const walk = async (folder: string): Promise<string[]> => (await Promise.all(
        (await readdir(folder, { withFileTypes: true })).map((entry) =>
          entry.isDirectory() ? walk(join(folder, entry.name)) : [join(folder, entry.name)],
        ),
      )).flat();
      const files = (await walk(outDir)).filter((path) => !path.endsWith("/sw.js")).sort();
      const hash = createHash("sha256");
      for (const file of files) hash.update(await readFile(file));
      const assets = files.map((file) => `./${relative(outDir, file)}`);
      await writeFile(join(outDir, "sw.js"), `/** Cache only this static build; never store imported artwork. */
const prefix = "relief-studio:" + self.registration.scope;
const name = prefix + ${JSON.stringify(hash.digest("hex").slice(0, 16))};
const assets = ${JSON.stringify(assets)};
self.addEventListener("install", event => event.waitUntil(caches.open(name).then(cache => cache.addAll(assets))));
self.addEventListener("activate", event => event.waitUntil((async () => {
  for (const key of await caches.keys()) if (key.startsWith(prefix) && key !== name) await caches.delete(key);
  await self.clients.claim();
})()));
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (!url.href.startsWith(self.registration.scope)) return;
  event.respondWith((async () => {
    const cache = await caches.open(name);
    const path = event.request.mode === "navigate" ? new URL("index.html", self.registration.scope).href : event.request;
    return await cache.match(path) || fetch(event.request);
  })());
});
`);
    },
  };
}
