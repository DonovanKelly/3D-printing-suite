/** Bundle a static, offline-capable workbench; Python is only a reference engine. */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { offline } from "./offline";

export default defineConfig({
  plugins: [react(), offline()],
  build: { outDir: "dist", emptyOutDir: true },
  base: "./",
});
