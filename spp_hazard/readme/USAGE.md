Testing guide for QA validation of the OpenSPP Hazard and Emergency Management module.

**Prerequisites**

1. OpenSPP instance running with `spp_hazard` installed (and demo data loaded)
2. Three test users configured with different security groups:
   - **Admin user** — system administrator (has all access)
   - **Manager user** — assigned to Hazard: Manager group
   - **Officer user** — assigned to Hazard: Officer group
   - **Viewer user** — assigned to Hazard: Viewer group
3. At least one area record in `spp.area` (created via Registry > Areas)
4. At least one registrant (individual) with an area assigned

To assign hazard groups: **Settings > Users & Companies > Users > (select user) > Access Rights
tab > Hazard section** — choose Viewer, Officer, or Manager.

---

**1. Module Installation**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1.1 | Navigate to **Apps**, search for "Hazard" | "OpenSPP Hazard & Emergency Management" appears |
| 1.2 | Install the module | Installation completes without errors |
| 1.3 | Refresh the browser | "Hazard and Emergency" appears in the top application menu bar |

---

**2. Menu Structure**

Log in as **Admin** or **Manager**.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 2.1 | Click **Hazard and Emergency** in the top menu | Submenu appears with "Incidents" and "Configuration" sections |
| 2.2 | Click **Incidents > All Incidents** | Incident list view loads (URL ends with `/hazard-incidents`) |
| 2.3 | Click **Incidents > Impact Records** | Impact list view loads (URL ends with `/hazard-impacts`) |
| 2.4 | Click **Configuration > Hazard Categories** | Category list loads with pre-seeded Active filter (URL: `/hazard-categories`) |
| 2.5 | Click **Configuration > Impact Types** | Impact type list loads with Active filter (URL: `/hazard-impact-types`) |

---

**3. Hazard Categories (Configuration)**

**3.1 Pre-installed Data (Demo)**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3.1.1 | Open **Configuration > Hazard Categories** | List shows categories. If demo data loaded: "Natural Disaster", "Storm", "Typhoon", "Geological", "Earthquake", "Volcanic Eruption", "Hydrological", "Flood", "Climate", "Drought", "Health Emergency", "Pandemic", "Disease Outbreak", "Conflict", "Armed Conflict", "Economic Shock", "Food Crisis" |
| 3.1.2 | Check the "Complete Name" column | Hierarchical names shown, e.g., "Natural Disaster > Storm > Typhoon" |
| 3.1.3 | Check the "Incidents" column | Shows integer count for each category |

**3.2 Create a Category**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3.2.1 | Click **New** | Form opens with Name field focused |
| 3.2.2 | Enter Name: `Test Wildfire`, Code: `TEST_WILDFIRE` | Fields accept input |
| 3.2.3 | Set Parent Category to "Natural Disaster" | Dropdown shows only active categories |
| 3.2.4 | Save | Record saves. Complete Name shows "Natural Disaster > Test Wildfire" |
| 3.2.5 | Navigate to the parent "Natural Disaster" record | "Subcategories" section is visible below the form and lists "Test Wildfire" |

**3.3 Category Incident Count**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3.3.1 | Open a category that has linked incidents (e.g., "Typhoon" if demo data loaded) | "Number of Incidents" field shows the count in the right column |
| 3.3.2 | Verify the count matches the actual number of incidents | Count should be accurate |

**3.4 Category Code Uniqueness**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3.4.1 | Create a new category with Code = `TEST_WILDFIRE` (same as 3.2) | Error: "A hazard category with this code already exists!" |

**3.5 Deactivation**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3.5.1 | Open a category, uncheck "Active", save | Red "Inactive" ribbon appears at top-right of form |
| 3.5.2 | Return to the list (Active filter is on by default) | Inactive category is hidden from the list |
| 3.5.3 | In search bar, click "Active" filter to remove it, add "Inactive" filter | Inactive category now visible |

