/** Launch a test-owned API and real Chromium; never attach tests to a user's live workbench. */
import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const python = process.env.RELIEF_TEST_PYTHON || join(root, ".venv/bin/python");
const port = Number(process.env.RELIEF_TEST_PORT || 8011);
if (!Number.isInteger(port) || port < 1024 || port > 65535)
  throw Error("Invalid RELIEF_TEST_PORT");
const url = `http://127.0.0.1:${port}`;
const quote = (value: string) => "'" + value.replace(/'/g, "'\\''") + "'";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../output/verification/browser-artifacts",
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [
    ["list"],
    ["json", { outputFile: "../output/verification/browser.json" }],
  ],
  use: {
    baseURL: url,
    browserName: "chromium",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: {
      args: [
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
      ],
    },
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1536, height: 1024 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: `${quote(python)} scripts/browser_test_server.py ${port}`,
    cwd: root,
    url: `${url}/api/health`,
    reuseExistingServer: false,
    timeout: 30_000,
    gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
  },
});
