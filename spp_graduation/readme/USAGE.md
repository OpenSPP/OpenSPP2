## UI Testing Guide

Manual QA test plan for the Graduation Management module. Tests are organized by feature area and should be
executed in order since later tests depend on data created in earlier ones.

### Prerequisites

- Install `spp_graduation` module
- Two test users configured:
  - **QA User**: assigned to Graduation > User privilege
  - **QA Manager**: assigned to Graduation > Manager privilege
- At least one `res.partner` record to use as a beneficiary

After installation, three default pathways exist: Standard Graduation, Early Graduation, and Administrative Exit.

---

### Test 1: Pathway Configuration (as QA Manager)

**Menu**: Graduation > Configuration > Pathways

#### 1.1 Verify pre-installed pathways

1. Open **Graduation > Configuration > Pathways**
2. Verify three pathways exist in the list:
   - Standard Graduation (code: STANDARD, positive exit, 12 months monitoring)
   - Early Graduation (code: EARLY, positive exit, 18 months monitoring)
   - Administrative Exit (code: ADMIN_EXIT, negative exit, 0 months monitoring)
3. Verify the **Criteria** column shows a count for each pathway (5 for Standard, 2 for Early, 0 for Admin Exit)
4. Verify optional columns can be toggled: Code, Is Assessment Required, Is Approval Required, Post Graduation
   Monitoring Months

#### 1.2 Search and filter pathways

1. Use the search bar to search by name (e.g., "Standard")
2. Apply the **Positive Exit** filter — only Standard and Early should appear
3. Apply the **Negative Exit** filter — only Administrative Exit should appear
4. Apply the **Archived** filter — should show no results (none are archived)

#### 1.3 Create a new pathway

1. Click **New**
2. Fill in:
   - Name: "Test Graduation Pathway"
   - Code: "TEST_QA"
   - Is Positive Exit: ON (toggle)
   - Is Assessment Required: ON (toggle)
   - Is Approval Required: ON (toggle)
   - Post Graduation Monitoring Months: 6
   - Description: "QA test pathway"
3. Open the **Criteria** tab
4. Click **Add a line** and create two criteria:
   - Name: "Income Criterion", Weight: 2.0, Assessment Method: Verification Required, Is Required: checked
   - Name: "Education Criterion", Weight: 1.0, Assessment Method: Self Report, Is Required: unchecked
5. Save
6. Verify the **Criteria** count in the list view shows 2

#### 1.4 Verify weight constraint

1. Open the Test Graduation Pathway
2. In the Criteria tab, try to add a criterion with **Weight: 0**
3. **Expected**: Validation error "Weight must be greater than zero"
4. Try **Weight: -1**
5. **Expected**: Same validation error

#### 1.5 Archive and unarchive

1. Open any pathway, click **Action > Archive**
2. Verify the red "Archived" ribbon appears
3. Go back to the list, apply the **Archived** filter, verify the pathway appears
4. Open it and click **Action > Unarchive**

#### 1.6 Drag to reorder

1. In the list view, drag the handle (≡) on a pathway row to reorder
2. Verify the sequence updates

---

### Test 2: Assessment Creation and Form Layout (as QA User)

**Menu**: Graduation > Assessments > All Assessments

#### 2.1 List view

1. Open **Graduation > Assessments > All Assessments**
2. Verify the list is empty (or shows existing assessments)
3. Verify columns: Name, Beneficiary, Pathway, Assessment Date, Assessor (with avatar), Readiness Score, Required
   Criteria Met, Recommendation, State (badge)
4. Verify optional columns can be toggled via the column selector icon

#### 2.2 Create an assessment

1. Click **New**
2. Verify the form opens with:
   - State: **Draft** in the statusbar
   - **Submit** button visible in the header
   - No Approve/Reject/Reset to Draft buttons (user is not a manager)
   - Title shows "New Assessment"
3. On the **Overview** tab, fill in:
   - Beneficiary: select a partner record
   - Pathway: select "Test Graduation Pathway" (created in Test 1.3)
   - Assessment Date: today (should be pre-filled)
   - Assessor: current user (should be pre-filled)
4. Verify the title updates to "{Beneficiary Name} - Test Graduation Pathway"
5. Verify the right column shows:
   - Readiness Score: 0%
   - Required Criteria Met: OFF
   - Graduation Date: empty
   - Monitoring End Date: empty
6. Save the record

#### 2.3 Add criteria responses

**Important — understanding `score` vs `is_met`**: These two fields serve different purposes and are set
independently by the assessor:

