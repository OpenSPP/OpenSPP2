// OpenSPP DCI Compliance — end-to-end test suite
//
// What this tests:
//   01 - Logs in as admin and installs the spp_dci_compliance module via the Apps menu
//   02 - Reloads the backend and confirms the webclient renders cleanly (navbar visible,
//        no uncaught page error, no client error dialog) and that the DCI
//        security-warning systray item shows a badge of 3, naming the three insecure
//        dci.* settings the module's post-install hook turns on (unsigned requests,
//        HTTP callbacks, internal callback IPs)
//   03 - Turns dci.allow_unsigned_requests back off in the System Parameters list,
//        reloads, and confirms the badge drops to 2 and that setting is no longer
//        listed in the dropdown
//
// The systray component runs for every backend user on every page load, so it is the
// one place a broken frontend service lookup (useService on a service Odoo 19 removed)
// takes the whole webclient down. Nothing else in CI mounts it — module tests run
// without a browser — which is why this spec exists.
//
// All tests run in order and share a single browser session (test.describe.serial).
// A fresh Docker stack is spun up in beforeAll so every run starts from a clean database.

import {test, expect, Page} from "@playwright/test";
import {resetStack} from "./helpers";

const SYSTRAY_ITEM = ".o_dci_security_warning";
// Odoo's error service renders every uncaught client error into one of these.
const ERROR_DIALOG =
  ".o_error_dialog, .modal:has-text('Odoo Client Error'), .modal:has-text('Odoo Error')";

async function login(page: Page) {
  await page.goto("/web/login");
  await page.getByRole("textbox", {name: "Email"}).fill("admin");
  await page.getByRole("textbox", {name: "Password"}).fill("admin");
  await page.getByRole("button", {name: "Log in"}).click();
  await expect(page.locator(".o_main_navbar")).toBeVisible({timeout: 30_000});
}

async function installApp(page: Page, technicalName: string) {
  console.log("✅ Clicking Apps menuitem");
  await page.getByRole("menuitem", {name: "Apps"}).click();
  await page.waitForLoadState("domcontentloaded");
  console.log("✅ Apps page loaded");

  // Remove all preset filter chips (there are two by default); spp_dci_compliance is
  // not flagged as an application, so the default "Apps" filter would hide it.
  await page.getByRole("button", {name: "Remove"}).click();
  await page.waitForLoadState("domcontentloaded");
  console.log("✅ Filter cleared, page settled");

  // Search by technical module name
  await page.getByRole("searchbox", {name: "Search..."}).fill(technicalName);
  await page.getByRole("searchbox", {name: "Search..."}).press("Enter");
  await page.waitForLoadState("domcontentloaded");
  console.log("✅ Search done, looking for Install button");

  // Click Install on the matching card
  const installBtn = page.getByRole("button", {name: "Activate"}).first();
  await expect(installBtn).toBeVisible({timeout: 15_000});
  await installBtn.click();

  // Wait for installation — Odoo shows a loading spinner then reloads the webclient
  console.log("✅ Waiting for installation to complete");
  await page.waitForLoadState("domcontentloaded", {timeout: 180_000});
  await page
    .locator(".o_loading")
    .waitFor({state: "hidden", timeout: 180_000})
    .catch(() => {});
  await expect(page.locator(".o_main_navbar")).toBeVisible({timeout: 180_000});
  console.log("✅ Installation complete — webclient is back");
}

async function reloadBackend(page: Page) {
  await page.goto("/odoo");
  await page.waitForLoadState("domcontentloaded");
  await expect(page.locator(".o_main_navbar")).toBeVisible({timeout: 60_000});
}

