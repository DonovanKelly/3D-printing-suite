/** Regress an opaque SVG backing that masks detail in automatic selection,
 * then verify both recovery paths through rendered pixels and downloaded solids. */
import { test, expect, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { observeWorker, nextBuild } from "./worker-harness";

const fixture = fileURLToPath(new URL("../../tests/fixtures/white-backed-icon.svg", import.meta.url));
const python = process.env.RELIEF_TEST_PYTHON || fileURLToPath(new URL("../../.venv/bin/python", import.meta.url));

async function selectedPixels(page: Page, svg: string) {
  return page.evaluate(async (source) => {
    const image = new Image();
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(source)}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 100;
    const context = canvas.getContext("2d")!;
    context.drawImage(image, 0, 0, 100, 100);
    return [10, 25, 50].map((x) => context.getImageData(x, 50, 1, 1).data[0] < 128);
  }, svg);
}

test("closed white-backed SVG recovers its detail with dark selection and cutout reimport", async ({ page }, info) => {
  await observeWorker(page);
  await page.goto("/");
  const download = page.getByRole("button", { name: "Download 3MF", exact: true });
  await expect(download).toBeEnabled();
  const filled = await nextBuild(page, () => page.getByLabel("Upload artwork", { exact: true }).setInputFiles(fixture));
  await page.getByRole("button", { name: "Vector", exact: true }).click();
  expect(await selectedPixels(page, filled.vector_svg)).toEqual([true, true, true]);

  await page.getByText("Image selection", { exact: true }).click();
  const dark = await nextBuild(page, () => page.getByRole("combobox", { name: "Foreground", exact: true }).selectOption("dark"));
  expect(await selectedPixels(page, dark.vector_svg)).toEqual([true, false, true]);
  expect(dark.manifest.pieces[0].volume_mm3).toBeLessThan(filled.manifest.pieces[0].volume_mm3);

  const source = (await readFile(fixture, "utf8")).replace(/<path id="white-backing"[^>]*\/>/, "");
  const restored = await nextBuild(page, () => page.getByLabel("Upload artwork", { exact: true }).setInputFiles({
    name: "transparent-cutout.svg", mimeType: "image/svg+xml", buffer: Buffer.from(source),
  }));
  expect(restored.manifest.settings.foreground).toBe("auto");
  expect(await selectedPixels(page, restored.vector_svg)).toEqual([true, false, true]);
  expect(restored.vector_svg).toBe(dark.vector_svg);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("recovered-cutout.png"), fullPage: true });
  const file = page.waitForEvent("download");
  await download.click();
  const path = info.outputPath("recovered-cutout.3mf");
  await (await file).saveAs(path);
  execFileSync(python, ["-c", "import sys, trimesh; s=trimesh.load_scene(sys.argv[1], file_type='3mf'); assert len(s.geometry)==2; assert all(m.is_volume for m in s.geometry.values())", path]);
});
