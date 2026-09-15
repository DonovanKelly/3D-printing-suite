/** Regress real upload/edit/recovery/export flows against Python, with isolated browser state. */
import { test, expect, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { delimiter } from "node:path";
import { fileURLToPath } from "node:url";
import type { Preview } from "../src/types";

const gold = fileURLToPath(
  new URL("../../tests/fixtures/gold-cutout.svg", import.meta.url),
);
const primary = (page: Page) => page.locator(".primary-button");

async function rebuild(
  page: Page,
  action: () => Promise<unknown>,
  status = 200,
) {
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/api/preview") && r.status() === status,
  );
  await action();
  const body = await (await response).json();
  if (status === 200) await expect(primary(page)).toBeEnabled();
  else await expect(page.getByRole("alert")).toBeVisible();
  return body;
}

async function number(
  page: Page,
  name: string,
  value: number,
  status = 200,
): Promise<Preview> {
  return rebuild(
    page,
    async () => {
      const field = page.getByRole("spinbutton", { name, exact: true });
      await field.fill(String(value));
      await field.press("Enter");
    },
    status,
  );
}

async function upload(page: Page, path = gold): Promise<Preview> {
  return rebuild(page, () =>
    page.getByLabel("Upload artwork", { exact: true }).setInputFiles(path),
  );
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(primary(page)).toBeEnabled();
});

test("a new SVG resets incompatible selection while preserving geometry", async ({
  page,
}) => {
  await number(page, "Border width (mm)", 8);
  await page.getByText("Image selection", { exact: true }).click();
  await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Foreground", exact: true })
      .selectOption("light"),
  );
  await rebuild(page, () =>
    page.getByRole("slider", { name: "Threshold", exact: true }).press("Home"),
  );
  await rebuild(page, () =>
    page.getByRole("switch", { name: "Invert artwork", exact: true }).click(),
  );
  const result = await upload(page);
  expect(result.manifest.settings.foreground).toBe("auto");
  expect(result.manifest.settings.threshold).toBe(128);
  expect(result.manifest.settings.invert).toBe(false);
  expect(result.manifest.settings.frame_width_mm).toBe(8);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("empty selection offers reset and restores a downloadable two-color relief", async ({
  page,
}, info) => {
  await upload(page);
  await page.getByText("Image selection", { exact: true }).click();
  const error = await rebuild(
    page,
    () =>
      page
        .getByRole("combobox", { name: "Foreground", exact: true })
        .selectOption("light"),
    422,
  );
  expect(error.code).toBe("image_selection");
  await expect(primary(page)).toBeDisabled();
  await expect(page.getByRole("alert")).toContainText("previous valid preview");
  await page.screenshot({
    path: info.outputPath("selection-error.png"),
    fullPage: true,
  });
  const restored = await rebuild(page, () =>
    page
      .getByRole("alert")
      .getByRole("button", { name: "Reset image selection" })
      .click(),
  );
  expect(restored.manifest.pieces[0].material_parts).toBe(2);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("selection-restored.png"),
    fullPage: true,
  });
  const download = page.waitForEvent("download");
  await primary(page).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/\.3mf$/);
  const path = info.outputPath("recovered.3mf");
  await file.saveAs(path);
  expect((await readFile(path)).subarray(0, 2).toString()).toBe("PK");
});

test("numeric drafts do not build until applied, cancel cleanly, and block invalid exports", async ({
  page,
}) => {
  let requests = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/api/preview")) requests += 1;
  });
  const width = page.getByRole("spinbutton", {
    name: "Width (mm)",
    exact: true,
  });
  await width.fill("");
  await expect(width).toHaveValue("");
  await width.fill("1");
  await page.waitForTimeout(800);
  expect(requests).toBe(0);
  await expect(primary(page)).toBeDisabled();
  await width.press("Escape");
  await expect(width).toHaveValue("180");
  await expect(primary(page)).toBeEnabled();
  await number(page, "Width (mm)", 1, 422);
  await expect(page.getByRole("alert")).toContainText("Width (mm)");
  await expect(primary(page)).toBeDisabled();
  await width.fill("160");
  const fixed = await rebuild(page, () => width.press("Tab"));
  expect(fixed.manifest.settings.width_mm).toBe(160);
  await width.fill("");
  await width.press("Tab");
  await expect(width).toHaveValue("160");
});

