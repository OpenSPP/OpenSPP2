import {test, expect, Page} from "@playwright/test";
import {resetStack} from "./helpers";

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

  await page.getByRole("button", {name: "Remove"}).click();
  console.log("✅ Clicked Remove button");
  await page.waitForLoadState("domcontentloaded");
  console.log("✅ Filter cleared, page settled");

  console.log("✅ Filling search box");
  await page.getByRole("searchbox", {name: "Search..."}).fill(technicalName);
  await page.getByRole("searchbox", {name: "Search..."}).press("Enter");
  await page.waitForLoadState("domcontentloaded");
  console.log("✅ Search done, looking for Install button");

  const installBtn = page.getByRole("button", {name: "Activate"}).first();
  await expect(installBtn).toBeVisible({timeout: 15_000});
  console.log("✅ Install button found, clicking");
  await installBtn.click();

  console.log("✅ Waiting for installation to complete");
  await page.waitForLoadState("domcontentloaded", {timeout: 180_000});
  await page
    .locator(".o_loading")
    .waitFor({state: "hidden", timeout: 180_000})
    .catch(() => {});
  await expect(
    page.locator(".o_main_navbar .o_menu_sections .o_nav_entry").first()
  ).toBeVisible({timeout: 180_000});
  console.log("✅ Installation complete — nav menus are visible");
}

test.describe("OpenSPP", () => {
  test.beforeAll(async () => {
    await resetStack();
  });

  test("login and install OpenSPP Starter Farmer Registry, then verify nav menus", async ({
    page,
  }) => {
    await login(page);

    await installApp(page, "spp_starter_farmer_registry");

    // Wait 1 minute for menus to fully settle after installation
    await page.waitForTimeout(60_000);

    // Verify navbar and menus are present
    await expect(page.locator(".o_main_navbar")).toBeVisible();
    const menuItems = page.locator(
      ".o_main_navbar .o_nav_entry, .o_main_navbar .o_dropdown"
    );
    await expect(menuItems.first()).toBeVisible({timeout: 10_000});

    await page.screenshot({
      path: "reports/post-install-farmer-registry-navbar.png",
      fullPage: false,
    });
  });
});