**3.6 Search and Grouping**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 3.6.1 | Type in search bar, select "Name" search | Filters by name |
| 3.6.2 | Type in search bar, select "Code" search | Filters by code |
| 3.6.3 | Use Filters > Active / Inactive | Filters correctly |
| 3.6.4 | Use Group By > Parent | Categories grouped by parent |

---

**4. Impact Types (Configuration)**

**4.1 Pre-installed Data**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 4.1.1 | Open **Configuration > Impact Types** | List shows 14 pre-configured types with drag handles for reordering |
| 4.1.2 | Verify Physical types | Displacement, Property Damage, Injury, Death/Fatality |
| 4.1.3 | Verify Economic types | Livelihood Loss, Asset Destruction, Crop Loss, Livestock Loss |
| 4.1.4 | Verify Health types | Illness, Disability, Psychological Impact |
| 4.1.5 | Verify Social types | Family Separation, Community Disruption, Education Disruption |
| 4.1.6 | Check "Category" column | Shows as badge widgets (Physical, Economic, Health, Social) |
| 4.1.7 | Check "Usage" column | Shows 0 for types not yet linked to any impact record |

**4.2 Create an Impact Type**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 4.2.1 | Click **New** | Form opens |
| 4.2.2 | Enter Name: `Water Contamination`, Code: `WATER_CONTAM`, Category: Health | Fields accept input |
| 4.2.3 | Save | Record saves successfully |

**4.3 Reorder via Drag**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 4.3.1 | In the list view, grab the drag handle (hamburger icon) on a type | Row becomes draggable |
| 4.3.2 | Drop it at a different position | Sequence updates; reload confirms new order |

**4.4 Code Uniqueness**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 4.4.1 | Create another type with Code = `WATER_CONTAM` | Error: "An impact type with this code already exists!" |

**4.5 Search Filters**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 4.5.1 | Use Filters > Physical / Economic / Health / Social | Filters by category correctly |
| 4.5.2 | Use Group By > Category | Types grouped into 4 category sections |

---

**5. Hazard Incidents**

**5.1 Demo Data**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.1.1 | Open **Incidents > All Incidents** | If demo loaded: 3 incidents visible |
| 5.1.2 | "Demo Typhoon Alpha" | Status: Recovery (yellow badge), Severity: Level 4 |
| 5.1.3 | "Demo Flooding Event" | Status: Closed (grey badge), has End Date |
| 5.1.4 | "Demo Drought 2024" | Status: Active (green badge), no End Date |

**5.2 Create an Incident**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.2.1 | Click **New** | Form opens. Status defaults to "Active". Statusbar shows: Alert / Active / Recovery / Closed |
| 5.2.2 | Enter Name: `Test Earthquake`, Code: `TEST-EQ-001` | Fields accept input |
| 5.2.3 | Select Category: search for "Earthquake" | Dropdown shows only active categories, filtered by search text |
| 5.2.4 | Set Start Date: today's date | Date picker works |
| 5.2.5 | Leave End Date empty | Allowed (ongoing incident) |
| 5.2.6 | Set Severity: "Level 3 - Significant" | Selection dropdown works |
| 5.2.7 | Save | Record saves. "Ongoing" ribbon appears (yellow, top-right corner) |

**5.3 Incident Form Layout**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.3.1 | Check the header | "Start Recovery" button visible (since status is Active). "Close Incident" button visible. Status bar shows current step |
| 5.3.2 | Check the button box (top-right) | "Affected" stat button (fa-users icon) always visible. "Areas" stat button visible only if areas > 0 |
| 5.3.3 | Check left column | Code, Category, Severity fields |
| 5.3.4 | Check right column | Start Date, End Date fields |
| 5.3.5 | Check notebook tabs | Three tabs: "Description", "Affected Areas", "Impacts" |
| 5.3.6 | Click "Description" tab | HTML editor for incident description |
| 5.3.7 | Click "Affected Areas" tab | Instruction text visible. Inline-editable list with: Area, Severity Override, Affected Population Estimate, Notes |
| 5.3.8 | Click "Impacts" tab | List showing Registrant, Impact Type, Damage Level, Impact Date, Verification Status |
| 5.3.9 | Scroll to bottom of form | Chatter (message log + activity scheduling) visible below the form |

