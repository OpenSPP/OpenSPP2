import {defineConfig, devices} from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 600_000, // 10 min — covers 2x app installs + 3 min wait
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", {outputFolder: "reports/html", open: "never"}]],
  // These files are inherently slow (docker rebuild + module installs) and
  // can't be split into parallel workers — they share one serial browser
  // session per file. The "slow test file" hint doesn't apply here.
  reportSlowTests: null,

  use: {
    baseURL: process.env.ODOO_URL ?? "http://localhost:8069",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    launchOptions: {
      // Deliberately always-on, not opt-in. Running this suite without a per-action
      // delay reliably (not rarely) exposes real timing races in Odoo's own OWL
      // frontend — not missing waits in this suite. Confirmed 3 distinct races via
      // 5 clean runs with this delay vs. repeated failures without it:
      //   1. Navbar "Configuration" button ambiguity when switching between apps
      //      that both have a same-named top-level Configuration menu (e.g.
      //      spp_approval's menu_approval_config vs. spp_change_request_v2's
      //      menu_change_request_config) — OWL's keyed diff briefly leaves both
      //      buttons mounted mid-transition.
      //   2. Vocabulary "Add a line" row insertion racing the row-fill, scrambling
      //      which code/display pair lands in which row.
      //   3. Odoo's webclient sometimes restores `current_action`/`menu_id` from
      //      sessionStorage on a fresh login instead of waiting for the server's
      //      real default-action response, landing on a stale page.
      // No human clicks fast enough to hit any of these — see e2e/README.md
      // ("Known frontend timing races") for details. Do not make this opt-in
      // again without addressing all three races directly in the test code.
      slowMo: 500,
    },
  },

  projects: [
    {
      name: "chromium",
      use: {...devices["Desktop Chrome"]},
    },
  ],
});
