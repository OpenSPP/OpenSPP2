## UI Testing Guide

This module has no views of its own. All UI interaction is through views provided
by `spp_vocabulary` and `spp_cel_domain`. This guide covers what to verify after
installing `spp_cel_vocabulary`.

### Prerequisites

- Install `spp_cel_vocabulary` (auto-installs when both `spp_cel_domain` and
  `spp_vocabulary` are present)
- Log in as an admin user
- Have at least one vocabulary with codes (e.g., a gender vocabulary)

---

### Test 1: Verify Concept Groups Are Created

**Path:** Settings > Vocabularies > Concept Groups

**Steps:**

1. Navigate to **Settings > Vocabularies > Concept Groups**
2. Verify the following 10 groups exist:

| Name                     | Label                    | CEL Function   |
| ------------------------ | ------------------------ | -------------- |
| `feminine_gender`        | Feminine Gender          | `is_female`    |
| `masculine_gender`       | Masculine Gender         | `is_male`      |
| `head_of_household`      | Head of Household        | `is_head`      |
| `pregnant_eligible`      | Pregnant/Eligible        | `is_pregnant`  |
| `climate_hazards`        | Climate-related Hazards  | _(empty)_      |
| `geophysical_hazards`    | Geophysical Hazards      | _(empty)_      |
| `children`               | Children                 | _(empty)_      |
| `adults`                 | Adults                   | _(empty)_      |
| `elderly`                | Elderly/Senior Citizens  | _(empty)_      |
| `persons_with_disability`| Persons with Disability  | _(empty)_      |

3. Open `feminine_gender` and verify:
   - Label: "Feminine Gender"
   - CEL Function: `is_female`
   - Description is populated
   - **Codes** tab is empty (groups are created empty by default)

**Expected:** All 10 groups are present with correct labels, CEL functions, and descriptions.

---

### Test 2: Add Codes to a Concept Group

**Path:** Settings > Vocabularies > Concept Groups > (select group) > Codes tab

**Precondition:** A gender vocabulary with at least a "Female" code must exist.

**Steps:**

1. Open `feminine_gender` concept group
2. Click **Edit**
3. Go to the **Codes** tab
4. Click **Add a line**
5. Search for and select your "Female" vocabulary code
6. Click **Save**

**Verify:**

- The code appears in the Codes tab with its vocabulary, code value, and display name
- If the code has a URI, it should be visible (may need Technical tab for `code_uris` field)

**Repeat** for `masculine_gender` with a "Male" code if available.

---

### Test 3: Idempotent Installation

**Steps:**

1. Note the current concept groups and their IDs
2. Upgrade `spp_cel_vocabulary` module (Settings > Apps > spp_cel_vocabulary > Upgrade)
3. Navigate back to **Settings > Vocabularies > Concept Groups**

**Expected:**

- No duplicate groups were created
- Existing groups retain their codes (codes added in Test 2 are still there)
- All 10 groups still present

---

### Test 4: CEL Expression Validation with Vocabulary Functions

**Path:** Custom > CEL Domain > Tools > Rule Preview

**Precondition:** Codes have been added to `feminine_gender` group (Test 2).

**Steps:**

1. Navigate to **Custom > CEL Domain > Tools > Rule Preview**
2. Select a model (e.g., the individual registrant model)
3. Enter the expression: `is_female(r.gender_id)`
4. Click **Validate & Preview**

**Expected:**

- Validation succeeds (no error)
- The **Summary** tab shows:
  - `preview_count`: number of matching records (may be 0 if no registrants have gender set)
  - `explain_text`: a human-readable explanation mentioning `feminine_gender` and URIs

**Repeat with these expressions:**

| Expression                                        | Should Validate |
| ------------------------------------------------- | --------------- |
| `is_female(r.gender_id)`                          | Yes             |
| `is_male(r.gender_id)`                            | Yes             |
| `in_group(r.gender_id, "feminine_gender")`        | Yes             |
| `code_eq(r.gender_id, "female")`                  | Yes (if code exists) |
| `r.gender_id == code("female")`                   | Yes (if code exists) |
| `members.exists(m, head(m) and is_female(m.gender_id))` | Yes        |
| `in_group(r.gender_id, "nonexistent_group")`      | Yes (validates but matches nothing) |
| `is_female(r.name)`                               | Depends on translator behavior |

---

### Test 5: Domain Translation Verification

**Path:** Custom > CEL Domain > Tools > Rule Preview

**Precondition:** `feminine_gender` group has at least one code with a URI.

**Steps:**

1. Open Rule Preview
2. Enter: `is_female(r.gender_id)`
3. Click **Validate & Preview**
4. Check the **Summary** tab explanation text

**Expected:**

- The explanation should reference `feminine_gender` and list the code URIs
- The generated domain should check both `gender_id.uri` and `gender_id.reference_uri`

---

### Test 6: Empty Group Behavior

**Path:** Custom > CEL Domain > Tools > Rule Preview

**Precondition:** `climate_hazards` group exists but has no codes assigned.

**Steps:**

1. Open Rule Preview
2. Enter: `in_group(r.gender_id, "climate_hazards")`
3. Click **Validate & Preview**

**Expected:**

- Validation succeeds but matches 0 records
- The explanation should indicate the group is empty (e.g., `[EMPTY GROUP]`)
- Check Odoo logs for a `[CEL Vocabulary]` warning about the empty group

---

### Test 7: Nonexistent Group Behavior

**Steps:**

1. Open Rule Preview
2. Enter: `in_group(r.gender_id, "does_not_exist")`
3. Click **Validate & Preview**

**Expected:**

- Validation succeeds but matches 0 records
- The explanation should indicate the group was not found (e.g., `[GROUP NOT FOUND]`)
- Check Odoo logs for a warning with guidance:
  "Check Settings > Vocabularies > Concept Groups"

---

### Test 8: Local Code Support (if applicable)

**Precondition:** A local vocabulary code exists with `is_local = True` and a
`reference_uri` pointing to a standard code's URI. Both codes are in the same
concept group.

**Steps:**

1. Create a local code (e.g., "Babae" with `reference_uri` pointing to the Female
   standard code's URI)
2. Add both the standard and local codes to `feminine_gender` group
3. Open Rule Preview
4. Enter: `is_female(r.gender_id)`
5. Click **Validate & Preview**

**Expected:**

- The domain checks both `uri` and `reference_uri` fields
- Records with either the standard code or the local code should be matched

---

### Test 9: Security - Read-Only Access

**Steps:**

1. Log in as a non-admin user (base user group)
2. Navigate to **Settings > Vocabularies > Concept Groups**

**Expected:**

- User can view concept groups (read access)
- User cannot create, edit, or delete concept groups

---

### Test 10: Concept Group Search and Filters

**Path:** Settings > Vocabularies > Concept Groups

**Steps:**

1. Use the search bar to search for "gender"
2. Apply the "Has CEL Function" filter

**Expected:**

- Search by "gender" finds `feminine_gender` and `masculine_gender`
- "Has CEL Function" filter shows only groups with a CEL function set
  (`feminine_gender`, `masculine_gender`, `head_of_household`, `pregnant_eligible`)

---

### Troubleshooting

If expressions return unexpected results:

1. **Check logs** for `[CEL Vocabulary]` entries — error messages include
   guidance on how to fix the issue
2. **Verify codes are in groups** — open the concept group and check the Codes tab
3. **Verify code URIs** — codes need a `uri` field populated for domain matching
4. **Check field names** — vocabulary functions require Many2one fields pointing to
   `spp.vocabulary.code` (e.g., `gender_id`, not `gender`)
