/** Drive contour splitting, overflow recovery, fragment exports, and saved workspaces
 * through the real browser worker. Desktop/mobile both use the same geometry. */
import { test, expect, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import type { Preview } from "../src/types";
import { observeWorker, nextBuild } from "./worker-harness";

const primary = (page: Page) => page.locator(".primary-button");
const fixture = fileURLToPath(new URL("../../tests/fixtures/contour-fork.svg", import.meta.url));

async function build(page: Page, action: () => Promise<unknown>, status = 200): Promise<Preview> {
  const result = await nextBuild(page, action, status);
  if (status === 200) await expect(primary(page)).toBeEnabled();
  else await expect(primary(page)).toBeDisabled();
  return result;
}
async function number(page: Page, name: string, value: number, status = 200) {
  return build(page, async () => {
    const field = page.getByRole("spinbutton", { name, exact: true });
    await field.fill(String(value));
    await field.press("Enter");
  }, status);
}
test.beforeEach(async ({ page }) => {
  await observeWorker(page);
  await page.goto("/");
  await expect(primary(page)).toBeEnabled();
  await build(page, () => page.getByLabel("Upload artwork", { exact: true }).setInputFiles(fixture));
});

test("large contours recover by splitting and preserve the layout across shape changes", async ({ page }, info) => {
  await build(page, () => page.getByRole("combobox", { name: "Backing shape", exact: true }).selectOption("contour"));
  await number(page, "Width (mm)", 540);
  await number(page, "Height (mm)", 540, 422);
  await expect(page.getByRole("alert")).toContainText("Choose Tiles or Puzzle");
  let preview = await build(page, () => page.getByRole("button", { name: "Tiles", exact: true }).click());
  expect(preview.manifest.piece_count).toBeGreaterThan(1);
  expect(preview.manifest.pieces.every((p) => p.extents_mm[0] <= 90.0001 && p.extents_mm[1] <= 90.0001)).toBe(true);
  await expect(page.getByRole("button", { name: "Pieces", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".canvas-heading")).toContainText("554.0 × 554.0 mm · finished");
  const many = preview.manifest.piece_count;
  preview = await build(page, () => page.getByRole("combobox", { name: "Split", exact: true }).selectOption("bed"));
  expect(preview.manifest.piece_count).toBeLessThan(many);
  expect(preview.manifest.pieces.every((p) => p.extents_mm[0] <= 230.0001 && p.extents_mm[1] <= 230.0001)).toBe(true);
  preview = await build(page, () => page.getByRole("button", { name: "Puzzle", exact: true }).click());
  expect(preview.manifest.settings.shape).toBe("contour");
  expect(preview.manifest.settings.split_mode).toBe("bed");
  await build(page, () => page.getByRole("combobox", { name: "Backing shape", exact: true }).selectOption("rectangle"));
  preview = await build(page, () => page.getByRole("combobox", { name: "Backing shape", exact: true }).selectOption("contour"));
  expect(preview.manifest.settings.layout).toBe("puzzle");
  await page.getByRole("button", { name: "Relief", exact: true }).click();
  await page.getByRole("button", { name: "View from top", exact: true }).click();
  await page.screenshot({ path: info.outputPath("large-contour-assembled.png"), fullPage: true });
  await page.getByRole("button", { name: "Pieces", exact: true }).click();
  await page.getByRole("button", { name: "View from top", exact: true }).click();
  await page.screenshot({ path: info.outputPath("large-contour-pieces.png"), fullPage: true });
  await page.getByRole("button", { name: "Assembly", exact: true }).click();
  await expect(page.getByRole("img", { name: "Front-view assembly map with piece labels" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const download = page.waitForEvent("download");
  await primary(page).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/\.zip$/);
  await file.saveAs(info.outputPath("large-contour.zip"));
  await expect(page.getByRole("link", { name: /^Plate \d/ })).toHaveCount(preview.manifest.plate_count);
});

test("concave cuts label every fragment and reopen the same contour workspace", async ({ page, context }, info) => {
  await build(page, () => page.getByRole("button", { name: "Tiles", exact: true }).click());
  await build(page, () => page.getByRole("combobox", { name: "Split", exact: true }).selectOption("manual"));
  await number(page, "Cols", 1);
  const preview = await build(page, () => page.getByRole("combobox", { name: "Backing shape", exact: true }).selectOption("contour"));
  expect(preview.manifest.pieces.map((p) => p.id)).toEqual(["r01-c01-p01", "r01-c01-p02", "r02-c01"]);
  expect(preview.manifest.grid).toEqual({ columns: 1, rows: 2 });
  for (const p of preview.manifest.pieces) expect(preview.assembly_svg).toContain(`>${p.id}</text>`);
  await number(page, "Rows", 1, 422);
  await expect(page.getByRole("alert")).toContainText("at least two pieces");
  await number(page, "Rows", 2);
  await number(page, "Clearance (mm)", 0);
  await page.getByRole("button", { name: "Assembly", exact: true }).click();
  await page.screenshot({ path: info.outputPath("contour-fragments-map.png"), fullPage: true });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save workspace", exact: true }).click();
  const workspace = await download;
  const path = info.outputPath("contour.print-workspace");
  await workspace.saveAs(path);
  const document = JSON.parse(await readFile(path, "utf8"));
  expect(document.settings.shape).toBe("contour");
  expect(document.settings.layout).toBe("tiles");
  expect(document.settings.clearance_mm).toBe(0);
  const fresh = await context.newPage();
  await observeWorker(fresh);
  await fresh.goto("/");
  await expect(primary(fresh)).toBeEnabled();
  const restored = await build(fresh, () => fresh.getByLabel("Open workspace file", { exact: true }).setInputFiles(path));
  expect(restored.manifest.settings).toEqual(document.settings);
  expect(restored.manifest.pieces.map((p) => p.id)).toEqual(preview.manifest.pieces.map((p) => p.id));
});
