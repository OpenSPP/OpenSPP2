## Prerequisites

- The module **OpenSPP Import Match** is installed
- You are logged in as a user with the **SPP Admin** (`spp_security.group_spp_admin`) role

## Test 1: Create a Matching Rule

**Steps:**

1. Navigate to **Registry > Configuration > Import Match**
2. Click **New**
3. Enter a name (e.g., "Match Partner by Name")
4. In the **Match Details** tab, set **Model** to `Contact` (res.partner)
5. Verify that **Model Name** and **Model Description** auto-populate as `res.partner` and `Contact`
6. In the **Fields** list, click **Add a line**
7. Select a non-relational field (e.g., `Name`)
8. Verify that the **Sub-Field** column is read-only (greyed out) for non-relational fields
9. Leave **Is Conditional** unchecked and **Imported Value** empty
10. Click **Save**

**Expected:**

- The rule appears in the list view with the name you entered
- The list view shows a drag handle for reordering by sequence

## Test 2: Verify Duplicate Field Validation

**Steps:**

1. Open the matching rule created in Test 1
2. In the **Fields** list, click **Add a line**
3. Select the same non-relational field (e.g., `Name`) that already exists in the list

**Expected:**

- A validation error appears: "Field 'Name', already exists!"
- The duplicate field is not added

## Test 3: Sub-Field on Relational Fields

**Steps:**

1. Create a new matching rule for model `Contact` (res.partner)
2. In the **Fields** list, add a relational field (e.g., `Parent` which is a Many2one)
3. Verify that the **Sub-Field** column becomes editable and required
4. Select a sub-field (e.g., `Name`)
5. Save the rule

**Expected:**

- The field's computed name displays as `parent_id/name` (field/sub-field format)
- The rule saves without error

## Test 4: Model Change Clears Fields

**Steps:**

1. Open the matching rule created in Test 3
2. Change the **Model** to a different model (e.g., `Country`)
3. Observe the **Fields** list

**Expected:**

- All previously configured fields are cleared from the list
- The field domain updates to show only fields from the newly selected model

## Test 5: Import with Matching — Skip Duplicates

**Steps:**

1. Create a matching rule for `Contact` with the `Name` field and **Overwrite Match** unchecked
2. Create a contact manually with Name = "Test Import Match"
3. Navigate to **Contacts** and click **Import records** (or use the gear/action menu)
4. Upload a CSV file containing:
   ```
   name,email
   Test Import Match,updated@example.com
   Brand New Contact,new@example.com
   ```
5. In the import sidebar, locate the **Import Matching** section
6. Select the matching rule you created from the dropdown
7. Verify the **Overwrite Match** checkbox is unchecked
8. Verify the helper text reads: "Matched records will be skipped."
9. Click **Test** (dry run)

**Expected:**

- An info message appears: "1 to skip, 1 to create"
- No records are modified yet

10. Click **Import**

**Expected:**

- A success notification appears: "1 skipped, 1 created"
- The existing "Test Import Match" contact retains its original email (not updated)
- A new "Brand New Contact" record is created with email `new@example.com`

## Test 6: Import with Matching — Overwrite

**Steps:**

1. Using the same matching rule from Test 5, re-import the same CSV
2. In the import sidebar, select the matching rule
3. Check the **Overwrite Match** checkbox
4. Verify the helper text changes to: "Matched records will be overwritten with imported data."
5. Click **Test** (dry run)

**Expected:**

- An info message appears showing counts for records to overwrite and to create

6. Click **Import**

**Expected:**

- A success notification with overwrite/create counts
- The "Test Import Match" contact now has email `updated@example.com`
- The "Brand New Contact" record either has a second copy created or is matched (depending on whether a Name rule matched it from the previous import)

## Test 7: Conditional Matching

**Steps:**

1. Create a new matching rule for `Contact` with **Overwrite Match** checked
2. Add the `Name` field to the match fields
3. Check **Is Conditional** on the Name field
4. Set **Imported Value** to "Test Import Match"
5. Save the rule
6. Import a CSV:
   ```
   name,email
   Test Import Match,conditional@example.com
   Some Other Name,other@example.com
   ```
7. Select this matching rule in the import sidebar

**Expected:**

- The row with name "Test Import Match" matches the condition and the existing record is overwritten
- The row with name "Some Other Name" does not match the condition (imported value differs from "Test Import Match"), so the entire rule is skipped for that row and a new record is created

## Test 8: Import Matching Dropdown Visibility

**Steps:**

1. Navigate to a model that has NO matching rules configured (e.g., `Countries`)
2. Open the import dialog

**Expected:**

- The **Import Matching** section does not appear in the sidebar (the dropdown is hidden when no rules exist for the model)

3. Navigate to a model that HAS matching rules (e.g., `Contacts`)
4. Open the import dialog

**Expected:**

- The **Import Matching** section appears with a dropdown listing all rules for that model
- The default selection is "-- No Matching --"
- The **Overwrite Match** checkbox is hidden until a rule is selected

## Test 9: Overwrite Match Default from Rule

**Steps:**

1. Create a matching rule with **Overwrite Match** checked on the rule form
2. Open the import dialog for the rule's model
3. Select this rule from the **Import Matching** dropdown

**Expected:**

- The **Overwrite Match** checkbox is automatically checked (inherits the rule's default)
- The user can uncheck it to override the default for this import

4. Select "-- No Matching --" from the dropdown

**Expected:**

- The **Overwrite Match** checkbox disappears

## Test 10: Asynchronous Import (Large File)

**Steps:**

1. Create a matching rule for `Contact` with the `Name` field
2. Prepare a CSV with more than 100 rows of contact data (101+ rows of data, not counting the header)
3. Open the import dialog and upload the CSV
4. Select the matching rule
5. Click **Import** (not Test)

**Expected:**

- A notification appears: "Successfully added on Queue"
- The browser navigates back to the previous page
- The import is processed in the background via job worker
- Check job status by navigating to **Settings > Technical > Queue Jobs > Jobs** (requires technical user access)

## Test 11: Multiple Matches Error

**Steps:**

1. Create two contacts with the same email: `duplicate@example.com`
2. Create a matching rule for `Contact` using the `Email` field
3. Import a CSV:
   ```
   email,name
   duplicate@example.com,Updated Name
   ```
4. Select the matching rule and click **Import**

**Expected:**

- An error is raised: "Multiple matches found for '...'" (where '...' is the name of the first matched record)
- No records are modified

## Test 12: Security — Non-Admin Access

**Steps:**

1. Log in as a user without the **SPP Admin** role
2. Try to navigate to **Registry > Configuration > Import Match**

**Expected:**

- The **Import Match** menu item is not visible
- The user cannot access the matching rule configuration

3. Open the import dialog for any model

**Expected:**

- The **Import Matching** section does not appear (the `searchRead` on `spp.import.match` returns no results due to access rules)