**5.4 Code Uniqueness**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.4.1 | Create another incident with Code = `TEST-EQ-001` | Error: "An incident with this code already exists!" |

**5.5 Date Validation**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.5.1 | Edit the incident, set End Date before Start Date | Error: "End date must be after start date." |
| 5.5.2 | Set End Date after Start Date, save | Saves successfully. "Ongoing" ribbon disappears (end date is now set) |
| 5.5.3 | Clear End Date, save | "Ongoing" ribbon reappears |

**5.6 Status Workflow (Lifecycle)**

Use the incident created in 5.2 (starts as "Active").

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.6.1 | Click **Start Recovery** | Status changes to "Recovery". Button changes to "Set Active". "Close Incident" still visible |
| 5.6.2 | Click **Set Active** | Status returns to "Active". "Start Recovery" button returns |
| 5.6.3 | Click **Start Recovery** again | Status = Recovery |
| 5.6.4 | Click **Close Incident** | Status = Closed. End Date auto-filled with today if it was empty. All fields become readonly |
| 5.6.5 | Check the form in Closed state | No action buttons visible (Set Active, Start Recovery, Close are all hidden). All fields are readonly. Description, areas, and impacts are readonly |

**5.7 Add Affected Areas**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.7.1 | Open a non-closed incident, go to "Affected Areas" tab | Instruction text: "Add areas affected by this incident..." |
| 5.7.2 | Click "Add a line" | New row appears. Area field is a dropdown (no create option) |
| 5.7.3 | Select an Area | Area appears in the row |
| 5.7.4 | Set Severity Override: "Level 5 - Catastrophic" | Selection dropdown works |
| 5.7.5 | Enter Affected Population Estimate: 5000 | Integer field accepts value |
| 5.7.6 | Save | Area link saved. "Areas" stat button now visible with count = 1 |
| 5.7.7 | Try adding the same area again | Error: "This area is already linked to this incident!" |

**5.8 Stat Buttons**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.8.1 | Click "Affected" stat button | Opens Impact Records list filtered to this incident |
| 5.8.2 | Click browser back | Returns to incident form |
| 5.8.3 | Click "Areas" stat button | Opens Area list filtered to linked areas |

**5.9 Search and Filters (Incident List)**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.9.1 | Use search: type a name | Filters by incident name |
| 5.9.2 | Use search: select Code field | Filters by code |
| 5.9.3 | Use search: select Category | Filters by category |
| 5.9.4 | Filters > Alert | Shows only alert-status incidents (blue-tinted rows) |
| 5.9.5 | Filters > Active | Shows only active-status incidents |
| 5.9.6 | Filters > Recovery | Shows only recovery-status incidents (yellow-tinted rows) |
| 5.9.7 | Filters > Closed | Shows only closed incidents (grey/muted rows) |
| 5.9.8 | Filters > Ongoing | Shows incidents with `is_ongoing = True` |
| 5.9.9 | Group By > Status | Groups into status sections |
| 5.9.10 | Group By > Category | Groups by hazard category |
| 5.9.11 | Group By > Severity | Groups by severity level |
| 5.9.12 | Group By > Start Date | Groups by month |

**5.10 List View Decorations**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.10.1 | Check row coloring | Alert rows: blue tint. Recovery rows: yellow tint. Closed rows: grey/muted. Active rows: default (no special coloring) |
| 5.10.2 | Check Status column badges | Alert: blue badge. Active: green badge. Recovery: yellow badge. Closed: grey badge |
| 5.10.3 | Check columns visible | Name, Code, Category, Start Date, End Date (optional), Status, Severity, Areas, Affected |

