// OpenSPP Starter SP-MIS — end-to-end test suite
//
// What this tests:
//   01 - Logs in as admin and installs the spp_starter_sp_mis module via the Apps menu
//   02 - Creates individual registrant: Doe, John Miller
//   03 - Creates individual registrant: Reyes, Maria Clara
//   04 - Creates individual registrant: Santos, Jose Miguel
//   05 - Creates individual registrant: Garcia, Ana Liza
//   06 - Creates individual registrant: Cruz, Roberto Paolo
//   07 - Creates group registrant: Doe Family
//   08 - Creates group registrant: Santos Family
//   09 - Assigns individuals to groups (Doe Family: 02–04, Santos Family: 05–06)
//   10 - Creates area hierarchy: Philippines > Manila, Cebu > Mandaue City
//   11 - Assigns an area to each individual registrant
//   12 - Assigns an area to each group registrant
//   13 - Creates an Approval Definition (Change request → HQ validator) and assigns it as the Approval Workflow for Edit Individual Information, Edit Group Information, and Update ID Document change request types
//   14 - Manually defines 5 Change Request Document Type vocabulary codes for the Philippines (PSA Birth Certificate, PhilSys National ID, Barangay Certificate of Residency, PSA Marriage Certificate, Proof of Income), matching what spp_mis_demo_v2's demo generator seeds for "phl", by adding rows to the existing vocabulary's Codes tab via Settings > Vocabularies
//   15 - Manually defines 5 more Change Request Document Type vocabulary codes for the Philippines (BIR Form 2316, Academic Calendar, Authorization Letter, Certificate of Enrolment, Valid ID of Parent), matching the e2e fixture PDFs in e2e/fixtures/, by adding rows to the same vocabulary's Codes tab as test 14
//   16 - Creates an "Edit Individual Information" change request for Santos, Jose Miguel (as admin), uploads a supporting document, and submits it for approval
//   17 - Creates an "Edit Group Information" change request for Santos Family (as admin), uploads a supporting document, and submits it for approval
//   18 - Creates an "Update ID Document" change request for Santos, Jose Miguel (as admin), sets a National ID with tomorrow's expiry date, uploads a supporting document, and submits it for approval
//   19 - Creates an HQ validator user (hqval@mail.com) with the "CR HQ Validator" role and sets its password
//   20 - Logs in as the HQ validator and resolves all three pending change requests: approves
//        Edit Individual Information, rejects Edit Group Information (with a reason), and
//        requests revision on Update ID Document (with revision notes)
//   21 - Logs back in as admin and confirms the three resolutions actually took effect: the
//        approved name change is reflected on the registrant, and the Change Requests list
//        shows Rejected / Needs Changes for the other two
//   22 - Imports 200 individual registrants in bulk via the Import records wizard
//        (200_individuals.xlsx) and confirms the pager reflects the new count
//   23 - Imports 200 group registrants in bulk via the Import records wizard
//        (200_groups.xlsx) and confirms the pager reflects the new count
//
// All tests run in order and share a single browser session (test.describe.serial).
// A fresh Docker stack is spun up in beforeAll so every run starts from a clean database.

import {test, expect, Page, Browser} from "@playwright/test";
import {resetStack} from "./helpers";
import * as path from "path";

async function login(page: Page) {
  await page.goto("/web/login");

  // Odoo shows an avatar picker instead of the plain form once 2+ accounts
  // have logged in during this browser session (admin + hqval, from test 20
  // onward) — skip past it to reach the Email/Password fields.
  const useAnotherUser = page.getByRole("button", {name: " Use another user"});
  if (await useAnotherUser.count()) {
    await useAnotherUser.click();
    await expect(page.getByRole("button", {name: "Choose a user"})).toBeVisible();
  }

  const emailField = page
    .getByRole("textbox", {name: "Email Choose a user"})
    .or(page.getByRole("textbox", {name: "Email", exact: true}));
  await emailField.fill("admin");
  await emailField.press("Tab");
  await page.getByRole("textbox", {name: "Password"}).fill("admin");
  await page.getByRole("button", {name: "Log in"}).click();
  await expect(page.locator(".o_main_navbar")).toBeVisible({timeout: 30_000});
}

async function logout(page: Page) {
  await page.getByRole("button", {name: "User User is online"}).click();
  await expect(page.getByRole("link", {name: "User is online Online "})).toBeVisible();
  await page.getByRole("menuitem", {name: "Log out"}).click();
}

function formatDateMDY(date: Date): string {
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  return `${mm}/${dd}/${date.getFullYear()}`;
}

async function installApp(page: Page, technicalName: string) {
  console.log("✅ Clicking Apps menuitem");
  await page.getByRole("menuitem", {name: "Apps"}).click();
  console.log("✅ Clicked Apps, waiting for DOM content loaded");
  await page.waitForLoadState("domcontentloaded");
  console.log("✅ Apps page loaded");

  // Remove all preset filter chips (there are two by default)
  await page.getByRole("button", {name: "Remove"}).click();
  console.log("✅ Clicked Remove button");
  await page.waitForLoadState("domcontentloaded");
  console.log("✅ Filter cleared, page settled");

  // Search by technical module name
  console.log("✅ Filling search box");
  await page.getByRole("searchbox", {name: "Search..."}).fill(technicalName);
  console.log("✅ Pressing Enter to search");
  await page.getByRole("searchbox", {name: "Search..."}).press("Enter");
  await page.waitForLoadState("domcontentloaded");
  console.log("✅ Search done, looking for Install button");

  // Click Install on the matching card
  const installBtn = page.getByRole("button", {name: "Activate"}).first();
  await expect(installBtn).toBeVisible({timeout: 15_000});
  console.log("✅ Install button found, clicking");
  await installBtn.click();

  // Wait for installation — Odoo shows a loading spinner then redirects away from apps
  console.log("✅ Waiting for installation to complete");
  await page.waitForLoadState("domcontentloaded", {timeout: 180_000});

  // Wait for Odoo loading spinner to fully disappear
  await page
    .locator(".o_loading")
    .waitFor({state: "hidden", timeout: 180_000})
    .catch(() => {});

  // Wait for at least one nav menu item to appear
  await expect(
    page.locator(".o_main_navbar .o_menu_sections .o_nav_entry").first()
  ).toBeVisible({timeout: 180_000});
  console.log("✅ Installation complete — nav menus are visible");
}

