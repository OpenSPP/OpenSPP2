### Prerequisites

- OpenSPP instance with `spp_cel_registry_search` module installed
- Demo data loaded (registrants with various attributes: birthdate, gender, registration date, phone,
  email, disabled status)
- At least one user with **Registry Officer** role (has CEL Search access automatically)
- At least one base user **without** Registry Officer or CEL Search User group

### Module Overview

The CEL Registry Search module adds an **Advanced Search** portal under the Registry menu. It allows
users to write CEL (Common Expression Language) expressions to query registrants. The module has no
Python models — it is a frontend-only OWL component that calls `spp.cel.service` on the backend.

**URL:** `/odoo/registry-cel`
**Menu:** Registry > Advanced Search

---

### Test 1: Installation and Menu Visibility

**1.1 Module installs without errors**

1. Go to **Apps**
2. Search for "CEL Registry Search"
3. Verify the module is listed with status "Installed"
4. Verify no errors in the server log related to this module

**Expected:** Module is installed and functional.

**1.2 Menu visible to Registry Officer**

1. Log in as a user with the **Registry Officer** role
2. Click the **Registry** top menu

**Expected:** "Advanced Search" menu item appears under Registry (sequence 85, typically near the
bottom of the menu).

**1.3 Menu not visible to base user**

1. Log in as a base user who does NOT have the Registry Officer, Registry Manager, or CEL Search
   User group
2. Click the **Registry** top menu (if visible)

**Expected:** "Advanced Search" menu item does NOT appear. The user should not have access to the
CEL search portal.

**1.4 Menu visible to CEL Search User**

1. Assign a user the **CEL Search User** group (without Registry Officer)
2. Log in as that user
3. Navigate to Registry

**Expected:** "Advanced Search" menu item appears. This user should also have Registry Viewer
permissions (implied by the CEL Search User group).

---

### Test 2: Initial Page Load (Empty State)

**2.1 Page loads correctly**

1. Navigate to **Registry > Advanced Search** (or go to `/odoo/registry-cel`)

**Expected:**
- Page title: "Advanced Search" with a code icon
- A card containing:
  - **Profile** dropdown defaulting to "Individuals"
  - **CEL Expression** label with an empty code editor
  - **Search** button (disabled)
  - **Clear** button (disabled)
- Below the card: an empty state with:
  - A large code icon (faded)
  - Text: "Search with CEL Expressions"
  - Text: "Write a CEL expression to filter registrants, then click Search."
  - Three example expressions:
    - `age_years(r.birthdate) >= 18` - Adults 18+
    - `is_female(r.gender_id)` - Females
    - `r.registration_date > "2024-01-01"` - Recent registrations

**2.2 Profile dropdown options**

1. Click the **Profile** dropdown

**Expected:** Two options: "Individuals" and "Groups". "Individuals" is selected by default.

---

### Test 3: CEL Expression Editor

**3.1 Editor accepts input**

1. Click inside the CEL expression editor
2. Type: `r.name != ""`

**Expected:**
- Text appears in the editor with syntax highlighting
- The **Search** button becomes enabled
- The **Clear** button becomes enabled
- A validation indicator appears (green checkmark with match count if valid)

**3.2 Autocomplete and symbol browser**

1. Clear the editor
2. Type: `r.` (with the dot)

**Expected:** An autocomplete dropdown appears showing available fields (e.g., `name`, `birthdate`,
`gender_id`, `phone`, `email`, `registration_date`, `disabled`, etc.).

**3.3 Toolbar and symbol browser visibility**

1. Look at the editor area

**Expected:** A toolbar is visible above the editor. A symbol browser panel is available for
browsing available fields and functions.

**3.4 Invalid expression feedback**

1. Type an invalid expression: `r.name ===`

**Expected:**
- A red error indicator appears (red X icon)
- The error message describes the syntax issue
- The **Search** button is disabled (cannot search with invalid expression)

**3.5 Validation match count**

1. Type a valid expression: `r.name != ""`

**Expected:** A green checkmark appears with a count like "X match(es)" showing how many registrants
match before you execute the search.

---

### Test 4: Search — Individuals Profile

**4.1 Basic search with results**

1. Set profile to **Individuals**
2. Type: `r.name != ""`
3. Click **Search**

**Expected:**
- A loading spinner appears briefly with "Searching..." text
- Results appear showing "X Result(s) Found" (or "Showing 50 of X Result(s)" if more than 50)
- Each result shows:
  - Registrant name
  - Type badge: "Individual" with a person icon
  - Registration date (right side)
  - Phone number (if present, with phone icon)
  - Email (if present, with envelope icon)
  - A right chevron indicating the row is clickable

**4.2 Search with no results**

1. Type an expression that matches nothing: `r.name == "ZZZZNONEXISTENT999"`
2. Click **Search**

**Expected:**
- Result section shows: "0 Result(s) Found"
- An info alert appears: "No registrants found matching your CEL expression."

**4.3 Result limit (50 records)**

1. Type an expression that matches many registrants: `r.name != ""`
2. Click **Search**

**Expected:** If more than 50 matches exist:
- Header shows: "Showing 50 of X Result(s)"
- Only 50 results are displayed in the list

**4.4 Click a result to open form**

1. Perform a search that returns results
2. Click on any result row

**Expected:** The individual's form view opens (the standard Individual form from `spp_registry`).
You should be able to navigate back using the browser back button or breadcrumbs.

**4.5 Disabled registrant display**