---

**6. Impact Records**

**6.1 Create an Impact Record**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 6.1.1 | Navigate to **Incidents > Impact Records**, click **New** | Form opens. Verification Status defaults to "Reported" |
| 6.1.2 | Select Registrant (h1 title area) | Dropdown shows registrants only (`is_registrant = True`). "Create" option not available |
| 6.1.3 | Select Incident (h2 below registrant) | Dropdown shows incidents. "Create" option not available |
| 6.1.4 | Set Impact Type: "Displacement" | Only active impact types shown. "Create" option not available |
| 6.1.5 | Set Damage Level: "Severe" | Selection works (Minimal, Moderate, Severe, Critical, Partially Damaged, Totally Damaged) |
| 6.1.6 | Set Impact Date: same as or after incident start date | Date accepted |
| 6.1.7 | Save | Record saves. Statusbar shows: Reported / Verified / Disputed / Closed |

**6.2 Impact Date Validation**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 6.2.1 | Edit the impact, set Impact Date before the incident's Start Date | Error: "Impact date cannot be before the incident start date." |

**6.3 Duplicate Impact Constraint**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 6.3.1 | Create another impact with the same Incident + Registrant + Impact Type | Error: "This registrant already has an impact of this type for this incident!" |
| 6.3.2 | Same Incident + Registrant but different Impact Type (e.g., "Property Damage") | Creates successfully — different types allowed for same registrant |

**6.4 Verification Workflow**

Using the impact created in 6.1 (starts as "Reported"):

| Step | Action | Expected Result |
|------|--------|-----------------|
| 6.4.1 | Check header buttons | "Verify" (primary), "Mark Disputed" (secondary), "Close" (secondary) visible. "Reset to Reported" hidden |
| 6.4.2 | Check "Verification Information" section | Hidden (only shows when not in "Reported" status) |
| 6.4.3 | Click **Verify** | Status → Verified. "Verification Information" section appears showing "Verified By" (current user) and "Verification Date" (now). "Verify" button disappears. "Mark Disputed" and "Close" remain |
| 6.4.4 | Click **Mark Disputed** | Status → Disputed. "Reset to Reported" button appears. "Verify" hidden. "Close" visible |
| 6.4.5 | Click **Reset to Reported** | Status → Reported. Verified By and Verification Date cleared. Back to initial button state |
| 6.4.6 | Click **Close** | Status → Closed. All fields become readonly. Only "Reset to Reported" visible |
| 6.4.7 | Click **Reset to Reported** | Status → Reported again. Fields editable again |

**6.5 Impact Form Layout**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 6.5.1 | Check title area | Registrant name displayed as h1, Incident name as h2 |
| 6.5.2 | Check left group ("incident_info") | Shows Incident Name (readonly) and Impact Category (readonly) for quick context |
| 6.5.3 | Check right group ("impact_details") | Impact Type, Damage Level, Impact Date fields |
| 6.5.4 | Check "Notes" section | Notes field displayed below verification info with full-width layout |
| 6.5.5 | Check bottom of form | Chatter visible (message log and activities) |

**6.6 Search and Filters (Impact List)**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 6.6.1 | Search by Incident | Filters to selected incident |
| 6.6.2 | Search by Registrant | Filters to selected registrant |
| 6.6.3 | Search by Impact Type | Filters to selected type |
| 6.6.4 | Filters > Reported / Verified / Disputed / Closed | Each shows correct subset |
| 6.6.5 | Filters > Critical | Shows only `critical` and `totally_damaged` damage levels |
| 6.6.6 | Filters > Severe or Critical | Shows `severe`, `critical`, and `totally_damaged` |
| 6.6.7 | Group By > Incident | Groups by incident |
| 6.6.8 | Group By > Impact Type | Groups by type |
| 6.6.9 | Group By > Damage Level | Groups by severity |
| 6.6.10 | Group By > Verification Status | Groups by status |
| 6.6.11 | Group By > Impact Date | Groups by month |

