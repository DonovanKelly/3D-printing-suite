/** Verify border filament assignment in the real Wasm UI, downloaded Bambu
 * projects, and versioned workspace/recovery data, including old two-color files. */
import { test, expect, type Page, type TestInfo } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { observeWorker, nextBuild } from "./worker-harness";

const primary = (page: Page) => page.locator(".primary-button");
const material = (page: Page) => page.getByRole("combobox", { name: "Border material", exact: true });
const python = process.env.RELIEF_TEST_PYTHON || fileURLToPath(new URL("../../.venv/bin/python", import.meta.url));

async function saveWorkspace(page: Page, info: TestInfo) {
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save workspace", exact: true }).click();
  const path = info.outputPath("colors.print-workspace");
  await (await downloaded).saveAs(path);
  return { path, document: JSON.parse(await readFile(path, "utf8")) };
}

test.beforeEach(async ({ page }) => {
  await observeWorker(page);
  await page.goto("/");
  await expect(primary(page)).toBeEnabled();
});

test("border can follow background or use a third exported filament, then return to artwork", async ({ page }, info) => {
  const background = await nextBuild(page, () => material(page).selectOption("background"));
  expect(background.meshes.map((m: { material: string }) => m.material)).toEqual(["background", "artwork"]);
  const baseZ = background.meshes[0].vertices.filter((_: number, i: number) => i % 3 === 2);
  expect(Math.max(...baseZ)).toBeCloseTo(background.manifest.settings.base_mm + background.manifest.settings.frame_height_mm);
  const colored = await nextBuild(page, () => page.getByLabel("Background color", { exact: true }).fill("#526c8a"));
  expect(colored.assembly_svg.match(/fill="#526c8a"/g)?.length).toBeGreaterThanOrEqual(2);
  await nextBuild(page, () => material(page).selectOption("custom"));
  const third = await nextBuild(page, () => page.getByLabel("Border color", { exact: true }).fill("#d5a341"));
  expect(third.meshes.map((m: { material: string }) => m.material)).toEqual(["background", "artwork", "border"]);
  expect(third.manifest.pieces[0].extents_mm).toEqual(background.manifest.pieces[0].extents_mm);
  expect(third.manifest.pieces[0].volume_mm3).toBeCloseTo(background.manifest.pieces[0].volume_mm3, 4);
  expect(third.assembly_svg).toContain('fill="#d5a341"');
  await expect(page.locator(".metrics > div").filter({ hasText: "Materials" }).locator("dd")).toHaveText("3");
  await page.getByRole("button", { name: "View from top", exact: true }).click();
  await page.screenshot({ path: info.outputPath("third-border-color.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const downloaded = page.waitForEvent("download");
  await primary(page).click();
  const path = info.outputPath("third-border-color.3mf");
  await (await downloaded).saveAs(path);
  const exported = JSON.parse(execFileSync(python, ["-c", `
import json, sys
from zipfile import ZipFile
from xml.etree import ElementTree as ET
with ZipFile(sys.argv[1]) as z:
    settings = json.loads(z.read("Metadata/project_settings.config"))
    config = ET.fromstring(z.read("Metadata/model_settings.config"))
    settings["parts"] = {p.find("metadata[@key='name']").attrib["value"]: p.find("metadata[@key='extruder']").attrib["value"] for p in config.findall("object/part")}
    print(json.dumps(settings))
`, path], { encoding: "utf8" }));
  expect(exported.filament_colour).toEqual(["#526C8A", "#252B28", "#D5A341"]);
  expect(exported.parts).toEqual({ Background: "1", Artwork: "2", Border: "3" });
  expect(exported.nozzle_diameter).toEqual(["0.4"]);
  const saved = await saveWorkspace(page, info);
  expect(saved.document.version).toBe(2);
  const returned = await nextBuild(page, () => material(page).selectOption("artwork"));
  expect(returned.meshes.map((m: { material: string }) => m.material)).toEqual(["background", "artwork"]);
  await expect(page.locator(".download-again")).toHaveCount(0);
  page.once("dialog", (dialog) => dialog.accept());
  await nextBuild(page, () => page.getByLabel("Open workspace file", { exact: true }).setInputFiles(saved.path));
  await expect(material(page)).toHaveValue("custom");
  await expect(page.getByLabel("Border color", { exact: true })).toHaveValue("#d5a341");
  await page.getByRole("checkbox", { name: "Restore on return" }).check();
  await expect(page.locator(".workspace-status")).toHaveText("Saved in this browser");
  await page.reload();
  await expect(primary(page)).toBeEnabled();
  await expect(material(page)).toHaveValue("custom");
  await expect(page.getByLabel("Border color", { exact: true })).toHaveValue("#d5a341");
});

test("removing a border omits the third material and re-enabling restores the selected color", async ({ page }) => {
  await nextBuild(page, () => material(page).selectOption("custom"));
  const removed = await nextBuild(page, () => page.getByRole("combobox", { name: "Border", exact: true }).selectOption("none"));
  expect(removed.meshes.some((m: { material: string }) => m.material === "border")).toBe(false);
  await expect(material(page)).toBeDisabled();
  await expect(page.getByLabel("Border color", { exact: true })).toBeDisabled();
  const restored = await nextBuild(page, () => page.getByRole("combobox", { name: "Border", exact: true }).selectOption("flat"));
  expect(restored.manifest.settings.border_material).toBe("custom");
  expect(restored.meshes.some((m: { material: string }) => m.material === "border")).toBe(true);
  await expect(material(page)).toBeEnabled();
});

test("version 1 files and browser recovery migrate to the original border color; malformed new settings recover", async ({ page }, info) => {
  const saved = await saveWorkspace(page, info);
  const legacy = { ...saved.document, version: 1 };
  delete legacy.settings.border_material;
  delete legacy.settings.border_color;
  legacy.name = "Original two-color workspace";
  const document = (value: unknown) => ({ name: "legacy.print-workspace", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(value)) });
  await nextBuild(page, () => page.getByLabel("Open workspace file", { exact: true }).setInputFiles(document(legacy)));
  await expect(material(page)).toHaveValue("artwork");
  await expect(page.getByRole("textbox", { name: "Project name" })).toHaveValue(legacy.name);
  await page.evaluate(async ({ settings, name, view }) => {
    await new Promise<void>((resolve, reject) => {
      const request = indexedDB.open("3d-printing-suite-workspaces", 1);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const db = request.result;
        const tx = db.transaction("recovery", "readwrite");
        tx.objectStore("recovery").put({ version: 1, settings, name, view, file: null }, "last");
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => reject(tx.error);
      };
    });
  }, legacy);
  await page.reload();
  await expect(primary(page)).toBeEnabled();
  await expect(material(page)).toHaveValue("artwork");
  await expect(page.getByRole("checkbox", { name: "Restore on return" })).toBeChecked();
  const upgraded = await saveWorkspace(page, info);
  expect(upgraded.document.version).toBe(2);
  expect(upgraded.document.settings.border_material).toBe("artwork");
  for (const values of [{ border_material: "unknown" }, { border_color: "invalid" }, { border_color: undefined }]) {
    const bad = { ...upgraded.document, settings: { ...upgraded.document.settings, ...values } };
    await page.getByLabel("Open workspace file", { exact: true }).setInputFiles(document(bad));
    await expect(page.getByRole("alert")).toContainText("invalid border_");
    await expect(material(page)).toHaveValue("artwork");
    await expect(primary(page)).toBeEnabled();
  }
  await nextBuild(page, () => page.getByLabel("Open workspace file", { exact: true }).setInputFiles(document(upgraded.document)));
  await expect(page.getByRole("alert")).toHaveCount(0);
});