1. Ensure at least one registrant is disabled (has `disabled = True`)
2. Search with an expression that includes disabled registrants

**Expected:** Disabled registrants appear in the list with:
- Muted text (gray, reduced opacity)
- A yellow "Disabled" badge with a ban icon next to the name
- The row is still clickable and opens the form view

---

### Test 5: Search — Groups Profile

**5.1 Switch to Groups profile**

1. Change the **Profile** dropdown to "Groups"

**Expected:**
- The dropdown shows "Groups" as selected
- If there was an expression in the editor, validation re-runs for the Groups profile
- The editor may show different autocomplete options appropriate for groups

**5.2 Search groups**

1. With "Groups" selected, type: `r.name != ""`
2. Click **Search**

**Expected:**
- Results show group registrants
- Each result shows type badge: "Group" with a people icon (fa-users)
- Clicking a result opens the Group form view (with membership tab)

**5.3 Profile switch triggers re-validation**

1. Type a valid expression with "Individuals" selected
2. Note the validation status (green checkmark)
3. Switch to "Groups"

**Expected:** The validation re-runs. The expression may still be valid (if it uses fields common to
both profiles) or may become invalid (if it uses individual-specific fields).

---

### Test 6: Clear Functionality

**6.1 Clear after search**

1. Perform a search that returns results
2. Click **Clear**

**Expected:**
- The expression editor is emptied
- The results section disappears
- The empty state (with examples) reappears
- The **Search** button is disabled
- The **Clear** button is disabled

**6.2 Clear with expression but no search**

1. Type an expression but do NOT click Search
2. Click **Clear**

**Expected:**
- The expression editor is emptied
- The empty state remains (no results were shown)
- Both buttons are disabled

---

### Test 7: Error Handling

**7.1 Backend error**

1. Type an expression that causes a backend error (e.g., reference a field that does not exist and
   somehow bypasses validation): `r.nonexistent_field_xyz > 0`

**Expected:**
- A red error notification appears with the error message
- The page returns to the empty state (does NOT show "0 Result(s) Found")
- The expression remains in the editor so the user can fix it

**7.2 Empty expression warning**

1. Clear the editor completely
2. If the Search button is somehow clickable, click it

**Expected:** The Search button should be disabled when the expression is empty. If triggered
programmatically, a warning notification appears: "Please enter a CEL expression to search."

**7.3 Invalid expression warning**

1. Type an invalid expression (e.g., `r.name ===`)
2. If the Search button is somehow clickable, click it

**Expected:** The Search button should be disabled when the expression is invalid. If triggered
programmatically, a warning notification appears: "Please fix the expression errors before
searching."

---

### Test 8: Visual and Layout Checks

**8.1 Hover effect on results**

1. Perform a search that returns results
2. Hover your mouse over a result row

**Expected:** The row background changes to a slightly darker shade (light gray), indicating it is
clickable.

**8.2 Responsive layout**

1. Resize the browser window to a narrow width (< 768px)

**Expected:**
- The page remains usable
- The header font size reduces
- The profile dropdown takes full width
- Result items stack gracefully

**8.3 Page scrolling**

1. Perform a search that returns many results (close to 50)
2. Scroll down the page

**Expected:** The page scrolls smoothly. The results list does not get clipped or overflow
incorrectly.

---

### Test 9: Security Verification

**9.1 Direct URL access without permission**

1. Log in as a base user who does NOT have the CEL Search User or Registry Officer group
2. Navigate directly to `/odoo/registry-cel`

**Expected:** The user should either see an access error or be redirected. They should NOT be able
to use the search portal.

**9.2 CEL Search User can only view (not edit) registrants**

1. Log in as a user with ONLY the **CEL Search User** group
2. Perform a search and click a result to open the form

**Expected:** The registrant form opens in read-only mode. The user should be able to view but not
modify the registrant (since CEL Search User only implies Registry Viewer, not Officer).

---

### Test Summary Checklist

| # | Test | Pass/Fail |
|---|------|-----------|
| 1.1 | Module installs without errors | |
| 1.2 | Menu visible to Registry Officer | |
| 1.3 | Menu not visible to base user | |
| 1.4 | Menu visible to CEL Search User | |
| 2.1 | Page loads with correct empty state | |
| 2.2 | Profile dropdown has correct options | |
| 3.1 | Editor accepts input and enables Search | |
| 3.2 | Autocomplete works | |
| 3.3 | Toolbar and symbol browser visible | |
| 3.4 | Invalid expression shows error | |
| 3.5 | Validation shows match count | |
| 4.1 | Individual search returns results | |
| 4.2 | Search with no results shows info alert | |
| 4.3 | Result limit (50) works correctly | |
| 4.4 | Clicking result opens Individual form | |
| 4.5 | Disabled registrant displayed correctly | |
| 5.1 | Profile switch to Groups works | |
| 5.2 | Groups search returns group results | |
| 5.3 | Profile switch triggers re-validation | |
| 6.1 | Clear after search resets everything | |
| 6.2 | Clear with expression but no search | |
| 7.1 | Backend error shows notification, returns to empty state | |
| 7.2 | Empty expression warning | |
| 7.3 | Invalid expression warning | |
| 8.1 | Hover effect visible on result rows | |
| 8.2 | Responsive layout on narrow screens | |
| 8.3 | Page scrolling works correctly | |
| 9.1 | Direct URL access denied without permission | |
| 9.2 | CEL Search User has read-only access | |