test.describe.serial("OpenSPP DCI Compliance", () => {
  let page: Page;
  // Uncaught errors thrown while the webclient mounts. A component whose setup()
  // throws (#450) never reaches an error dialog: the OWL root dies first and the
  // page stays blank, so this is the assertion that encodes that failure mode.
  const pageErrors: string[] = [];

  test.beforeAll(async ({browser}) => {
    await resetStack();
    page = await browser.newPage();
    page.on("pageerror", (error) => pageErrors.push(error.message));
  });

  test.afterAll(async () => {
    // page is only assigned after resetStack() succeeds — guard so a beforeAll
    // failure/timeout reports its own real error instead of this masking it.
    if (!page) return;
    await page.close();
  });

  test.afterEach(async ({}, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus && !process.env.CI) {
      console.log(
        `❌ "${testInfo.title}" failed — pausing for investigation (set CI=1 to skip)`
      );
      await page.pause();
    }
  });

  test("01 - login and install DCI Compliance", async () => {
    await login(page);
    await installApp(page, "spp_dci_compliance");
    await page.screenshot({path: "reports/dci-post-install.png", fullPage: false});
  });

  test("02 - webclient renders and the systray item lists the enabled settings", async () => {
    await reloadBackend(page);

    // A broken service lookup in the component's setup() would surface here as a
    // client error dialog and a webclient that never mounts.
    await expect(page.locator(ERROR_DIALOG)).toHaveCount(0);
    await expect(page.locator(".o_main_navbar .o_menu_systray")).toBeVisible();

    // The module's post-install hook enables three insecure settings on purpose (it is
    // a compliance test harness), so a fresh install must show all three.
    const systrayItem = page.locator(SYSTRAY_ITEM);
    await expect(systrayItem).toBeVisible({timeout: 30_000});
    await expect(systrayItem.locator(".badge")).toHaveText("3");

    await systrayItem.click();
    await expect(page.getByText("Not safe for production!")).toBeVisible();
    await expect(page.getByText("Allow Unsigned Requests")).toBeVisible();
    await expect(page.getByText("Allow HTTP Callbacks")).toBeVisible();
    await expect(page.getByText("Allow Internal Callback IPs")).toBeVisible();
    await expect(page.getByText("Bypass Bearer Authentication")).toHaveCount(0);
    await expect(page.locator(ERROR_DIALOG)).toHaveCount(0);
    expect(pageErrors).toEqual([]);

    await page.screenshot({
      path: "reports/dci-systray-three-warnings.png",
      fullPage: false,
    });
    await page.keyboard.press("Escape");
  });

  test("03 - turning a setting off removes it from the systray item", async () => {
    // The System Parameters action is opened by its XML id; the Technical menu that
    // normally leads to it needs developer mode, the action itself does not.
    await page.goto("/odoo/action-base.ir_config_list_action");
    await page.waitForLoadState("domcontentloaded");
    const search = page.getByRole("searchbox", {name: "Search..."});
    await expect(search).toBeVisible({timeout: 30_000});
    await search.fill("dci.allow_unsigned_requests");
    await search.press("Enter");
    await page.waitForLoadState("domcontentloaded");

    // The list is editable in place: clicking the Value cell turns it into a text
    // field (a textarea, since ir.config_parameter.value is a Text field). Odoo puts
    // the field name on the cell, which is the stable handle.
    const row = page.getByRole("row", {name: /dci\.allow_unsigned_requests/});
    const valueCell = row.locator("td[name='value']");
    await valueCell.click();
    const valueField = valueCell.getByRole("textbox");
    await expect(valueField).toBeVisible({timeout: 15_000});
    await valueField.fill("false");
    await page.getByRole("button", {name: "Save", exact: true}).click();
    await expect(valueCell).toHaveText("false");
    console.log("✅ dci.allow_unsigned_requests = false saved");

    await reloadBackend(page);

    await expect(page.locator(ERROR_DIALOG)).toHaveCount(0);
    const systrayItem = page.locator(SYSTRAY_ITEM);
    await expect(systrayItem).toBeVisible({timeout: 30_000});
    await expect(systrayItem.locator(".badge")).toHaveText("2");

    await systrayItem.click();
    await expect(page.getByText("Allow HTTP Callbacks")).toBeVisible();
    await expect(page.getByText("Allow Internal Callback IPs")).toBeVisible();
    await expect(page.getByText("Allow Unsigned Requests")).toHaveCount(0);
    expect(pageErrors).toEqual([]);

    await page.screenshot({
      path: "reports/dci-systray-two-warnings.png",
      fullPage: false,
    });
  });
});