**6.7 Impact List Decorations**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 6.7.1 | Check row coloring | Reported: blue. Verified: green. Disputed: yellow. Closed: grey/muted |
| 6.7.2 | Verification Status badges | Same color coding as rows |
| 6.7.3 | Damage Level column | Shows as badge widget (neutral color) |
| 6.7.4 | Optional columns | "Verified By" and "Verified Date" available under column options (hidden by default) |

---

**7. Registrant Integration**

**7.1 Stat Button**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 7.1.1 | Open a registrant that has NO impact records | No "Impacts" stat button visible in button box |
| 7.1.2 | Open a registrant that HAS impact records | "Impacts" stat button with bolt icon visible, showing count |
| 7.1.3 | Click the stat button | Opens Impact Records list filtered to this registrant |

**7.2 Emergency Response Tab**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 7.2.1 | Open a registrant with NO impacts | "Emergency Response" tab visible. Tab content shows: "No emergency response records yet. Impact records will appear here when this registrant is affected by a hazard incident." |
| 7.2.2 | Open a registrant with impacts from a CLOSED incident | "Emergency Response" tab shows the "Incident Impacts" section with a readonly list of impacts. No yellow alert banner |
| 7.2.3 | Open a registrant with impacts from an ACTIVE or ALERT incident | Yellow alert banner with warning icon: "Active incident impacts recorded. This registrant is affected by one or more ongoing hazard incidents." Impact list shows below |
| 7.2.4 | Check the impact list columns | Incident, Impact Type, Damage Level (badge), Impact Date, Verification Status (badge with colors) |
| 7.2.5 | Verify the list is readonly | Cannot edit, add, or delete impact records from this view |

**7.3 Registrant List Extensions**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 7.3.1 | Open the registrants list view | "Impacts" and "Active Impact" columns available in column options (hidden by default) |
| 7.3.2 | Enable both columns via column selector | Columns show correct counts and boolean values |

**7.4 Registrant Search Extensions**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 7.4.1 | In registrant search, check Filters | "Has Active Impact" and "Has Any Impact" filters available |
| 7.4.2 | Apply "Has Active Impact" | Shows only registrants with impacts from active/alert/recovery incidents |
| 7.4.3 | Apply "Has Any Impact" | Shows all registrants with any impact count > 0 |

---

**8. Security and Access Control**

**8.1 Viewer Access**

Log in as the **Viewer** user.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 8.1.1 | Navigate to Hazard and Emergency | Menu visible. "Incidents" submenu visible |
| 8.1.2 | Check for "Configuration" submenu | NOT visible (restricted to managers) |
| 8.1.3 | Open Incidents > All Incidents | Can view the list and open records |
| 8.1.4 | Try to create a new incident (click New) | Access denied or "New" button not available |
| 8.1.5 | Try to edit an existing incident | Cannot save changes (write access denied) |
| 8.1.6 | Open Incidents > Impact Records | Can view but not create or edit |

**8.2 Officer Access**

Log in as the **Officer** user.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 8.2.1 | Check for "Configuration" submenu | NOT visible (restricted to managers) |
| 8.2.2 | Create a new incident | Succeeds |
| 8.2.3 | Edit an existing incident | Succeeds |
| 8.2.4 | Try to delete an incident | Access denied (officer has no delete permission) |
| 8.2.5 | Create a new impact record | Succeeds |
| 8.2.6 | Edit an existing impact record | Succeeds |
| 8.2.7 | Try to delete an impact record | Access denied |
| 8.2.8 | Open a registrant's Emergency Response tab | Can view impact records (read access) |

**8.3 Manager Access**

