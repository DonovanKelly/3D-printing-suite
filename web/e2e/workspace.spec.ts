/** Exercise portable documents and browser recovery through real UI and Wasm,
 * including failures that must preserve the open project and its source bytes. */
import { test, expect, type Page, type TestInfo } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { observeWorker, nextBuild } from "./worker-harness";

const artwork = fileURLToPath(new URL("../../tests/fixtures/gold-cutout.svg", import.meta.url));
const primary = (page: Page) => page.locator(".primary-button");
const name = (page: Page) => page.getByRole("textbox", { name: "Project name", exact: true });
const open = (page: Page) => page.getByLabel("Open workspace file", { exact: true });
const save = (page: Page) => page.getByRole("button", { name: "Save workspace", exact: true });

async function saveDocument(page: Page, info: TestInfo) {
  const downloaded = page.waitForEvent("download");
  await save(page).click();
  const file = await downloaded;
  const path = info.outputPath(file.suggestedFilename());
  await file.saveAs(path);
  return { file, path, document: JSON.parse(await readFile(path, "utf8")) };
}

async function prepare(page: Page) {
  await observeWorker(page);
  await page.goto("/");
  await expect(primary(page)).toBeEnabled();
}

test("project name is editable and names all exports without rebuilding geometry", async ({ page }, info) => {
  await prepare(page);
  const builds = await page.evaluate(() => window.engineTest.requests.length);
  await name(page).fill("Lake study");
  await name(page).press("Enter");
  expect(await page.evaluate(() => window.engineTest.requests.length)).toBe(builds);
  const workspace = await saveDocument(page, info);
  expect(workspace.file.suggestedFilename()).toBe("Lake study.print-workspace");
  expect(workspace.document.name).toBe("Lake study");
  expect(Buffer.from(workspace.document.artwork.base64, "base64").toString()).toContain("<svg");
  let download = page.waitForEvent("download");
  await primary(page).click();
  expect((await download).suggestedFilename()).toBe("Lake study.3mf");
  await name(page).fill("Lake revision");
  await name(page).press("Enter");
  await expect(page.getByRole("link", { name: "Download 3MF again" })).toHaveAttribute("download", "Lake revision.3mf");
  download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download full print pack" }).click();
  expect((await download).suggestedFilename()).toBe("Lake revision-print-pack.zip");
  await name(page).fill("   ");
  await name(page).press("Enter");
  await expect(name(page)).toHaveValue("Untitled project");
  await name(page).fill("../My:piece?");
  const sanitized = await saveDocument(page, info);
  expect(sanitized.file.suggestedFilename()).toBe("-My-piece-.print-workspace");
  await name(page).fill("Lake study");
  await saveDocument(page, info);
  await page.screenshot({ path: info.outputPath("workspace-controls.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("a portable workspace restores exact artwork, settings and tab in a fresh offline tab", async ({ page, context }, info) => {
  await prepare(page);
  await nextBuild(page, () => page.getByLabel("Upload artwork", { exact: true }).setInputFiles(artwork));
  await name(page).fill("Golden puzzle");
  await name(page).press("Enter");
  await nextBuild(page, () => page.getByRole("button", { name: "Puzzle", exact: true }).click());
  await nextBuild(page, () => page.getByLabel("Artwork color", { exact: true }).fill("#426a95"));
  await page.getByRole("button", { name: "Assembly", exact: true }).click();
  const saved = await saveDocument(page, info);
  expect(Buffer.from(saved.document.artwork.base64, "base64")).toEqual(await readFile(artwork));
  expect(saved.document.settings.layout).toBe("puzzle");
  expect(saved.document.settings.artwork_color).toBe("#426a95");
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
  await context.setOffline(true);
  const fresh = await context.newPage();
  await prepare(fresh);
  await expect(name(fresh)).toHaveValue("Alpine study");
  const requests: string[] = [];
  fresh.on("request", (request) => { if (request.method() !== "GET") requests.push(request.url()); });
  const restored = await nextBuild(fresh, () => open(fresh).setInputFiles(saved.path));
  await expect(primary(fresh)).toBeEnabled();
  await expect(name(fresh)).toHaveValue("Golden puzzle");
  await expect(fresh.getByRole("button", { name: "Assembly", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(restored.manifest.settings).toEqual(saved.document.settings);
  const second = await saveDocument(fresh, info);
  expect(second.document).toEqual(saved.document);
  const download = fresh.waitForEvent("download");
  await primary(fresh).click();
  expect((await download).suggestedFilename()).toMatch(/^Golden puzzle.*\.(zip|3mf)$/);
  if (restored.manifest.plate_count > 1)
    await expect(fresh.getByRole("link", { name: /^Plate 1 ·/ })).toHaveAttribute("download", "Golden puzzle-plate-01.3mf");
  expect(requests).toEqual([]);
});

test("bad documents preserve the current project; valid documents can be canceled then opened", async ({ page }, info) => {
  await prepare(page);
  const original = await saveDocument(page, info);
  await name(page).fill("Keep my edits");
  await name(page).press("Enter");
  const cases = [
    { text: "{", message: "not a readable workspace" },
    { text: JSON.stringify({ ...original.document, version: 99 }), message: "version is not supported" },
    { text: JSON.stringify({ ...original.document, settings: { ...original.document.settings, width_mm: "180" } }), message: "invalid width_mm" },
    { text: JSON.stringify({ ...original.document, settings: { ...original.document.settings, layout: "unknown" } }), message: "invalid layout" },
    { text: JSON.stringify({ ...original.document, artwork: { ...original.document.artwork, base64: "!bad" } }), message: "artwork is missing, damaged" },
    { text: " ".repeat(17 * 1024 * 1024 + 1), message: "smaller than 17 MiB" },
  ];
  for (const entry of cases) {
    await open(page).setInputFiles({ name: "broken.print-workspace", mimeType: "application/json", buffer: Buffer.from(entry.text) });
    await expect(page.getByRole("alert")).toContainText(entry.message);
    await expect(name(page)).toHaveValue("Keep my edits");
    await expect(primary(page)).toBeEnabled();
  }
  page.once("dialog", (dialog) => dialog.dismiss());
  await open(page).setInputFiles(original.path);
  await expect(open(page)).toBeEnabled();
  await expect(name(page)).toHaveValue("Keep my edits");
  page.once("dialog", (dialog) => dialog.accept());
  await nextBuild(page, () => open(page).setInputFiles(original.path));
  await expect(name(page)).toHaveValue("Alpine study");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(primary(page)).toBeEnabled();
});

test("optional recovery restores source and tab after reload and can be removed", async ({ page, context }, info) => {
  await prepare(page);
  await nextBuild(page, () => page.getByLabel("Upload artwork", { exact: true }).setInputFiles(artwork));
  await name(page).fill("Return to this");
  await page.getByRole("button", { name: "Vector", exact: true }).click();
  await page.getByRole("checkbox", { name: "Restore on return" }).check();
  await expect(page.locator(".workspace-status")).toHaveText("Saved in this browser");
  await name(page).fill("Latest revision");
  await name(page).press("Enter");
  await expect(page.locator(".workspace-status")).toHaveText("Saved in this browser");
  await page.reload();
  await expect(primary(page)).toBeEnabled();
  await expect(name(page)).toHaveValue("Latest revision");
  await expect(page.getByRole("button", { name: "Vector", exact: true })).toHaveAttribute("aria-pressed", "true");
  const restored = await saveDocument(page, info);
  expect(Buffer.from(restored.document.artwork.base64, "base64")).toEqual(await readFile(artwork));
  const another = await context.newPage();
  await prepare(another);
  await expect(name(another)).toHaveValue("Latest revision");
  await another.close();
  await page.getByRole("checkbox", { name: "Restore on return" }).uncheck();
  await expect(page.locator(".workspace-status")).toHaveText("Browser copy removed");
  await page.reload();
  await expect(primary(page)).toBeEnabled();
  await expect(name(page)).toHaveValue("Alpine study");
  await expect(page.getByRole("checkbox", { name: "Restore on return" })).not.toBeChecked();
});

test("browser storage failure leaves portable files usable, including import while the name is focused", async ({ page }, info) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "indexedDB", { get() { throw Error("Storage unavailable"); } });
  });
  await prepare(page);
  await expect(page.getByRole("alert")).toContainText("Could not restore browser storage");
  await page.getByRole("checkbox", { name: "Restore on return" }).check();
  await expect(page.locator(".workspace-status")).toContainText("Browser save failed");
  await name(page).fill("Portable backup");
  const saved = await saveDocument(page, info);
  expect(saved.document.name).toBe("Portable backup");
  await name(page).fill("Changed");
  page.once("dialog", (dialog) => dialog.accept());
  await nextBuild(page, () => open(page).setInputFiles(saved.path));
  await expect(name(page)).toHaveValue("Portable backup");
  await expect(primary(page)).toBeEnabled();
});

test("unfinished settings can be saved, reopened and repaired without resetting image selection", async ({ page }, info) => {
  await prepare(page);
  const width = page.getByRole("spinbutton", { name: "Width (mm)", exact: true });
  await width.fill("1");
  await nextBuild(page, () => width.press("Enter"), 422);
  await expect(primary(page)).toBeDisabled();
  const saved = await saveDocument(page, info);
  expect(saved.document.settings.width_mm).toBe(1);
  await width.fill("180");
  await nextBuild(page, () => width.press("Enter"));
  page.once("dialog", (dialog) => dialog.accept());
  await nextBuild(page, () => open(page).setInputFiles(saved.path), 422);
  await expect(width).toHaveValue("1");
  await expect(primary(page)).toBeDisabled();
  await width.fill("160");
  await nextBuild(page, () => width.press("Enter"));
  await expect(primary(page)).toBeEnabled();
});

test("a failed browser write preserves the previous recovery copy and a later edit retries", async ({ page, context }) => {
  await prepare(page);
  await name(page).fill("Last good copy");
  await name(page).press("Enter");
  await page.getByRole("checkbox", { name: "Restore on return" }).check();
  await expect(page.locator(".workspace-status")).toHaveText("Saved in this browser");
  await page.evaluate(() => {
    const original = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (...args: Parameters<typeof original>) {
      if (sessionStorage.getItem("fail-storage") === "yes")
        throw new DOMException("Storage full", "QuotaExceededError");
      return original.apply(this, args);
    };
    sessionStorage.setItem("fail-storage", "yes");
  });
  await name(page).fill("Unsaved browser edit");
  await name(page).press("Enter");
  await expect(page.locator(".workspace-status")).toContainText("Browser save failed");
  const recovered = await context.newPage();
  await prepare(recovered);
  await expect(name(recovered)).toHaveValue("Last good copy");
  await recovered.close();
  await page.evaluate(() => sessionStorage.removeItem("fail-storage"));
  await name(page).fill("Storage recovered");
  await name(page).press("Enter");
  await expect(page.locator(".workspace-status")).toHaveText("Saved in this browser");
  await page.reload();
  await expect(primary(page)).toBeEnabled();
  await expect(name(page)).toHaveValue("Storage recovered");
});
