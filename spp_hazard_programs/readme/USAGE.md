### Prerequisites

Before testing, ensure the following modules are installed:

- `spp_hazard` (provides incidents, impacts, categories)
- `spp_programs` (provides programs)
- `spp_hazard_programs` (auto-installs when both above are present)

You will also need:

- At least one hazard category (e.g., "Typhoon") created at
  **Hazard and Emergency > Configuration > Hazard Categories**
- At least one impact type (e.g., "Property Damage") created at
  **Hazard and Emergency > Configuration > Impact Types**
- At least two registrants with `is_registrant = True`
- At least one incident with impact records linked to those registrants

### Test Scenario 1: Link a Program to Incidents

**Steps:**

1. Navigate to **Programs > Programs**
2. Open an existing program or create a new one
3. Click the **"Emergency Response"** tab in the form notebook
4. In the "Target Incidents" section, confirm the **Is Emergency Program** field
   is read-only and shows `False`
5. In the "Emergency Settings" section, confirm:
   - **Qualifying Damage Levels** defaults to "Any Damage Level"
   - **Emergency Mode** checkbox defaults to unchecked
6. In the inline list below, click "Add a line" to add an incident
7. Select an incident with status **Active**
8. Save the program

**Expected results:**

- The **Is Emergency Program** field changes to `True`
- A yellow **"Emergency Response"** ribbon appears at the top of the form
- An **"Incidents"** stat button (bolt icon) appears in the button box showing "1"
- An **"Affected"** stat button (users icon) appears showing the count of
  registrants with verified impacts from that incident

### Test Scenario 2: Verify Emergency Flag by Incident Status

**Steps:**

1. Link a program to an incident with status **Alert**
2. Save and confirm **Is Emergency Program** is `True`
3. Change the incident status to **Active** -- confirm still `True`
4. Change the incident status to **Recovery** -- confirm still `True`
5. Change the incident status to **Closed** -- confirm **Is Emergency Program**
   becomes `False` (assuming no other linked incidents have alert/active/recovery
   status)

**Expected results:**

- The emergency flag is `True` for alert, active, and recovery statuses
- The emergency flag is `False` for closed status (when no other active incidents
  are linked)
- The yellow ribbon appears/disappears accordingly

### Test Scenario 3: Damage Level Filtering

**Setup:** Ensure the linked incident has verified impact records with different
damage levels (e.g., one "critical", one "moderate", one unverified "severe").

**Steps:**

1. Open a program linked to the incident
2. Go to the **"Emergency Response"** tab
3. Set **Qualifying Damage Levels** to each option and save after each change:

| Setting | Expected "Affected" count |
| --- | --- |
| "Any Damage Level" | All registrants with verified impacts (unverified excluded) |
| "Moderate and Above" | Registrants with moderate, severe, critical, partially damaged, or totally damaged verified impacts |
| "Severe and Above" | Registrants with severe, critical, or totally damaged verified impacts |
| "Critical/Totally Damaged Only" | Registrants with critical or totally damaged verified impacts |

**Expected results:**

- The **"Affected"** stat button count updates after each save
- Unverified impact records are always excluded regardless of damage level

### Test Scenario 4: Stat Button Navigation

**Steps:**

1. Open a program with at least one linked incident and affected registrants
2. Click the **"Incidents"** stat button (bolt icon)
3. Confirm it opens a list view of `spp.hazard.incident` records filtered to
   only the program's target incidents
4. Navigate back to the program
5. Click the **"Affected"** stat button (users icon)
6. Confirm it opens a list view of `res.partner` records filtered to only
   registrants with qualifying verified impacts

**Expected results:**

- Each stat button opens the correct model with the correct filtered records
- The number of records in the opened list matches the stat button count

### Test Scenario 5: Incident Side -- Response Programs

**Steps:**

1. Navigate to **Hazard and Emergency > Incidents > All Incidents**
2. Open an incident that has NO programs linked to it
3. Confirm:
   - No **"Programs"** stat button is visible in the button box
   - No **"Response Programs"** tab is visible in the notebook
4. Now link a program to this incident (from the program side, add this incident
   to a program's target incidents)
5. Reload the incident form

**Expected results:**

- A **"Programs"** stat button (list icon) appears showing "1"
- A **"Response Programs"** tab appears in the notebook
- The tab contains a read-only list showing the linked program's name, state
  (badge), qualifying damage levels, and emergency mode
- Clicking the stat button opens a list view of `spp.program` records filtered
  to the responding programs

### Test Scenario 6: Bidirectional Relationship

**Steps:**

1. Open a program and add Incident A to its target incidents via the
   "Emergency Response" tab
2. Save the program
3. Open Incident A and check the "Response Programs" tab

**Expected results:**

- Incident A's "Response Programs" tab shows the program
- Removing the incident from the program also removes the program from the
  incident's response programs (and vice versa)

### Test Scenario 7: Program List View Columns

**Steps:**

1. Navigate to **Programs > Programs** (list view)
2. Check the column headers

**Expected results:**

- An **"Emergency"** column is visible by default (shows True/False)
- An **"Incidents"** column is available via the optional columns toggle
  (hidden by default)

### Test Scenario 8: Search Filters

**Steps:**

1. Navigate to **Programs > Programs** (list view)
2. Open the search bar's **Filters** dropdown
3. Activate the **"Emergency Programs"** filter
4. Confirm only programs with `is_emergency_program = True` are shown
5. Deactivate that filter and activate **"Has Target Incidents"**
6. Confirm only programs with at least one target incident are shown

**Expected results:**

- Both filters appear in the search dropdown
- Each filter correctly narrows the program list

### Test Scenario 9: Incident List View Column

**Steps:**

1. Navigate to **Hazard and Emergency > Incidents > All Incidents** (list view)
2. Check the column headers

**Expected results:**

- A **"Programs"** column is visible by default showing the count of response
  programs for each incident