test.describe.serial("OpenSPP Starter SP-MIS", () => {
  let page: Page;

  test.beforeAll(async ({browser}) => {
    await resetStack();
    page = await browser.newPage();
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

  test("01 - login and install OpenSPP Starter SP-MIS", async () => {
    await login(page);
    await installApp(page, "spp_starter_sp_mis");

    console.log("⏳ Waiting for the Registry menu to be ready before proceeding...");
    // Odoo renders "Registry" as a menuitem in two places (top navbar dropdown and the
    // side nav list) once the app is loaded — .nth(1) picks the side-list one, matching
    // what test 02 later clicks.
    await expect(page.getByRole("menuitem", {name: "Registry"}).nth(1)).toBeVisible({
      timeout: 120_000,
    });

    await expect(page.locator(".o_main_navbar")).toBeVisible();
    const menuItems = page.locator(
      ".o_main_navbar .o_nav_entry, .o_main_navbar .o_dropdown"
    );
    await expect(menuItems.first()).toBeVisible({timeout: 10_000});

    await page.screenshot({path: "reports/post-install-navbar.png", fullPage: false});
  });

  test("02 - create individual registrant", async () => {
    await page.getByRole("menuitem", {name: "Registry"}).nth(1).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "New Individual"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Family Name?"}).fill("Doe");
    await page.getByRole("textbox", {name: "Given Name?"}).fill("John Miller");
    await page.getByRole("textbox", {name: "Date of Birth?"}).fill("01/01/1975");
    await page.getByRole("textbox", {name: "Date of Birth?"}).press("Escape");
    console.log("✅ Basic info filled");

    await page.getByRole("combobox", {name: "Gender"}).click();
    await page.getByRole("option", {name: "Male", exact: true}).click();
    await page.getByRole("combobox", {name: "Civil Status?"}).click();
    await page.getByRole("option", {name: "Married", exact: true}).click();
    await page.getByRole("textbox", {name: "Income"}).fill("10000");
    await page.getByRole("combobox", {name: "Occupation?"}).click();
    await page
      .getByRole("option", {name: "Armed Forces Occupations", exact: true})
      .click();
    console.log("✅ Demographics filled");

    await page.getByRole("textbox", {name: "Email?"}).fill("johnmiller@mail.com");
    await page.getByRole("button", {name: "Add a line"}).first().click();
    await page.locator('input[type="tel"]').fill("09772603521");
    await page.getByRole("row", {name: "Delete row"}).getByRole("combobox").fill("ph");
    await page.getByRole("option", {name: "Philippines"}).click();
    console.log("✅ Contact info filled");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.locator(".o_form_view")).toBeVisible();
    console.log("✅ Individual registrant saved — verifying all fields...");

    await expect(page.getByRole("textbox", {name: "Family Name?"})).toHaveValue("Doe");
    console.log("✅ Family Name: Doe");

    await expect(page.getByRole("textbox", {name: "Given Name?"})).toHaveValue(
      "John Miller"
    );
    console.log("✅ Given Name: John Miller");

    await expect(page.getByRole("button", {name: "Date of Birth?"})).toContainText(
      "Jan 1, 1975"
    );
    console.log("✅ Date of Birth: Jan 1, 1975");

    await expect(page.getByRole("combobox", {name: "Gender"})).toHaveValue("Male");
    console.log("✅ Gender: Male");

    await expect(page.getByRole("combobox", {name: "Civil Status?"})).toHaveValue(
      "Married"
    );
    console.log("✅ Civil Status: Married");

    await expect(page.getByRole("textbox", {name: "Income"})).toHaveValue("10,000.00");
    console.log("✅ Income: 10,000.00");

    await expect(page.getByRole("textbox", {name: "Email?"})).toHaveValue(
      "johnmiller@mail.com"
    );
    console.log("✅ Email: johnmiller@mail.com");

    await expect(page.getByRole("link", {name: "09772603521"})).toBeVisible();
    console.log("✅ Phone: 09772603521");

    console.log("✅ All fields verified — individual registrant saved successfully");

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Individuals"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("cell", {name: "DOE, JOHN MILLER"})).toBeVisible({
      timeout: 10_000,
    });
    console.log(
      '✅ Registrant "DOE, JOHN MILLER" verified in Browse All Individuals list'
    );

    await page.getByRole("cell", {name: "DOE, JOHN MILLER"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator(".o_form_view")).toBeVisible({timeout: 10_000});
    await expect(page.getByRole("textbox", {name: "Family Name?"})).toHaveValue("Doe");
    console.log(
      '✅ Individual registrant "DOE, JOHN MILLER" created via GUI successfully'
    );
  });

  test("03 - create individual registrant: Reyes, Maria Clara", async () => {
    await page.getByRole("menuitem", {name: "Registry"}).nth(1).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "New Individual"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Family Name?"}).fill("Reyes");
    await page.getByRole("textbox", {name: "Given Name?"}).fill("Maria Clara");
    await page.getByRole("textbox", {name: "Date of Birth?"}).fill("03/15/1985");
    await page.getByRole("textbox", {name: "Date of Birth?"}).press("Escape");
    console.log("✅ Basic info filled");

    await page.getByRole("combobox", {name: "Gender"}).click();
    await page.getByRole("option", {name: "Female", exact: true}).click();
    await page.getByRole("combobox", {name: "Civil Status?"}).click();
    await page.getByRole("option", {name: "Married", exact: true}).click();
    await page.getByRole("textbox", {name: "Income"}).fill("15000");
    await page.getByRole("combobox", {name: "Occupation?"}).click();
    await page
      .getByRole("option", {name: "Armed Forces Occupations", exact: true})
      .click();
    console.log("✅ Demographics filled");

    await page.getByRole("textbox", {name: "Email?"}).fill("mariaclara@mail.com");
    await page.getByRole("button", {name: "Add a line"}).first().click();
    await page.locator('input[type="tel"]').fill("09123456789");
    await page.getByRole("row", {name: "Delete row"}).getByRole("combobox").fill("ph");
    await page.getByRole("option", {name: "Philippines"}).click();
    console.log("✅ Contact info filled");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.locator(".o_form_view")).toBeVisible();
    console.log("✅ Individual registrant saved — verifying all fields...");

    await expect(page.getByRole("textbox", {name: "Family Name?"})).toHaveValue(
      "Reyes"
    );
    await expect(page.getByRole("textbox", {name: "Given Name?"})).toHaveValue(
      "Maria Clara"
    );
    await expect(page.getByRole("button", {name: "Date of Birth?"})).toContainText(
      "Mar 15, 1985"
    );
    await expect(page.getByRole("combobox", {name: "Gender"})).toHaveValue("Female");
    await expect(page.getByRole("combobox", {name: "Civil Status?"})).toHaveValue(
      "Married"
    );
    await expect(page.getByRole("textbox", {name: "Income"})).toHaveValue("15,000.00");
    await expect(page.getByRole("textbox", {name: "Email?"})).toHaveValue(
      "mariaclara@mail.com"
    );
    await expect(page.getByRole("link", {name: "09123456789"})).toBeVisible();
    console.log("✅ All fields verified — REYES, MARIA CLARA saved successfully");

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Individuals"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("cell", {name: "REYES, MARIA CLARA"})).toBeVisible({
      timeout: 10_000,
    });
    console.log(
      '✅ Individual registrant "REYES, MARIA CLARA" created via GUI successfully'
    );
  });

  test("04 - create individual registrant: Santos, Jose Miguel", async () => {
    await page.getByRole("menuitem", {name: "Registry"}).nth(1).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "New Individual"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Family Name?"}).fill("Santos");
    await page.getByRole("textbox", {name: "Given Name?"}).fill("Jose Miguel");
    await page.getByRole("textbox", {name: "Date of Birth?"}).fill("07/22/1990");
    await page.getByRole("textbox", {name: "Date of Birth?"}).press("Escape");
    console.log("✅ Basic info filled");

    await page.getByRole("combobox", {name: "Gender"}).click();
    await page.getByRole("option", {name: "Male", exact: true}).click();
    await page.getByRole("combobox", {name: "Civil Status?"}).click();
    await page.getByRole("option", {name: "Married", exact: true}).click();
    await page.getByRole("textbox", {name: "Income"}).fill("20000");
    await page.getByRole("combobox", {name: "Occupation?"}).click();
    await page
      .getByRole("option", {name: "Armed Forces Occupations", exact: true})
      .click();
    console.log("✅ Demographics filled");

    await page.getByRole("textbox", {name: "Email?"}).fill("josemiguel@mail.com");
    await page.getByRole("button", {name: "Add a line"}).first().click();
    await page.locator('input[type="tel"]').fill("09234567890");
    await page.getByRole("row", {name: "Delete row"}).getByRole("combobox").fill("ph");
    await page.getByRole("option", {name: "Philippines"}).click();
    console.log("✅ Contact info filled");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.locator(".o_form_view")).toBeVisible();
    console.log("✅ Individual registrant saved — verifying all fields...");

    await expect(page.getByRole("textbox", {name: "Family Name?"})).toHaveValue(
      "Santos"
    );
    await expect(page.getByRole("textbox", {name: "Given Name?"})).toHaveValue(
      "Jose Miguel"
    );
    await expect(page.getByRole("button", {name: "Date of Birth?"})).toContainText(
      "Jul 22, 1990"
    );
    await expect(page.getByRole("combobox", {name: "Gender"})).toHaveValue("Male");
    await expect(page.getByRole("combobox", {name: "Civil Status?"})).toHaveValue(
      "Married"
    );
    await expect(page.getByRole("textbox", {name: "Income"})).toHaveValue("20,000.00");
    await expect(page.getByRole("textbox", {name: "Email?"})).toHaveValue(
      "josemiguel@mail.com"
    );
    await expect(page.getByRole("link", {name: "09234567890"})).toBeVisible();
    console.log("✅ All fields verified — SANTOS, JOSE MIGUEL saved successfully");

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Individuals"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("cell", {name: "SANTOS, JOSE MIGUEL"})).toBeVisible({
      timeout: 10_000,
    });
    console.log(
      '✅ Individual registrant "SANTOS, JOSE MIGUEL" created via GUI successfully'
    );
  });

  test("05 - create individual registrant: Garcia, Ana Liza", async () => {
    await page.getByRole("menuitem", {name: "Registry"}).nth(1).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "New Individual"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Family Name?"}).fill("Garcia");
    await page.getByRole("textbox", {name: "Given Name?"}).fill("Ana Liza");
    await page.getByRole("textbox", {name: "Date of Birth?"}).fill("11/08/1968");
    await page.getByRole("textbox", {name: "Date of Birth?"}).press("Escape");
    console.log("✅ Basic info filled");

    await page.getByRole("combobox", {name: "Gender"}).click();
    await page.getByRole("option", {name: "Female", exact: true}).click();
    await page.getByRole("combobox", {name: "Civil Status?"}).click();
    await page.getByRole("option", {name: "Married", exact: true}).click();
    await page.getByRole("textbox", {name: "Income"}).fill("8000");
    await page.getByRole("combobox", {name: "Occupation?"}).click();
    await page
      .getByRole("option", {name: "Armed Forces Occupations", exact: true})
      .click();
    console.log("✅ Demographics filled");

    await page.getByRole("textbox", {name: "Email?"}).fill("analiza@mail.com");
    await page.getByRole("button", {name: "Add a line"}).first().click();
    await page.locator('input[type="tel"]').fill("09345678901");
    await page.getByRole("row", {name: "Delete row"}).getByRole("combobox").fill("ph");
    await page.getByRole("option", {name: "Philippines"}).click();
    console.log("✅ Contact info filled");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.locator(".o_form_view")).toBeVisible();
    console.log("✅ Individual registrant saved — verifying all fields...");

    await expect(page.getByRole("textbox", {name: "Family Name?"})).toHaveValue(
      "Garcia"
    );
    await expect(page.getByRole("textbox", {name: "Given Name?"})).toHaveValue(
      "Ana Liza"
    );
    await expect(page.getByRole("button", {name: "Date of Birth?"})).toContainText(
      "Nov 8, 1968"
    );
    await expect(page.getByRole("combobox", {name: "Gender"})).toHaveValue("Female");
    await expect(page.getByRole("combobox", {name: "Civil Status?"})).toHaveValue(
      "Married"
    );
    await expect(page.getByRole("textbox", {name: "Income"})).toHaveValue("8,000.00");
    await expect(page.getByRole("textbox", {name: "Email?"})).toHaveValue(
      "analiza@mail.com"
    );
    await expect(page.getByRole("link", {name: "09345678901"})).toBeVisible();
    console.log("✅ All fields verified — GARCIA, ANA LIZA saved successfully");

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Individuals"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("cell", {name: "GARCIA, ANA LIZA"})).toBeVisible({
      timeout: 10_000,
    });
    console.log(
      '✅ Individual registrant "GARCIA, ANA LIZA" created via GUI successfully'
    );
  });

  test("06 - create individual registrant: Cruz, Roberto Paolo", async () => {
    await page.getByRole("menuitem", {name: "Registry"}).nth(1).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "New Individual"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Family Name?"}).fill("Cruz");
    await page.getByRole("textbox", {name: "Given Name?"}).fill("Roberto Paolo");
    await page.getByRole("textbox", {name: "Date of Birth?"}).fill("04/30/1978");
    await page.getByRole("textbox", {name: "Date of Birth?"}).press("Escape");
    console.log("✅ Basic info filled");

    await page.getByRole("combobox", {name: "Gender"}).click();
    await page.getByRole("option", {name: "Male", exact: true}).click();
    await page.getByRole("combobox", {name: "Civil Status?"}).click();
    await page.getByRole("option", {name: "Married", exact: true}).click();
    await page.getByRole("textbox", {name: "Income"}).fill("12000");
    await page.getByRole("combobox", {name: "Occupation?"}).click();
    await page
      .getByRole("option", {name: "Armed Forces Occupations", exact: true})
      .click();
    console.log("✅ Demographics filled");

    await page.getByRole("textbox", {name: "Email?"}).fill("robertopaolo@mail.com");
    await page.getByRole("button", {name: "Add a line"}).first().click();
    await page.locator('input[type="tel"]').fill("09456789012");
    await page.getByRole("row", {name: "Delete row"}).getByRole("combobox").fill("ph");
    await page.getByRole("option", {name: "Philippines"}).click();
    console.log("✅ Contact info filled");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.locator(".o_form_view")).toBeVisible();
    console.log("✅ Individual registrant saved — verifying all fields...");

    await expect(page.getByRole("textbox", {name: "Family Name?"})).toHaveValue("Cruz");
    await expect(page.getByRole("textbox", {name: "Given Name?"})).toHaveValue(
      "Roberto Paolo"
    );
    await expect(page.getByRole("button", {name: "Date of Birth?"})).toContainText(
      "Apr 30, 1978"
    );
    await expect(page.getByRole("combobox", {name: "Gender"})).toHaveValue("Male");
    await expect(page.getByRole("combobox", {name: "Civil Status?"})).toHaveValue(
      "Married"
    );
    await expect(page.getByRole("textbox", {name: "Income"})).toHaveValue("12,000.00");
    await expect(page.getByRole("textbox", {name: "Email?"})).toHaveValue(
      "robertopaolo@mail.com"
    );
    await expect(page.getByRole("link", {name: "09456789012"})).toBeVisible();
    console.log("✅ All fields verified — CRUZ, ROBERTO PAOLO saved successfully");

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Individuals"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("cell", {name: "CRUZ, ROBERTO PAOLO"})).toBeVisible({
      timeout: 10_000,
    });
    console.log(
      '✅ Individual registrant "CRUZ, ROBERTO PAOLO" created via GUI successfully'
    );
  });

  test("07 - create group registrant", async () => {
    await page.getByRole("menuitem", {name: "Registry"}).nth(1).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "New Group"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Group Name?"}).fill("Doe Family");
    await page.getByRole("combobox", {name: "Group Type?"}).click();
    await page.getByRole("option", {name: "Family"}).click();
    console.log("✅ Group name and type filled");

    await page.getByRole("textbox", {name: "Address"}).fill("Sample Address");
    console.log("✅ Address filled");

    await page.getByRole("textbox", {name: "Email?"}).fill("Doefamiliy@mail.com");
    await page.getByRole("button", {name: "Add a line"}).first().click();
    await page.locator('input[type="tel"]').fill("09987654321");
    await page.getByRole("row", {name: "Delete row"}).getByRole("combobox").fill("ph");
    await page.getByRole("option", {name: "Philippines"}).click();
    console.log("✅ Contact info filled");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.locator(".o_form_view")).toBeVisible();
    console.log("✅ Group registrant saved — verifying all fields...");

    await expect(page.getByRole("textbox", {name: "Group Name?"})).toHaveValue(
      "Doe Family"
    );
    console.log("✅ Group Name: Doe Family");

    await expect(page.getByRole("combobox", {name: "Group Type?"})).toHaveValue(
      "Family"
    );
    console.log("✅ Group Type: Family");

    await expect(page.getByRole("textbox", {name: "Address"})).toHaveValue(
      "Sample Address"
    );
    console.log("✅ Address: Sample Address");

    await expect(page.getByRole("textbox", {name: "Email?"})).toHaveValue(
      "Doefamiliy@mail.com"
    );
    console.log("✅ Email: Doefamiliy@mail.com");

    await expect(page.getByRole("link", {name: "09987654321"})).toBeVisible();
    console.log("✅ Phone: 09987654321");

    console.log("✅ All fields verified — group registrant saved successfully");

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Groups"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("cell", {name: "Doe Family"})).toBeVisible({
      timeout: 10_000,
    });
    console.log('✅ Group "Doe Family" verified in Browse All Groups list');

    await page.getByRole("cell", {name: "Doe Family"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator(".o_form_view")).toBeVisible({timeout: 10_000});
    await expect(page.getByRole("textbox", {name: "Group Name?"})).toHaveValue(
      "Doe Family"
    );
    console.log('✅ Group registrant "Doe Family" created via GUI successfully');
  });

  test("08 - create group registrant: Santos Family", async () => {
    await page.getByRole("menuitem", {name: "Registry"}).nth(1).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "New Group"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Group Name?"}).fill("Santos Family");
    await page.getByRole("combobox", {name: "Group Type?"}).click();
    await page.getByRole("option", {name: "Family"}).click();
    console.log("✅ Group name and type filled");

    await page.getByRole("textbox", {name: "Address"}).fill("456 Rizal Street");
    console.log("✅ Address filled");

    await page.getByRole("textbox", {name: "Email?"}).fill("santosfamily@mail.com");
    await page.getByRole("button", {name: "Add a line"}).first().click();
    await page.locator('input[type="tel"]').fill("09112233445");
    await page.getByRole("row", {name: "Delete row"}).getByRole("combobox").fill("ph");
    await page.getByRole("option", {name: "Philippines"}).click();
    console.log("✅ Contact info filled");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.locator(".o_form_view")).toBeVisible();
    console.log("✅ Group registrant saved — verifying all fields...");

    await expect(page.getByRole("textbox", {name: "Group Name?"})).toHaveValue(
      "Santos Family"
    );
    console.log("✅ Group Name: Santos Family");

    await expect(page.getByRole("combobox", {name: "Group Type?"})).toHaveValue(
      "Family"
    );
    console.log("✅ Group Type: Family");

    await expect(page.getByRole("textbox", {name: "Address"})).toHaveValue(
      "456 Rizal Street"
    );
    console.log("✅ Address: 456 Rizal Street");

    await expect(page.getByRole("textbox", {name: "Email?"})).toHaveValue(
      "santosfamily@mail.com"
    );
    console.log("✅ Email: santosfamily@mail.com");

    await expect(page.getByRole("link", {name: "09112233445"})).toBeVisible();
    console.log("✅ Phone: 09112233445");

    console.log("✅ All fields verified — group registrant saved successfully");

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Groups"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("cell", {name: "Santos Family"})).toBeVisible({
      timeout: 10_000,
    });
    console.log('✅ Group "Santos Family" verified in Browse All Groups list');

    await page.getByRole("cell", {name: "Santos Family"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator(".o_form_view")).toBeVisible({timeout: 10_000});
    await expect(page.getByRole("textbox", {name: "Group Name?"})).toHaveValue(
      "Santos Family"
    );
    console.log('✅ Group registrant "Santos Family" created via GUI successfully');
  });

  test("09 - assign individuals to groups", async () => {
    // --- Doe Family: assign first 3 individuals ---
    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Groups"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("cell", {name: "Doe Family"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("tab", {name: "Participation"}).click();

    await page.getByRole("button", {name: "Add a line"}).click();
    await page.getByRole("combobox").first().click();
    await page.getByRole("option", {name: "DOE, JOHN MILLER"}).click();
    console.log("✅ Added DOE, JOHN MILLER to Doe Family");

    await page.getByRole("button", {name: "Add a line"}).click();
    await page.getByRole("combobox").first().click();
    await page.getByRole("option", {name: "REYES, MARIA CLARA"}).click();
    console.log("✅ Added REYES, MARIA CLARA to Doe Family");

    await page.getByRole("button", {name: "Add a line"}).click();
    await page.getByRole("combobox").first().click();
    await page.getByRole("option", {name: "SANTOS, JOSE MIGUEL"}).click();
    console.log("✅ Added SANTOS, JOSE MIGUEL to Doe Family");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.locator(".o_form_view")).toBeVisible();
    console.log("✅ Doe Family members saved — verifying...");

    await page.getByRole("tab", {name: "Participation"}).click();
    await expect(page.getByRole("cell", {name: "DOE, JOHN MILLER"})).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByRole("cell", {name: "REYES, MARIA CLARA"})).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByRole("cell", {name: "SANTOS, JOSE MIGUEL"})).toBeVisible({
      timeout: 10_000,
    });
    console.log("✅ All 3 members verified in Doe Family participation tab");

    // --- Santos Family: assign last 2 individuals ---
    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Groups"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("cell", {name: "Santos Family"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("tab", {name: "Participation"}).click();

    await page.getByRole("button", {name: "Add a line"}).click();
    await page.getByRole("combobox").first().click();
    await page.getByRole("option", {name: "GARCIA, ANA LIZA"}).click();
    console.log("✅ Added GARCIA, ANA LIZA to Santos Family");

    await page.getByRole("button", {name: "Add a line"}).click();
    await page.getByRole("combobox").first().click();
    await page.getByRole("option", {name: "CRUZ, ROBERTO PAOLO"}).click();
    console.log("✅ Added CRUZ, ROBERTO PAOLO to Santos Family");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.locator(".o_form_view")).toBeVisible();
    console.log("✅ Santos Family members saved — verifying...");

    await page.getByRole("tab", {name: "Participation"}).click();
    await expect(page.getByRole("cell", {name: "GARCIA, ANA LIZA"})).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByRole("cell", {name: "CRUZ, ROBERTO PAOLO"})).toBeVisible({
      timeout: 10_000,
    });
    console.log("✅ All 2 members verified in Santos Family participation tab");
  });

  test("10 - create areas", async () => {
    await page.getByRole("menuitem", {name: "Area"}).click();
    await page.waitForLoadState("domcontentloaded");

    // --- Philippines (top-level) ---
    await page.getByRole("button", {name: "New"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("textbox", {name: "Enter Area Name..."}).fill("Philippines");
    await page.getByRole("textbox", {name: "Code"}).fill("PH01");
    await page.getByRole("textbox", {name: "Alternate Names"}).fill("ph");
    await page.getByRole("combobox", {name: "Area Type?"}).click();
    await page.getByRole("option", {name: "Admin Area"}).click();
    await page.getByRole("textbox", {name: "Area (km²)?"}).fill("100000");
    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.getByRole("textbox", {name: "Enter Area Name..."})).toHaveValue(
      "Philippines"
    );
    console.log("✅ Area created: Philippines (PH01)");

    // --- Manila (under Philippines) ---
    await page.getByRole("button", {name: "New"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("combobox", {name: "Parent"}).click();
    await page.getByRole("option", {name: "Philippines (PH01)"}).click();
    await page.getByRole("textbox", {name: "Enter Area Name..."}).fill("Manila");
    await page.getByRole("textbox", {name: "Code"}).fill("MNL001");
    await page.getByRole("textbox", {name: "Alternate Names"}).fill("MNL");
    await page.getByRole("combobox", {name: "Area Type?"}).click();
    await page.getByRole("option", {name: "Admin Area"}).click();
    await page.getByRole("textbox", {name: "Area (km²)?"}).fill("5000");
    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.getByRole("textbox", {name: "Enter Area Name..."})).toHaveValue(
      "Manila"
    );
    console.log("✅ Area created: Manila (MNL001) under Philippines");

    // --- Cebu (under Philippines) ---
    await page.getByRole("button", {name: "New"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("combobox", {name: "Parent"}).click();
    await page.getByRole("option", {name: "Philippines (PH01)"}).click();
    await page.getByRole("textbox", {name: "Enter Area Name..."}).fill("Cebu");
    await page.getByRole("textbox", {name: "Code"}).fill("CEB007");
    await page.getByRole("textbox", {name: "Alternate Names"}).fill("CEB");
    await page.getByRole("combobox", {name: "Area Type?"}).click();
    await page.getByRole("option", {name: "Admin Area"}).click();
    await page.getByRole("textbox", {name: "Area (km²)?"}).fill("5000");
    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.getByRole("textbox", {name: "Enter Area Name..."})).toHaveValue(
      "Cebu"
    );
    console.log("✅ Area created: Cebu (CEB007) under Philippines");

    // --- Mandaue City (under Cebu) ---
    await page.getByRole("button", {name: "New"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("combobox", {name: "Parent"}).click();
    await page.getByRole("option", {name: "Cebu (CEB007)"}).click();
    await page.getByRole("textbox", {name: "Enter Area Name..."}).fill("Mandaue City");
    await page.getByRole("textbox", {name: "Code"}).fill("MC004");
    await page.getByRole("textbox", {name: "Alternate Names"}).fill("MC");
    await page.getByRole("combobox", {name: "Area Type?"}).click();
    await page.getByRole("option", {name: "Admin Area"}).click();
    await page.getByRole("textbox", {name: "Area (km²)?"}).fill("500");
    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.getByRole("textbox", {name: "Enter Area Name..."})).toHaveValue(
      "Mandaue City"
    );
    console.log("✅ Area created: Mandaue City (MC004) under Cebu");
  });

  test("11 - assign areas to individuals", async () => {
    const assignments: Array<{name: string; area: string}> = [
      {name: "CRUZ, ROBERTO PAOLO", area: "Philippines (PH01)"},
      {name: "GARCIA, ANA LIZA", area: "Manila (MNL001)"},
      {name: "SANTOS, JOSE MIGUEL", area: "Cebu (CEB007)"},
      {name: "REYES, MARIA CLARA", area: "Mandaue City (MC004)"},
      {name: "DOE, JOHN MILLER", area: "Cebu (CEB007)"},
    ];

    await page.getByRole("list").getByRole("menuitem", {name: "Registry"}).click();
    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Individuals"}).click();
    await page.waitForLoadState("domcontentloaded");

    for (const {name, area} of assignments) {
      await page.getByRole("cell", {name}).click();
      await page.waitForLoadState("domcontentloaded");
      await page.getByPlaceholder("Area").click();
      await page.getByPlaceholder("Area").press("ArrowDown");
      await page.getByRole("option", {name: area}).click();
      await page.getByRole("button", {name: "Save manually"}).click();
      await expect(page.getByPlaceholder("Area")).toHaveValue(area, {timeout: 10_000});
      console.log(`✅ Area assigned and verified: ${name} → ${area}`);
      await page.getByRole("link", {name: "Browse All Individuals"}).click();
      await page.waitForLoadState("domcontentloaded");
    }

    console.log("✅ All individuals assigned to areas successfully");
  });

  test("12 - assign areas to groups", async () => {
    const assignments: Array<{name: string; area: string}> = [
      {name: "Doe Family", area: "Philippines (PH01)"},
      {name: "Santos Family", area: "Cebu (CEB007)"},
    ];

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Groups"}).click();
    await page.waitForLoadState("domcontentloaded");

    for (const {name, area} of assignments) {
      await page.getByRole("cell", {name}).click();
      await page.waitForLoadState("domcontentloaded");
      await page.getByPlaceholder("Area").click();
      await page.getByPlaceholder("Area").press("ArrowDown");
      await page.getByRole("option", {name: area}).click();
      await page.getByRole("button", {name: "Save manually"}).click();
      await expect(page.getByPlaceholder("Area")).toHaveValue(area, {timeout: 10_000});
      console.log(`✅ Area assigned and verified: ${name} → ${area}`);
      await page.getByRole("link", {name: "Browse All Groups"}).click();
      await page.waitForLoadState("domcontentloaded");
    }

    console.log("✅ All groups assigned to areas successfully");
  });

  test("13 - configure approval definition for change requests", async () => {
    // --- Create Approval Definition: "Change request" (Model: Change Request, Group: Change Requests / Validator HQ) ---
    await page.getByRole("list").getByRole("menuitem", {name: "Approvals"}).click();
    await page.getByRole("button", {name: "Configuration"}).click();
    await page.getByRole("menuitem", {name: "Approval Definitions"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "New"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Name"}).fill("Change request");
    await page.getByRole("combobox", {name: "Model"}).click();
    await page.getByRole("combobox", {name: "Model"}).fill("change");
    await page.getByRole("option", {name: "Change Request", exact: true}).click();
    await page.getByRole("combobox", {name: "Approval Group"}).click();
    await page.getByRole("option", {name: "Change Requests / Validator HQ"}).click();
    console.log("✅ Approval Definition filled: Change request");

    await page.getByRole("button", {name: "Save manually"}).click();
    await expect(page.getByRole("textbox", {name: "Name"})).toHaveValue(
      "Change request"
    );
    console.log(
      "✅ Approval Definition saved: Change request (Model: Change Request, Group: Change Requests / Validator HQ)"
    );

    // --- Assign the Approval Definition as the Approval Workflow for the basic change request types ---
    await page.getByRole("list").getByRole("menuitem", {name: "Approvals"}).click();
    await page.getByRole("menuitem", {name: "Change Requests"}).click();
    await page.getByRole("button", {name: "Configuration"}).click();
    await page.getByRole("menuitem", {name: "Change Request Types"}).click();
    await page.waitForLoadState("domcontentloaded");

    const changeRequestTypes = [
      "Edit Individual Information",
      "Edit Group Information",
      "Update ID Document",
    ];

    for (const typeName of changeRequestTypes) {
      await page.getByRole("cell", {name: typeName}).click();
      await page.waitForLoadState("domcontentloaded");
      await page.getByRole("tab", {name: "Approval"}).click();
      await page.getByRole("combobox", {name: "Approval Workflow"}).click();
      await page.getByRole("combobox", {name: "Approval Workflow"}).press("ArrowDown");
      await page.getByRole("option", {name: "Change request"}).click();

      await page.getByRole("button", {name: "Save manually"}).click();
      await expect(page.getByRole("combobox", {name: "Approval Workflow"})).toHaveValue(
        "Change request"
      );
      console.log(
        `✅ Approval Workflow "Change request" (HQ validator) assigned to ${typeName}`
      );

      await page.getByRole("link", {name: "Change Request Types"}).click();
      await page.waitForLoadState("domcontentloaded");
    }

    console.log("✅ Approval Workflow assigned to all basic change request types");
  });

  test("14 - define CR document types for the Philippines (manual vocabulary codes)", async () => {
    // Mirrors spp_mis_demo_v2's MisDemoGenerator.CR_DOCUMENT_TYPES["phl"] list, added by hand
    // to the existing "Change Request Document Types" vocabulary (shipped by spp_vocabulary,
    // is_system=False) to prove the manual GUI flow works without the demo data generator.
    const documentTypes = [
      {code: "psa_birth_certificate", display: "PSA Birth Certificate"},
      {code: "philsys_id", display: "PhilSys National ID"},
      {
        code: "barangay_residency_certificate",
        display: "Barangay Certificate of Residency",
      },
      {code: "psa_marriage_certificate", display: "PSA Marriage Certificate"},
      {code: "proof_of_income", display: "Proof of Income"},
    ];

    await page.getByRole("menuitem", {name: "Settings"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "Vocabularies"}).click();
    await page.getByRole("menuitem", {name: "Manage Vocabularies"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "Remove"}).click();
    await page.getByRole("searchbox", {name: "Search..."}).fill("change");
    await page.getByRole("searchbox", {name: "Search..."}).press("Enter");
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("cell", {name: "Change Request Document Types"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("tab", {name: "Codes"}).click();

    for (const {code, display} of documentTypes) {
      await page.getByRole("button", {name: "Add a line"}).click();
      const row = page.locator(".o_data_row").last();
      await row.getByRole("textbox").first().fill(code);
      await row.getByRole("textbox").nth(1).fill(display);
      console.log(`✅ Vocabulary code row filled: ${display} (${code})`);
    }

    await page.getByRole("button", {name: "Save manually"}).click();
    for (const {display} of documentTypes) {
      await expect(page.getByRole("cell", {name: display})).toBeVisible({
        timeout: 10_000,
      });
    }
    console.log(
      "✅ All 5 CR document types saved under the Change Request Document Types vocabulary"
    );
  });

  test("15 - define additional CR document types for the Philippines (BIR 2316, Academic Calendar, Authorization Letter, Certificate of Enrolment, Valid ID of Parent)", async () => {
    // Matches the e2e fixture PDFs in e2e/fixtures/, added to the same "Change Request Document Types"
    // vocabulary as test 14, ahead of a later test that uploads these files via the Update ID Document
    // change request flow. Test 14 leaves the page sitting on this same record's Codes tab after saving,
    // so no re-navigation is needed here (and re-clicking "Settings" from inside Settings is ambiguous).
    const documentTypes = [
      {code: "bir_2316", display: "BIR Form 2316"},
      {code: "academic_calendar", display: "Academic Calendar"},
      {code: "authorization_letter", display: "Authorization Letter"},
      {code: "certificate_of_enrolment", display: "Certificate of Enrolment"},
      {code: "valid_id_parent", display: "Valid ID of Parent"},
    ];

    for (const {code, display} of documentTypes) {
      await page.getByRole("button", {name: "Add a line"}).click();
      const row = page.locator(".o_data_row").last();
      await row.getByRole("textbox").first().fill(code);
      await row.getByRole("textbox").nth(1).fill(display);
      console.log(`✅ Vocabulary code row filled: ${display} (${code})`);
    }

    await page.getByRole("button", {name: "Save manually"}).click();
    for (const {display} of documentTypes) {
      await expect(page.getByRole("cell", {name: display})).toBeVisible({
        timeout: 10_000,
      });
    }
    console.log(
      "✅ All 5 additional CR document types saved under the Change Request Document Types vocabulary"
    );
  });

  test("16 - create Edit Individual Information change request for Santos, Jose Miguel", async () => {
    // Test 15 leaves the session inside Settings > Vocabularies, which replaces the OpenSPP
    // navbar with the Settings app's own navbar. Go back to the OpenSPP home to get the
    // "Change Requests" top-level menu back.
    await page.goto("/odoo");
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("menuitem", {name: "Change Requests"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "New Request"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Request Type"}).click();
    await page.getByText("Edit Individual Information").click();
    console.log("✅ Request Type: Edit Individual Information");

    await page.getByRole("textbox", {name: "Enter name or ID number..."}).fill("san");
    await page.getByRole("cell", {name: "SANTOS, JOSE MIGUEL"}).click();
    console.log("✅ Registrant selected: SANTOS, JOSE MIGUEL");

    await page.getByRole("button", {name: "Create"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("textbox", {name: "Given Name"})).toBeVisible({
      timeout: 10_000,
    });
    console.log("✅ Change request draft opened for editing");

    await page.getByRole("textbox", {name: "Given Name"}).fill("Jose Miguel Updated");
    await page.getByRole("textbox", {name: "Address Line 1"}).fill("updated");
    await page.getByRole("textbox", {name: "Address Line 2"}).fill("updated");
    await page.getByRole("textbox", {name: "City"}).fill("updated");
    await page.getByRole("textbox", {name: "Postal Code"}).fill("6000");
    await expect(page.getByRole("textbox", {name: "Given Name"})).toHaveValue(
      "Jose Miguel Updated"
    );
    console.log("✅ Updated fields filled: Given Name, Address, City, Postal Code");

    await page.getByRole("button", {name: "Next: Upload Documents"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("button", {name: "Upload Document"}).click();
    await page.getByRole("combobox", {name: "Document Type?"}).click();
    await page.getByRole("option", {name: "PSA Birth Certificate"}).click();
    await page
      .getByRole("dialog")
      .locator('input[type="file"]')
      .setInputFiles(
        path.resolve(__dirname, "..", "fixtures", "sample_valid_ID_parent.pdf")
      );
    await expect(
      page.getByRole("textbox", {name: "sample_valid_ID_parent.pdf"})
    ).toBeVisible({timeout: 10_000});
    await page.getByRole("button", {name: "Upload", exact: true}).click();
    console.log(
      "✅ Document uploaded: sample_valid_ID_parent.pdf (PSA Birth Certificate)"
    );

    await page.getByRole("button", {name: "Next: Review & Submit"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("tab", {name: "Attached Documents"}).click();
    await expect(
      page.getByRole("cell", {name: "sample_valid_ID_parent.pdf"})
    ).toBeVisible();
    console.log("✅ Review page shows attached document");

    await page.getByRole("button", {name: "Submit for Approval"}).click();
    await page
      .getByRole("alert")
      .filter({hasText: "Edit Individual"})
      .getByRole("button", {name: "Close"})
      .click();
    console.log("✅ Edit Individual Information change request submitted for approval");
  });

  test("17 - create Edit Group Information change request for Santos Family", async () => {
    // Continues directly on the Change Requests list from test 16 — no re-navigation needed.
    await page.getByRole("button", {name: "New Request"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Request Type"}).click();
    await page.getByText("Edit Group Information").click();
    console.log("✅ Request Type: Edit Group Information");

    await page.getByRole("textbox", {name: "Enter name or ID number..."}).fill("san");
    await page.getByRole("cell", {name: "Santos Family"}).click();
    console.log("✅ Registrant selected: Santos Family");

    await page.getByRole("button", {name: "Create"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("textbox", {name: "Address Line 1"})).toBeVisible({
      timeout: 10_000,
    });
    console.log("✅ Change request draft opened for editing");

    await page.getByRole("textbox", {name: "Address Line 1"}).fill("updated");
    await page.getByRole("textbox", {name: "Address Line 2"}).fill("updated");
    await page.getByRole("textbox", {name: "City"}).fill("updated");
    await page.getByRole("textbox", {name: "Postal Code"}).fill("6000");
    await expect(page.getByRole("textbox", {name: "Address Line 1"})).toHaveValue(
      "updated"
    );
    console.log("✅ Updated fields filled: Address, City, Postal Code");

    await page.getByRole("button", {name: "Next: Upload Documents"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("button", {name: "Upload Document"}).click();
    await page.getByRole("combobox", {name: "Document Type?"}).click();
    await page.getByRole("option", {name: "PSA Birth Certificate"}).click();
    await page
      .getByRole("dialog")
      .locator('input[type="file"]')
      .setInputFiles(
        path.resolve(__dirname, "..", "fixtures", "sample_valid_ID_parent.pdf")
      );
    await expect(
      page.getByRole("textbox", {name: "sample_valid_ID_parent.pdf"})
    ).toBeVisible({timeout: 10_000});
    await page.getByRole("button", {name: "Upload", exact: true}).click();
    console.log(
      "✅ Document uploaded: sample_valid_ID_parent.pdf (PSA Birth Certificate)"
    );

    await page.getByRole("button", {name: "Next: Review & Submit"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("tab", {name: "Attached Documents"}).click();
    await expect(
      page.getByRole("cell", {name: "sample_valid_ID_parent.pdf"})
    ).toBeVisible();
    console.log("✅ Review page shows attached document");

    await page.getByRole("button", {name: "Submit for Approval"}).click();
    console.log("✅ Edit Group Information change request submitted for approval");
  });

  test("18 - create Update ID Document change request for Santos, Jose Miguel", async () => {
    // Continues directly on the Change Requests list from test 17 — no re-navigation needed.
    await page.getByRole("button", {name: "New Request"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "Request Type"}).click();
    await page.getByText("Update ID Document").click();
    console.log("✅ Request Type: Update ID Document");

    await page.getByRole("textbox", {name: "Enter name or ID number..."}).fill("sant");
    await page
      .locator("tr.o_cr_search_result", {hasText: "SANTOS, JOSE MIGUEL"})
      .click();
    console.log("✅ Registrant selected: SANTOS, JOSE MIGUEL");

    await page.getByRole("button", {name: "Create"}).click();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByRole("combobox", {name: "ID Type"})).toBeVisible({
      timeout: 10_000,
    });
    console.log("✅ Change request draft opened for editing");

    await page.getByRole("combobox", {name: "ID Type"}).click();
    await page.getByRole("option", {name: "National ID"}).click();
    await page.getByRole("textbox", {name: "ID Number/Value?"}).fill("9999999991");

    const expiryDate = new Date();
    expiryDate.setDate(expiryDate.getDate() + 1);
    const expiryDateStr = formatDateMDY(expiryDate);
    await page.getByRole("textbox", {name: "Expiry Date"}).fill(expiryDateStr);
    await page.getByRole("textbox", {name: "Expiry Date"}).press("Escape");
    console.log(
      `✅ ID Information filled: National ID, 9999999991, expires ${expiryDateStr}`
    );

    await page.getByRole("button", {name: "Next: Upload Documents"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("button", {name: "Upload Document"}).click();
    await page.getByRole("combobox", {name: "Document Type?"}).click();
    await page.getByRole("option", {name: "PSA Birth Certificate"}).click();
    await page
      .getByRole("dialog")
      .locator('input[type="file"]')
      .setInputFiles(
        path.resolve(__dirname, "..", "fixtures", "sample_valid_ID_parent.pdf")
      );
    await expect(
      page.getByRole("textbox", {name: "sample_valid_ID_parent.pdf"})
    ).toBeVisible({timeout: 10_000});
    await page.getByRole("button", {name: "Upload", exact: true}).click();
    console.log(
      "✅ Document uploaded: sample_valid_ID_parent.pdf (PSA Birth Certificate)"
    );

    await page.getByRole("button", {name: "Next: Review & Submit"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("tab", {name: "Attached Documents"}).click();
    await expect(
      page.getByRole("cell", {name: "sample_valid_ID_parent.pdf"})
    ).toBeVisible();
    console.log("✅ Review page shows attached document");

    await page.getByRole("button", {name: "Submit for Approval"}).click();
    await page
      .getByRole("alert")
      .filter({hasText: "Update ID Document"})
      .getByRole("button", {name: "Close"})
      .click();
    console.log("✅ Update ID Document change request submitted for approval");
  });

  test("19 - create HQ validator user", async () => {
    await page.getByRole("menuitem", {name: "Settings"}).click();
    await page.waitForLoadState("domcontentloaded");
    await page.getByRole("button", {name: "Users & Companies"}).click();
    await page.getByRole("menuitem", {name: "Users"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("button", {name: "New"}).click();
    await page.waitForLoadState("domcontentloaded");

    await page.getByRole("textbox", {name: "e.g. John Doe"}).fill("hqval@mail.com");
    await page.getByRole("textbox", {name: "Login"}).fill("hqval@mail.com");
    console.log("✅ User name and login filled: hqval@mail.com");

    await page.getByRole("button", {name: "Add a line"}).click();
    await page.getByRole("combobox").fill("hq");
    await page.getByRole("option", {name: "CR HQ Validator"}).click();
    console.log("✅ Role assigned: CR HQ Validator");

    await page.getByRole("button", {name: "Actions menu"}).click();
    await page.getByRole("menuitem", {name: "Change Password"}).click();
    await expect(page.getByRole("button", {name: "Edit"})).toBeVisible();

    await page.getByRole("row", {name: "hqval@mail.com"}).locator("td").nth(1).click();
    await page.locator('input[type="password"]').fill("hqval1234$");
    await page.getByRole("button", {name: "Change Password"}).click();
    console.log("✅ Password set for hqval@mail.com");

    await logout(page);
    console.log("✅ HQ validator user created and logged out");
  });

  test("20 - HQ validator resolves the three pending change requests", async () => {
    // The CR sequence number is year-scoped (Odoo's ir.sequence uses the
    // current year), so build the expected value instead of hardcoding it.
    const crNumber = `CR/${new Date().getFullYear()}/00003`;

    // hqval hasn't logged in before this point, so only "admin" is a known cached
    // account — Odoo shows the plain form directly here, not the avatar picker
    // (that only appears once 2+ accounts are cached, as in test 21 below).
    await page
      .getByRole("textbox", {name: "Email Choose a user"})
      .fill("hqval@mail.com");
    await page.getByRole("textbox", {name: "Email Choose a user"}).press("Tab");
    await page.getByRole("textbox", {name: "Password"}).fill("hqval1234$");
    await page.getByRole("button", {name: "Log in"}).click();
    await expect(page.getByRole("row", {name: `${crNumber} Update ID`})).toBeVisible();
    console.log("✅ Logged in as HQ validator (hqval@mail.com)");

    await page.getByRole("menuitem", {name: "All Requests"}).click();
    await page.getByRole("cell", {name: "Edit Individual Information"}).click();
    await expect(
      page.getByRole("row", {name: "Given Name Jose Miguel Jose"})
    ).toBeVisible();

    await page.getByRole("button", {name: "Approve"}).click();
    await expect(page.getByRole("heading", {name: "Confirmation"})).toBeVisible();
    await page.getByRole("button", {name: "Ok"}).click();
    await expect(page.getByRole("button", {name: "Messages"})).toBeVisible();
    console.log("✅ Approved the Edit Individual Information change request");

    await page.getByRole("menuitem", {name: "All Requests"}).click();
    await expect(page.getByRole("row", {name: `${crNumber} Update ID`})).toBeVisible();
    await page.getByRole("cell", {name: "Edit Group Information"}).click();
    await expect(page.getByRole("row", {name: "Street — updated"})).toBeVisible();

    await page.getByRole("button", {name: "Reject"}).click();
    await expect(page.getByRole("heading", {name: "Confirmation"})).toBeVisible();
    await page.getByRole("button", {name: "Ok"}).click();

    // Scope to the actual Reject dialog by its heading rather than a
    // hardcoded #dialog_N id — Odoo's dialog counter isn't stable across runs.
    const rejectDialog = page
      .getByRole("dialog")
      .filter({has: page.getByRole("heading", {name: "Reject"})});
    await expect(rejectDialog).toBeVisible();
    await rejectDialog
      .getByRole("textbox", {name: "Rejection Reason?"})
      .fill("wrong information");
    await rejectDialog.getByRole("button", {name: "Reject"}).click();
    await expect(page.getByRole("button", {name: "Messages"})).toBeVisible();
    console.log("✅ Rejected the Edit Group Information change request");

    await page.getByRole("menuitem", {name: "All Requests"}).click();
    await expect(page.getByRole("row", {name: `${crNumber} Update ID`})).toBeVisible();
    await page.getByRole("cell", {name: "Update ID Document"}).click();
    await expect(page.getByRole("radiogroup", {name: "Statusbar"})).toBeVisible();

    await page.getByRole("button", {name: "Request Changes"}).click();
    await page
      .getByRole("textbox", {name: "Revision Notes?"})
      .fill("ID document required");
    await page.getByRole("button", {name: "Request Revision"}).click();
    await expect(page.getByRole("row", {name: `${crNumber} Update ID`})).toBeVisible();
    console.log("✅ Requested revision on the Update ID Document change request");

    await logout(page);
    console.log("✅ HQ validator logged out");
  });

  test("21 - admin confirms the three change request resolutions took effect", async () => {
    await expect(
      page.getByRole("button", {name: "admin Administrator "})
    ).toBeVisible();
    await page.getByRole("button", {name: " Use another user"}).click();
    await expect(page.getByRole("button", {name: "Choose a user"})).toBeVisible();

    await page.getByRole("textbox", {name: "Email Choose a user"}).fill("admin");
    await page.getByRole("textbox", {name: "Email Choose a user"}).press("Tab");
    await page.getByRole("textbox", {name: "Password"}).fill("admin");
    await page.getByRole("button", {name: "Log in"}).click();
    await expect(page.getByRole("button", {name: "User User is online"})).toBeVisible();
    console.log("✅ Logged back in as admin");

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await expect(page.getByRole("menuitem", {name: "All Individuals"})).toBeVisible();
    await page.getByRole("menuitem", {name: "All Individuals"}).click();

    await page
      .getByRole("searchbox", {name: "Search..."})
      .fill("SANTOS, JOSE MIGUEL UPDATED");
    await page.getByRole("searchbox", {name: "Search..."}).press("Enter");
    await expect(page.locator("tbody")).toContainText("SANTOS, JOSE MIGUEL UPDATED");
    await expect(page.locator("tbody")).toContainText("Jul 22, 1990");
    console.log("✅ Approved name change is reflected on the registrant");

    await page.getByRole("menuitem", {name: "Change Requests"}).click();
    await expect(page.locator("tbody")).toContainText("Rejected");
    await expect(page.locator("tbody")).toContainText("Needs Changes");
    console.log("✅ Change Requests list shows Rejected and Needs Changes");

    await logout(page);
    console.log("✅ Admin logged out");
  });

  test("22 - imports 200 individual registrants via Excel file", async () => {
    await login(page);
    console.log("✅ Logged in as admin");

    await page.getByRole("list").getByRole("menuitem", {name: "Registry"}).click();
    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await page.getByRole("menuitem", {name: "All Individuals"}).click();

    await page.getByRole("button", {name: "Actions menu"}).click();
    await page.getByRole("menuitem", {name: " Import records"}).click();
    // No click on "Upload Data File" first — that button triggers the hidden
    // input's native click, popping a real OS file dialog that Playwright
    // can't control. setInputFiles sets the file directly, no dialog needed.
    await page
      .locator('input[type="file"]')
      .setInputFiles(path.resolve(__dirname, "..", "fixtures", "200_individuals.xlsx"));
    await page.getByRole("button", {name: "Test"}).click();
    await page.getByRole("button", {name: "Import"}).click();
    await expect(page.getByLabel("Pager")).toContainText("200");
    console.log("✅ Imported 200 individual registrants, pager confirms count");

    await logout(page);
    console.log("✅ Admin logged out");
  });

  test("23 - imports 200 group registrants via Excel file", async () => {
    await login(page);
    console.log("✅ Logged in as admin");

    await page.getByRole("button", {name: "Browse All (Audit)"}).click();
    await expect(page.getByRole("menuitem", {name: "All Individuals"})).toBeVisible();
    await page.getByRole("menuitem", {name: "All Groups"}).click();

    await page.getByRole("button", {name: "Actions menu"}).click();
    await page.getByRole("menuitem", {name: " Import records"}).click();
    // No click on "Upload Data File" first — see the comment in test 22.
    await page
      .locator('input[type="file"]')
      .setInputFiles(path.resolve(__dirname, "..", "fixtures", "200_groups.xlsx"));
    await expect(page.getByRole("button", {name: "User User is online"})).toBeVisible();

    await page.getByRole("button", {name: "Test"}).click();
    await expect(page.locator("b")).toContainText("Everything seems valid.");
    await page.getByRole("button", {name: "Import"}).click();
    await expect(page.getByRole("alert")).toContainText(
      "200 records successfully imported"
    );
    await expect(page.getByLabel("Pager")).toContainText("200");
    console.log("✅ Imported 200 group registrants, pager confirms count");

    await logout(page);
    console.log("✅ Admin logged out");
  });
});