test("border off/narrow/wide and rounded centered hanging keep valid exports", async ({
  page,
}) => {
  await upload(page);
  let result = await number(page, "Border width (mm)", 0);
  expect(result.manifest.settings.frame).toBe(false);
  result = await number(page, "Border width (mm)", 0.5);
  expect(result.manifest.settings.frame).toBe(true);
  await number(page, "Border width (mm)", 8);
  await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Border", exact: true })
      .selectOption("rounded"),
  );
  await number(page, "Corner radius (mm)", 90);
  result = await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Hanging", exact: true })
      .selectOption("loops"),
  );
  expect(result.manifest.pieces[0].extents_mm).toEqual([180, 189, 4]);
});

test("tiles and puzzles split the sample and download separate plate objects", async ({
  page,
}, info) => {
  let result: Preview = await rebuild(page, () =>
    page.getByRole("button", { name: "Tiles", exact: true }).click(),
  );
  expect(result.manifest.piece_count).toBe(4);
  result = await rebuild(page, () =>
    page.getByRole("button", { name: "Puzzle", exact: true }).click(),
  );
  expect(result.manifest.piece_count).toBe(9);
  await expect(
    page.getByRole("button", { name: "Pieces", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  result = await rebuild(page, () =>
    page.getByRole("button", { name: "Shuffle pattern", exact: true }).click(),
  );
  expect(result.manifest.settings.puzzle_seed).toBe(2);
  result = await number(page, "Max piece size (mm)", 60);
  expect(result.manifest.piece_count).toBe(16);
  expect(
    Math.max(
      ...result.manifest.pieces.flatMap((p) => p.extents_mm.slice(0, 2)),
    ),
  ).toBeLessThanOrEqual(60);
  result = await number(page, "Width (mm)", 360);
  expect(result.manifest.plate_count).toBeGreaterThan(1);
  await expect(primary(page)).toContainText("plates (ZIP)");
  const download = page.waitForEvent("download");
  const exported = page.waitForResponse(
    (r) => r.url().includes("/api/export/") && r.status() === 200,
  );
  await primary(page).click();
  await (await download).saveAs(info.outputPath("puzzle-plates.zip"));
  const urls = await (await exported).json();
  expect(urls.plate_urls).toHaveLength(result.manifest.plate_count);
  for (const url of urls.plate_urls)
    expect((await page.request.get(url)).ok()).toBe(true);
});

test("a newer preview wins when an older response arrives late", async ({
  page,
}) => {
  let first = true;
  let release!: () => void;
  let captured!: () => void;
  const capturedResponse = new Promise<void>((resolve) => {
    captured = resolve;
  });
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/preview", async (route) => {
    if (!first) return route.continue();
    first = false;
    const response = await route.fetch();
    captured();
    await gate;
    await route.fulfill({ response });
  });
  const field = page.getByRole("spinbutton", {
    name: "Width (mm)",
    exact: true,
  });
  await field.fill("160");
  await field.press("Enter");
  await capturedResponse;
  await number(page, "Width (mm)", 170);
  release();
  await page.waitForTimeout(300);
  await expect(page.locator(".canvas-heading")).toContainText("170 × 180 mm");
  await expect(primary(page)).toBeEnabled();
});

test("preview requests recover from a busy worker and a temporary server failure", async ({
  page,
}) => {
  let calls = 0;
  await page.route("**/api/preview", async (route) => {
    calls += 1;
    if (calls === 1)
      return route.fulfill({ status: 409, json: { detail: "Busy" } });
    if (calls === 2)
      return route.fulfill({
        status: 500,
        json: { detail: "Temporary failure" },
      });
    return route.continue();
  });
  await number(page, "Width (mm)", 160, 500);
  await expect(primary(page)).toBeDisabled();
  await rebuild(page, () =>
    page.getByRole("button", { name: "Rebuild preview", exact: true }).click(),
  );
  expect(calls).toBe(3);
});

test("preview modes remain usable without horizontal overflow", async ({
  page,
}) => {
  for (const mode of ["Pieces", "Assembly", "Vector", "Relief"]) {
    await page.getByRole("button", { name: mode, exact: true }).click();
    await expect(
      page.getByRole("button", { name: mode, exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
  await page
    .getByRole("button", { name: "View from top", exact: true })
    .click();
  const canvas = page.locator("canvas");
  const beforeZoom = await canvas.screenshot();
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  expect((await canvas.screenshot()).equals(beforeZoom)).toBe(false);
  const beforeWheel = await canvas.screenshot();
  await canvas.hover();
  await page.mouse.wheel(0, -300);
  await expect
    .poll(async () => (await canvas.screenshot()).equals(beforeWheel))
    .toBe(false);
});

const privateSources = (process.env.RELIEF_TEST_ARTWORK || "")
  .split(delimiter)
  .filter(Boolean);
for (const [index, source] of privateSources.entries()) {
  test(`private SVG ${index + 1} uploads after incompatible image selection`, async ({
    page,
  }) => {
    await page.getByText("Image selection", { exact: true }).click();
    await rebuild(page, () =>
      page
        .getByRole("combobox", { name: "Foreground", exact: true })
        .selectOption("light"),
    );
    const result = await upload(page, source);
    expect(result.manifest.settings.foreground).toBe("auto");
    expect(result.manifest.pieces[0].material_parts).toBe(2);
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
}

test("built-in sample supports contour directly and recovers from disconnected artwork", async ({
  page,
}, info) => {
  const initial: Preview = await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Backing shape", exact: true })
      .selectOption("contour"),
  );
  expect(initial.manifest.piece_count).toBe(1);
  await number(page, "Padding (mm)", 0);
  const plain: Preview = await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Border", exact: true })
      .selectOption("none"),
  );
  expect(plain.manifest.pieces[0].extents_mm[1]).toBeCloseTo(180, 1);
  await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Border", exact: true })
      .selectOption("rounded"),
  );
  await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Hanging", exact: true })
      .selectOption("loops"),
  );
  await rebuild(
    page,
    () =>
      page.getByLabel("Upload artwork", { exact: true }).setInputFiles({
        name: "disconnected.svg",
        mimeType: "image/svg+xml",
        buffer: Buffer.from(
          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
            '<circle cx="15" cy="50" r="10"/><circle cx="85" cy="50" r="10"/></svg>',
        ),
      }),
    422,
  );
  await expect(page.getByRole("alert")).toContainText("disconnected islands");
  await expect(primary(page)).toBeDisabled();
  const restored: Preview = await rebuild(page, () =>
    page.getByRole("button", { name: "Use sample artwork", exact: true }).click(),
  );
  expect(restored.manifest.settings.shape).toBe("contour");
  expect(restored.manifest.settings.frame_profile).toBe("rounded");
  expect(restored.manifest.settings.hanging).toBe("loops");
  expect(restored.manifest.pieces[0].material_parts).toBe(2);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByRole("button", { name: "View from top", exact: true }).click();
  await page.screenshot({
    path: info.outputPath("sample-contour-rounded.png"),
    fullPage: true,
  });
  const download = page.waitForEvent("download");
  await primary(page).click();
  const path = info.outputPath("sample-contour.3mf");
  await (await download).saveAs(path);
  expect((await readFile(path)).subarray(0, 2).toString()).toBe("PK");
});

test("contour bezels expand the icon, keep one piece, and recover from bed overflow", async ({
  page,
}, info) => {
  const icon = fileURLToPath(
    new URL("../../tests/fixtures/contour-icon.svg", import.meta.url),
  );
  await upload(page, icon);
  await rebuild(page, () =>
    page.getByRole("button", { name: "Puzzle", exact: true }).click(),
  );
  const initial: Preview = await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Backing shape", exact: true })
      .selectOption("contour"),
  );
  expect(initial.manifest.piece_count).toBe(1);
  expect(initial.manifest.settings.layout).toBe("plaque");
  await expect(
    page.getByRole("button", { name: "Tiles", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Puzzle", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("spinbutton", { name: "Corner radius (mm)", exact: true }),
  ).toHaveCount(0);
  const wider = await number(page, "Border width (mm)", 8);
  expect(wider.vector_svg).not.toBe(initial.vector_svg); // Its viewport expands, while the traced paths stay the same.
  const tracePath = (svg: string) =>
    svg.match(/<path d="([^"]+)" fill="black"/)?.[1];
  expect(tracePath(wider.vector_svg)).toBeTruthy();
  expect(tracePath(wider.vector_svg)).toBe(tracePath(initial.vector_svg));
  expect(wider.manifest.pieces[0].extents_mm[1]).toBeCloseTo(
    initial.manifest.pieces[0].extents_mm[1] + 8,
    2,
  );
  await number(page, "Border height (mm)", 3);
  for (const profile of ["none", "rounded", "beaded"]) {
    await rebuild(page, () =>
      page
        .getByRole("combobox", { name: "Border", exact: true })
        .selectOption(profile),
    );
  }
  await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Hanging", exact: true })
      .selectOption("keyholes"),
  );
  await expect(
    page.getByRole("spinbutton", {
      name: "Background thickness (mm)",
      exact: true,
    }),
  ).toHaveValue("5");
  await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Hanging", exact: true })
      .selectOption("loops"),
  );
  await number(page, "Height (mm)", 220, 422);
  await expect(page.getByRole("alert")).toContainText(
    "including its bezel and loop",
  );
  await expect(primary(page)).toBeDisabled();
  const restored = await number(page, "Height (mm)", 180);
  await expect(page.locator(".canvas-heading")).toContainText("finished");
  expect(restored.manifest.piece_count).toBe(1);
  await page
    .getByRole("button", { name: "View from top", exact: true })
    .click();
  await page.screenshot({
    path: info.outputPath("contour-beaded.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
  const download = page.waitForEvent("download");
  await primary(page).click();
  await (await download).saveAs(info.outputPath("contour.3mf"));
  await rebuild(page, () =>
    page
      .getByRole("combobox", { name: "Backing shape", exact: true })
      .selectOption("rectangle"),
  );
  await expect(
    page.getByRole("button", { name: "Tiles", exact: true }),
  ).toBeEnabled();
  await rebuild(page, () =>
    page.getByRole("button", { name: "Tiles", exact: true }).click(),
  );
});

for (const [index, source] of privateSources.entries()) {
  test(`private SVG ${index + 1} makes a contour bezel with optional mounting`, async ({
    page,
  }, info) => {
    await upload(page, source);
    await rebuild(page, () =>
      page
        .getByRole("combobox", { name: "Backing shape", exact: true })
        .selectOption("contour"),
    );
    await number(page, "Border width (mm)", 6);
    await number(page, "Border height (mm)", 3);
    await rebuild(page, () =>
      page
        .getByRole("combobox", { name: "Border", exact: true })
        .selectOption("rounded"),
    );
    await rebuild(page, () =>
      page
        .getByRole("combobox", { name: "Hanging", exact: true })
        .selectOption("keyholes"),
    );
    const loop: Preview = await rebuild(page, () =>
      page
        .getByRole("combobox", { name: "Hanging", exact: true })
        .selectOption("loops"),
    );
    expect(loop.manifest.piece_count).toBe(1);
    expect(loop.manifest.pieces[0].material_parts).toBe(2);
    await page
      .getByRole("button", { name: "View from top", exact: true })
      .click();
    await page.screenshot({
      path: info.outputPath("private-contour-rounded.png"),
      fullPage: true,
    });
    await rebuild(page, () =>
      page
        .getByRole("combobox", { name: "Border", exact: true })
        .selectOption("beaded"),
    );
    await page
      .getByRole("button", { name: "View from top", exact: true })
      .click();
    await page.screenshot({
      path: info.outputPath("private-contour-beaded.png"),
      fullPage: true,
    });
  });
}