Log in as the **Manager** user.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 8.3.1 | Check for "Configuration" submenu | Visible with "Hazard Categories" and "Impact Types" |
| 8.3.2 | Create a hazard category | Succeeds |
| 8.3.3 | Edit a hazard category | Succeeds |
| 8.3.4 | Delete a hazard category (with no linked incidents) | Succeeds |
| 8.3.5 | Try to delete a category linked to an incident | Blocked by `ondelete="restrict"` — error shown |
| 8.3.6 | Create, edit, delete impact types | All succeed |
| 8.3.7 | Create, edit, delete incidents | All succeed |
| 8.3.8 | Create, edit, delete impact records | All succeed |

---

**9. URL Paths (Pretty URLs)**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 9.1 | Navigate to All Incidents | URL contains `/hazard-incidents` |
| 9.2 | Navigate to Impact Records | URL contains `/hazard-impacts` |
| 9.3 | Navigate to Hazard Categories | URL contains `/hazard-categories` |
| 9.4 | Navigate to Impact Types | URL contains `/hazard-impact-types` |

---

**10. Empty States**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 10.1 | Open Incidents list with no records (new database, no demo) | Smiling face icon with text: "Record your first hazard incident" and helper text about tracking events |
| 10.2 | Open Impact Records list with no records | Smiling face icon with text: "Record impacts on registrants" |
| 10.3 | Open Categories list with no records | Smiling face icon with text: "Create your first hazard category" |
| 10.4 | Open Impact Types list with no records | Smiling face icon with text: "Define impact types" |

---

**11. Chatter and Tracking**

**11.1 Incident Tracking**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 11.1.1 | Create an incident, then change its status | Chatter log shows "Status: Active → Recovery" (or whichever transition) |
| 11.1.2 | Change the severity | Chatter log shows "Severity: Level 2 → Level 4" |
| 11.1.3 | Change the category | Chatter log shows category change |
| 11.1.4 | Post a message in the chatter | Message appears in log |
| 11.1.5 | Schedule an activity | Activity appears in the scheduled activities section |

**11.2 Impact Tracking**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 11.2.1 | Create an impact, then verify it | Chatter shows "Verification Status: Reported → Verified", "Verified By" set, "Verification Date" set |
| 11.2.2 | Change the damage level | Chatter log shows change |
| 11.2.3 | Post a message | Message appears |

---

**12. Edge Cases**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 12.1 | Create an incident with status "Alert" (create, then note: default is Active — the "alert" status must be set by creating with status alert or changing the initial state) | "Set Active" button visible. "Close Incident" visible. "Start Recovery" NOT visible (only visible for Active) |
| 12.2 | Create an incident, add areas, then close it | All tabs (Description, Affected Areas, Impacts) become readonly. Cannot add or remove areas |
| 12.3 | Close an incident that has no end date | End Date is auto-populated with today's date |
| 12.4 | Close an incident that already has an end date | End Date preserved (not overwritten) |
| 12.5 | Create an impact, set the date to exactly the incident start date | Accepted (boundary case: equal dates are valid) |
| 12.6 | Delete an incident that has geofences linked to it | Incident deletes. Geofence's "Related Incident" field becomes empty (set null) |
| 12.7 | Try to delete an area that is linked to an incident via incident_area_ids | Blocked by `ondelete="restrict"` |

---

**13. Cross-Module: Groups/Households**

| Step | Action | Expected Result |
|------|--------|-----------------|
| 13.1 | Open a group (household) registrant form | "Emergency Response" tab visible (groups reuse the individual form view) |
| 13.2 | Create an impact record for a group registrant | Impact record creation succeeds; registrant domain allows groups (`is_registrant=True` includes both) |
| 13.3 | View the group's Emergency Response tab | Impact records appear correctly |

---

**Defect Reference**

All previously known issues from the fix plan (`docs/plans/SPP_HAZARD_FIXES_PLAN.md`) have been resolved.
If you encounter unexpected behavior, please report it as a new issue.

| ID | Known Limitation | Notes |
|----|-----------------|-------|
| N/A | Badge decorations (severity, damage level) rely on color only | Odoo's badge widget does not support embedded icons. Screen reader users rely on the text label |
