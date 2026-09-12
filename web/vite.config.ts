/** Bundle the workbench into the Python package; proxy local development to its API. */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "../src/relief_studio/static", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