- **Score** (0–1): A numeric rating that feeds into the weighted **Readiness Score** calculation. For example,
  0.8 means the beneficiary scored 80% on this criterion.
- **Is Met** (toggle): A qualitative yes/no judgment by the assessor indicating whether the criterion is
  satisfied. This is used only to check the **Required Criteria Met** flag — if a criterion is marked as
  "required" on the pathway, its `is_met` must be ON for the overall check to pass.

These fields are intentionally independent because some assessment methods (e.g., field observation) may not map
cleanly to a numeric score. An assessor might give a low numeric score but still consider the criterion met based
on qualitative judgment, or vice versa.

1. Open the **Criteria Responses** tab
2. Click **Add a line**
3. Add a response for "Income Criterion":
   - Score: 0.8
   - Is Met: ON (toggle) — assessor judges this criterion is satisfied
   - Value: "Above threshold"
   - Notes: "Verified via documentation"
4. Add a response for "Education Criterion":
   - Score: 0.6
   - Is Met: OFF — assessor judges this criterion is not yet satisfied
   - Value: "Partial"
5. Save
6. Go back to the **Overview** tab and verify:
   - Readiness Score is computed (should be around 73% based on weights 2.0 and 1.0)
   - Required Criteria Met: ON (because Income Criterion is required and is_met = True)

#### 2.3a Verify score and is_met independence

1. Change the Income Criterion response to Score: 0.3, Is Met: ON
2. Save and verify:
   - Readiness Score drops (lower numeric score)
   - Required Criteria Met stays ON (because is_met is still toggled on)
3. Change it to Score: 1.0, Is Met: OFF
4. Save and verify:
   - Readiness Score increases (higher numeric score)
   - Required Criteria Met changes to OFF (because is_met is toggled off on a required criterion)
5. Restore to Score: 0.8, Is Met: ON for subsequent tests

#### 2.4 Evidence attachments

1. Go to the **Criteria Responses** tab
2. On the Income Criterion response row, click the attachment icon in the Evidence Attachments column
3. Upload a test file (e.g., a small PDF or image)
4. Verify the file appears attached
5. Click on the response row to open the popup form
6. Verify the popup shows: Criteria (readonly), Score, Is Met, Value, Notes, and an Evidence section with the
   uploaded file

#### 2.5 Score constraint

1. In the Criteria Responses tab, try to change a score to **1.5**
2. **Expected**: Validation error "Score must be between 0 and 1"
3. Try **-0.1**
4. **Expected**: Same validation error
5. Try **0** and **1** — both should be accepted

#### 2.6 Recommendation tab

1. Open the **Recommendation** tab
2. Select a recommendation: "Ready to Graduate"
3. Enter recommendation notes: "Beneficiary meets all criteria"
4. Save

---

### Test 3: Approval Workflow

#### 3.1 Submit (as QA User)

1. Open the assessment created in Test 2
2. Click the **Submit** button
3. Verify:
   - State changes to **Submitted**
   - Submit button disappears
   - A yellow **Pending Review** alert banner appears: "This assessment is awaiting manager approval."
   - Overview fields (Beneficiary, Pathway, Date, Assessor) are still editable
   - No Approve/Reject buttons visible (user is not a manager)

#### 3.2 Verify double-submit is blocked (as QA User)

1. The assessment is already in Submitted state
2. There should be no Submit button visible
3. (Programmatic check: calling `action_submit()` on a submitted record raises an error)

#### 3.3 Approve (as QA Manager)

1. Log in as QA Manager
2. Open **Graduation > Assessments > All Assessments**
3. Verify the manager can see the submitted assessment (even though another user created it)
4. Open the assessment
5. Verify **Approve** and **Reject** buttons are visible, plus **Reset to Draft**
6. Click **Approve**
7. Verify:
   - State changes to **Approved**
   - All buttons disappear (no further actions on approved records)
   - **Graduation Date** is set to today (because recommendation was "Ready to Graduate")
   - **Monitoring End Date** is set to 6 months from today (pathway has 6 months monitoring)
   - **Approved By** shows the manager's name
   - **Approved Date** shows the current datetime
   - Overview fields (Beneficiary, Pathway, etc.) become readonly
   - Criteria Responses tab becomes readonly
   - Recommendation tab becomes readonly

#### 3.4 Verify reset from approved is blocked

1. On the approved assessment, verify there is no **Reset to Draft** button

---

### Test 4: Rejection and Reset Flow

#### 4.1 Create and submit another assessment (as QA User)

