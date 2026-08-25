import {defineConfig, devices} from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 600_000, // 10 min — covers 2x app installs + 3 min wait
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", {outputFolder: "reports/html", open: "never"}]],

  use: {
    baseURL: process.env.ODOO_URL ?? "http://localhost:8069",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    launchOptions: {
      slowMo: process.env.PWDEBUG_SLOWMO ? 500 : 0,
    },
  },

  projects: [
    {
      name: "chromium",
      use: {...devices["Desktop Chrome"]},
    },
  ],
});