1. Create a new assessment with:
   - Beneficiary: any partner
   - Pathway: "Standard Graduation"
   - Recommendation: "Extend Participation"
2. Submit it

#### 4.2 Reject (as QA Manager)

1. Open the submitted assessment
2. Click **Reject**
3. Verify:
   - State changes to **Rejected**
   - A red **Rejected** alert banner appears: "This assessment was rejected. Review and reset to draft to
     resubmit."
   - **Reset to Draft** button is visible
   - Overview and Criteria Responses fields are readonly

#### 4.3 Reset to draft (as QA Manager)

1. Click **Reset to Draft**
2. Verify:
   - State returns to **Draft**
   - Alert banners disappear
   - **Submit** button reappears
   - Fields become editable again
3. Make changes and re-submit

#### 4.4 Approve non-graduate recommendation

1. Approve the re-submitted assessment (recommendation is "Extend Participation")
2. Verify:
   - State is Approved
   - **Graduation Date is empty** (not set because recommendation is not "Ready to Graduate")
   - **Monitoring End Date is empty**

---

### Test 5: Kanban View

1. Navigate to **Graduation > Assessments > All Assessments**
2. Switch to **Kanban** view
3. Verify:
   - Cards are grouped by state columns: Draft, Submitted, Approved, Rejected
   - A colored progress bar appears at the top of each column
   - Each card shows: Beneficiary name, state badge, pathway, date with calendar icon, readiness score as
     percentage, and recommendation badge (if set)
   - Recommendation badges have colors: green (Graduate), yellow (Extend), red (Exit), blue (Defer)

---

### Test 6: Graph and Pivot Views

#### 6.1 Graph view

1. Switch to **Graph** view (bar chart icon)
2. Verify a bar chart appears grouped by Pathway and State
3. Toggle between bar, line, and pie chart options

#### 6.2 Pivot view

1. Switch to **Pivot** view (grid icon)
2. Verify a pivot table appears with:
   - Rows: Pathway
   - Columns: State
   - Measure: Readiness Score
3. Verify you can add/remove measures and change row/column groupings

---

### Test 7: Search and Filters

1. Navigate to **Graduation > Assessments > All Assessments**
2. Test each filter:
   - **My Assessments**: shows only assessments where you are the assessor
   - **Draft / Submitted / Approved / Rejected**: filters by state
   - **Ready to Graduate**: shows only assessments with "Ready to Graduate" recommendation
   - **Assessment Date**: date range filter
3. Test group-by options:
   - Group by **Pathway**: assessments grouped under pathway names
   - Group by **Assessor**: assessments grouped under assessor names
   - Group by **State**: assessments grouped by state
   - Group by **Recommendation**: assessments grouped by recommendation
   - Group by **Assessment Date**: assessments grouped by date

---

### Test 8: My Assessments

1. Navigate to **Graduation > Assessments > My Assessments**
2. Verify the "My Assessments" filter is active by default
3. Verify only assessments where the current user is the assessor are shown

---

### Test 9: Security / Access Control

#### 9.1 User cannot access configuration

1. Log in as **QA User**
2. Verify the **Graduation > Configuration** menu is NOT visible

#### 9.2 User cannot modify pathways

1. Navigate to a pathway via URL (e.g., `/odoo/spp-graduation-pathway/{id}`)
2. Verify the form is readonly — no edit capability

#### 9.3 User cannot see other users' assessments

1. Log in as QA User
2. Navigate to **Graduation > Assessments > All Assessments**
3. Verify only assessments where QA User is the assessor appear
4. Log in as QA Manager
5. Verify all assessments from all users appear

#### 9.4 User cannot delete assessments

1. Log in as QA User
2. Open an assessment, try to delete it (Action > Delete)
3. **Expected**: Access error — user does not have delete permission on assessments

---

### Test 10: Edge Cases

#### 10.1 Assessment with no responses

1. Create a new assessment, do NOT add any criteria responses
2. Verify: Readiness Score = 0%, Required Criteria Met = OFF
3. Submit and approve it
4. Verify: No graduation date (no recommendation set)

#### 10.2 Pathway with zero monitoring months

1. Create an assessment using "Administrative Exit" pathway (0 months monitoring)
2. Set recommendation to "Ready to Graduate"
3. Submit and approve
4. Verify: Graduation Date = today, Monitoring End Date = empty (0 months means no monitoring)

#### 10.3 Multiple assessments for same beneficiary

1. Create two assessments for the same beneficiary with different pathways
2. Verify both can exist independently and have separate scores/states
