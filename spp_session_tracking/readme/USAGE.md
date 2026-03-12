# UI Testing Guide: Session Tracking Module

This guide covers all testable areas of the `spp_session_tracking` module. It is organized by
functional area, with step-by-step instructions and expected results.

## Prerequisites

- Module `spp_session_tracking` is installed
- Two test users are available:
  - **Session User** (group: `Session Tracking / User`)
  - **Session Manager** (group: `Session Tracking / Manager`)
- Admin account is available for setup steps
- At least two contacts (res.partner) exist for use as participants

## 1. Module Installation and Demo Data

### 1.1 Verify Installation

1. Log in as admin
2. Go to **Apps**, search for "Session Tracking"
3. Confirm the module is installed

**Expected**: Module appears as installed.

### 1.2 Verify Pre-configured Session Types

1. Navigate to **Session Tracking > Configuration > Session Types**
2. Verify 4 session types exist:

| Name                        | Code     | Frequency | Duration | Attendance % | Topics? |
|-----------------------------|----------|-----------|----------|--------------|---------|
| Training Session            | TRAINING | Monthly   | 3.0h     | 80%          | Yes     |
| Group Meeting               | MEETING  | Bi-weekly | 2.0h     | 75%          | No      |
| Family Development Session  | FDS      | Monthly   | 2.5h     | 85%          | Yes     |
| Workshop                    | WORKSHOP | One-time  | 4.0h     | 90%          | Yes     |

**Expected**: All 4 types are present with the values above.

### 1.3 Verify Pre-configured Topics

1. Open the **Family Development Session** type
2. Check the Topics section (visible because Track Topics is enabled)

**Expected**: 4 topics exist: Nutrition and Health, Education and Child Development, Financial
Literacy, Positive Parenting.

3. Open the **Training Session** type

**Expected**: 2 topics exist: Livelihood Skills, Basic Business Management.

4. Open the **Group Meeting** type

**Expected**: No Topics section is visible (Track Topics is disabled).

---

## 2. Menu Structure and Navigation

### 2.1 Main Menu

1. Log in as Session Manager
2. Check the main menu bar

**Expected**: "Session Tracking" menu item is visible with the module icon.

### 2.2 Submenu Structure

1. Click **Session Tracking**

**Expected**: Two submenu groups are visible:
- **Sessions**: All Sessions, My Sessions
- **Configuration**: Session Types

### 2.3 Configuration Menu Visibility

1. Log in as **Session User**
2. Navigate to Session Tracking

**Expected**: The "Configuration" submenu is NOT visible. Only "Sessions" submenu is shown.

3. Log in as **Session Manager**

**Expected**: Both "Sessions" and "Configuration" submenus are visible.

---

## 3. Session Type Management (Manager Only)

### 3.1 Create a Session Type

1. Log in as Session Manager
2. Go to **Session Tracking > Configuration > Session Types**
3. Click **New**
4. Fill in:
   - Name: "Health Workshop"
   - Code: "HEALTH"
   - Frequency: Quarterly
   - Duration: 1.5
   - Required Attendance %: 70
   - Track Topics: enabled
5. Save

**Expected**: Session type is created. Topics section appears below.

### 3.2 Add Topics to a Session Type

1. Open the "Health Workshop" type created above
2. In the Topics section, click **Add a line**
3. Add topics: "Hygiene Practices", "First Aid Basics"
4. Save

**Expected**: Topics are saved and listed under the session type.

### 3.3 Unique Code Constraint

1. Go to **Session Tracking > Configuration > Session Types**
2. Click **New**
3. Enter Name: "Duplicate Code Test", Code: "HEALTH" (same as above)
4. Save

**Expected**: Error message: "Session type code must be unique."

### 3.4 Archive a Session Type

1. Open an existing session type
2. Use **Action > Archive**
3. Go to the list view and remove the "Active" filter

**Expected**: The archived type shows as inactive (greyed out in list view with muted decoration).

### 3.5 Session Count Stat Button

1. Open a session type that has sessions (e.g., create a session first)
2. Check the "Sessions" stat button in the top-right area

**Expected**: The button shows the correct count of sessions for this type.

3. Click the stat button

**Expected**: A filtered list of sessions for this type opens.

### 3.6 Session Type List View

1. Go to **Session Tracking > Configuration > Session Types**

**Expected**: List displays columns: Name, Code, Frequency, Duration, Required Attendance %, Sessions,
Active. Inactive types are greyed out.

### 3.7 User Cannot Create Session Types

1. Log in as **Session User**
2. Try to access **Session Tracking > Configuration > Session Types**

**Expected**: The Configuration menu is not visible. If accessed via URL, an access error is raised.

---

## 4. Session Creation and Form View

### 4.1 Create a Session (Manager)

1. Log in as Session Manager
2. Go to **Session Tracking > Sessions > All Sessions**
3. Click **New**
4. Fill in:
   - Name: "FDS - Barangay San Jose - March 2026"
   - Session Type: Family Development Session
   - Date: today's date
   - Facilitator: (select a user)
   - Co-Facilitators: (select one or more users)
   - Location: "Barangay Hall"
   - Start Time: 09:00
   - End Time: 11:30
   - Max Participants: 25
5. Save

**Expected**:
- Session is created in "Scheduled" state
- Duration shows 2.5 hours (auto-computed)
- Statusbar shows: Scheduled > In Progress > Completed
- "Start" button is visible and highlighted
- "Cancel" button is visible (not highlighted)
- "Complete" button is NOT visible

### 4.2 User Cannot Create a Session

1. Log in as **Session User**
2. Go to **Session Tracking > Sessions > All Sessions**
3. Try to click **New**

**Expected**: An access error is raised. Session users cannot create sessions.

### 4.3 Form View Structure

1. Open any session in form view

**Expected**:
- **Header**: Action buttons (Start/Complete/Cancel based on state) + statusbar
- **Ribbons**: Green "Completed" ribbon on completed sessions, red "Cancelled" ribbon on cancelled
- **Button Box**: "Attended" stat button with user icon (shows attendance count)
- **Title**: Session name in large text
- **Main Info**: Two-column layout
  - Left: Session Type, Date, Location, Area
  - Right: Facilitator, Co-Facilitators, Start Time, End Time, Duration, Max Participants, Company
- **Tabs**: Participants, Attendance, Topics (conditional), Notes
- **Chatter**: Message log and activity tracking at the bottom

### 4.4 Duration Auto-computation

1. Create or edit a session
2. Set Start Time: 09:00, End Time: 12:00

**Expected**: Duration shows 3.0 hours automatically.

3. Clear the End Time

**Expected**: Duration shows 0.0.

### 4.5 Time Validation

1. Create or edit a session
2. Set Start Time: 14:00, End Time: 10:00
3. Save

**Expected**: Validation error: "End time must be after start time."

### 4.6 Topics Tab Visibility

1. Open a session with type "Family Development Session" (track_topics=True)

**Expected**: "Topics" tab is visible. Can select from the FDS topics.

2. Open a session with type "Group Meeting" (track_topics=False)

**Expected**: "Topics" tab is NOT visible.

### 4.7 Participants Tab

1. Open a session and go to the **Participants** tab
2. Click **Add a line**
3. Select contacts as participants

**Expected**: Participants are listed by name in a simple list format.

### 4.8 Attended Stat Button

1. Open a session that has attendance records
2. Click the "Attended" stat button

**Expected**: A popup list opens showing all attendance records for this session.

---

## 5. Session State Workflow

### 5.1 Scheduled to In Progress

1. Open a session in "Scheduled" state
2. Click the **Start** button

**Expected**:
- State changes to "In Progress"
- "Start" button disappears
- "Complete" button appears (highlighted)
- "Cancel" button remains visible
- Statusbar updates to show "In Progress" as current step

### 5.2 In Progress to Completed

1. Open a session in "In Progress" state
2. Click the **Complete** button

**Expected**:
- State changes to "Completed"
- Green "Completed" ribbon appears on the form
- All "Start", "Complete", and "Cancel" buttons disappear
- All fields become read-only (name, type, date, location, participants, attendance, etc.)

### 5.3 Cancel from Scheduled

1. Open a session in "Scheduled" state
2. Click **Cancel**

**Expected**:
- A confirmation dialog appears: "Are you sure you want to cancel this session?"
- Click OK
- State changes to "Cancelled"
- Red "Cancelled" ribbon appears
- All fields become read-only
- All action buttons disappear

### 5.4 Cancel from In Progress

1. Open a session in "In Progress" state
2. Click **Cancel**

**Expected**: Same confirmation and behavior as 5.3.

### 5.5 Invalid Transitions (Negative Tests)

These transitions should NOT be possible via the UI (buttons are hidden), but verify:

1. A "Completed" session has no Start, Complete, or Cancel buttons
2. A "Cancelled" session has no Start, Complete, or Cancel buttons
3. A "Scheduled" session has no Complete button (must Start first)

**Expected**: Buttons are hidden for invalid transitions. The form is fully read-only for Completed
and Cancelled sessions.

### 5.6 Chatter Tracking

1. Perform any state transition on a session

**Expected**: The chatter logs the state change (e.g., "State: Scheduled → In Progress"). Changes to
Name, Session Type, Date, and Facilitator are also tracked.

---

## 6. Attendance Management

### 6.1 Record Attendance

1. Open a session in "Scheduled" or "In Progress" state
2. Go to the **Attendance** tab
3. Click **Add a line** in the attendance list
4. Select a participant
5. Check "Attended" checkbox
6. Optionally set Attendance Time, Excused, Excuse Reason, and Notes
7. Save

**Expected**: Attendance record is created. Row is highlighted green (attended).

### 6.2 Attendance Decorations

1. Create attendance records with different statuses:
   - Participant A: Attended = True
   - Participant B: Attended = False, Excused = True
   - Participant C: Attended = False, Excused = False

**Expected**:
- Participant A row: green (success decoration)
- Participant B row: yellow/orange (warning decoration)
- Participant C row: grey/muted

### 6.3 Attendance Count and Rate

1. Create a session with 4 expected participants
2. Record attendance: 3 attended, 1 did not

**Expected**:
- Attendance Count shows 3 (in the tab and in the stat button)
- Attendance Rate shows 75.0%

### 6.4 Attendance Rate with Zero Expected Participants

1. Create a session with NO expected participants
2. Record one attendance as attended

**Expected**: Attendance Rate shows 0.0% (no expected participants to calculate against).

### 6.5 Duplicate Attendance Prevention

1. Open a session and go to the Attendance tab
2. Add an attendance record for "Participant A"
3. Try to add another attendance record for the same "Participant A"
4. Save

**Expected**: Error: "A participant can only have one attendance record per session."

### 6.6 Attendance Read-only on Completed/Cancelled

1. Open a completed or cancelled session
2. Go to the Attendance tab

**Expected**: The attendance list is read-only. No "Add a line" button is available.

---

## 7. Session Views

### 7.1 List View

1. Go to **Session Tracking > Sessions > All Sessions**

**Expected**:
- Columns: Date, Name, Session Type, Facilitator, Location, Attendance Count, Attendance Rate, State
- Location is visible by default (optional=show)
- Area is hidden by default (optional=hide)
- State shows as a colored badge:
  - Scheduled: blue (info)
  - In Progress: yellow (warning)
  - Completed: green (success)
  - Cancelled: grey (muted)
- Row colors match the state badge colors
- Default sort: Date descending (newest first)

### 7.2 Optional Column Toggles

1. In the list view, click the column selector (gear icon or right-click header)
2. Toggle Location off, Area on

**Expected**: Location column hides, Area column appears. Settings persist within the session.

### 7.3 Calendar View

1. Switch to Calendar view (click the calendar icon in the view switcher)

**Expected**:
- Monthly calendar is displayed
- Sessions appear on their scheduled dates
- Sessions are color-coded by Session Type
- Clicking a date does NOT open a quick-create popup (quick_create is disabled)
- Clicking a session shows: Name, Facilitator, State

### 7.4 Kanban View

1. Switch to Kanban view

**Expected**:
- Cards are grouped by State (Scheduled, In Progress, Completed, Cancelled columns)
- Each card shows: Name (bold), Session Type, Date, Facilitator, Attendance Rate %
- Progress bar at the top of each column shows color-coded distribution
- Quick-create is disabled (no "+" button at top of columns)
- Cards cannot be dragged between columns (state changes via buttons only)

### 7.5 Graph View

1. Switch to Graph view

**Expected**: A bar chart showing Duration Hours grouped by Session Type.

### 7.6 Pivot View

1. Switch to Pivot view

**Expected**: A pivot table with Session Type as rows, Facilitator as columns, and Duration Hours as
the measure.

### 7.7 My Sessions View

1. Go to **Session Tracking > Sessions > My Sessions**

**Expected**: Only sessions where the current user is the facilitator are shown (My Sessions filter
is pre-applied).

---

## 8. Search and Filtering

### 8.1 Quick Search Fields

1. In the search bar, type a session name

**Expected**: Results are filtered by name.

2. Clear and search by session type, facilitator, location, or area

**Expected**: Each field filters correctly.

### 8.2 State Filters

1. Click **Filters** in the search bar
2. Apply "Scheduled" filter

**Expected**: Only scheduled sessions are shown.

3. Test "In Progress", "Completed", and "Cancelled" filters individually

**Expected**: Each filter works correctly.

### 8.3 Ownership Filters

1. Apply "My Sessions" filter

**Expected**: Only sessions where you are the facilitator are shown.

2. Apply "My Co-facilitated Sessions" filter

**Expected**: Only sessions where you are a co-facilitator are shown.

### 8.4 Date Filter

1. Apply "This Month" filter

**Expected**: Only sessions with dates in the current month are shown.

### 8.5 Group By

1. Use **Group By > Session Type**

**Expected**: Sessions are grouped by their session type with counts.

2. Test Group By: Facilitator, State, and Date

**Expected**: Each grouping works correctly.

### 8.6 Combined Filters

1. Apply "Scheduled" filter AND "My Sessions" filter together

**Expected**: Only your scheduled sessions are shown. Filters combine with AND logic.

---

## 9. Security and Access Control

### 9.1 Session User - Read All Sessions

1. Log in as **Session User**
2. Go to **Session Tracking > Sessions > All Sessions**

**Expected**: All sessions are visible (including ones facilitated by others), regardless of
facilitator.

### 9.2 Session User - Edit Own Facilitated Session

1. Log in as **Session User**
2. Open a session where you are the **facilitator**
3. Edit the Location field and save

**Expected**: Save succeeds. You can edit sessions you facilitate.

### 9.3 Session User - Edit Co-facilitated Session

1. Log in as **Session User**
2. Open a session where you are a **co-facilitator** (but not the main facilitator)
3. Edit the Location field and save

**Expected**: Save succeeds. You can edit sessions you co-facilitate.

### 9.4 Session User - Cannot Edit Another's Session

1. Log in as **Session User**
2. Open a session where you are NOT the facilitator or co-facilitator
3. Try to edit the Location field and save

**Expected**: Access error is raised. You cannot modify sessions you don't facilitate.

### 9.5 Session User - Cannot Create Sessions

1. Log in as **Session User**
2. Try to create a new session

**Expected**: Access error. Only managers can create sessions.

### 9.6 Session User - Cannot Delete Sessions

1. Log in as **Session User**
2. Open a session you facilitate
3. Try to delete it (Action > Delete)

**Expected**: Access error. Users cannot delete sessions.

### 9.7 Session User - Attendance on Own Sessions

1. Log in as **Session User**
2. Open a session you facilitate
3. Go to the Attendance tab and add an attendance record

**Expected**: Attendance record is created successfully.

### 9.8 Session User - Cannot Add Attendance on Others' Sessions

1. Log in as **Session User**
2. Open a session you do NOT facilitate or co-facilitate
3. Try to add an attendance record

**Expected**: Access error. You cannot create attendance on sessions you don't facilitate.

### 9.9 Session User - Cannot Delete Attendance

1. Log in as **Session User**
2. Open a session with attendance records
3. Try to delete an attendance record

**Expected**: Access error. Users cannot delete attendance records.

### 9.10 Session Manager - Full Access

1. Log in as **Session Manager**
2. Create, read, update, and delete sessions, session types, topics, and attendance

**Expected**: All operations succeed. Managers have full CRUD on everything.

### 9.11 Admin Inherits Manager

1. Log in as **OpenSPP Admin** (spp_security.group_spp_admin)
2. Verify you can access all Session Tracking features

**Expected**: Admin has full access (manager group is implied by admin).

### 9.12 Multi-Company Isolation

*Requires multi-company setup with at least 2 companies.*

1. Log in as a user belonging to Company A only
2. Go to All Sessions

**Expected**: Only sessions belonging to Company A (or no company) are visible. Sessions belonging to
Company B are NOT visible.

---

## 10. Data Integrity Constraints

### 10.1 Delete Session Type with Existing Sessions

1. Create a session using a specific session type
2. Try to delete that session type

**Expected**: Error preventing deletion: the session type cannot be deleted while sessions reference
it (ondelete=restrict).

### 10.2 Delete Participant with Attendance Records

1. Create an attendance record for a participant
2. Try to delete that participant (contact) from the system

**Expected**: Error preventing deletion: the participant cannot be deleted while attendance records
reference them (ondelete=restrict).

### 10.3 Delete Facilitator with Sessions

1. Create a session with a specific facilitator
2. Try to delete that user from the system

**Expected**: Error preventing deletion (ondelete=restrict).

---

## 11. Cross-module Integration (spp_case_session)

*Only applicable if `spp_case_session` module is also installed.*

### 11.1 Case Stat Button on Session Form

1. Open any session in form view
2. Check the button box area

**Expected**: If spp_case_session is installed, a "Cases" stat button appears alongside the
"Attended" stat button, inside the same button box. There should NOT be duplicate button boxes.

---

## 12. Edge Cases

### 12.1 Session with No Times

1. Create a session without setting Start Time or End Time

**Expected**: Duration shows 0.0. No validation error.

### 12.2 Session with Only Start Time

1. Create a session with Start Time = 09:00 but no End Time

**Expected**: Duration shows 0.0. No validation error.

### 12.3 Session with Only End Time

1. Create a session with End Time = 12:00 but no Start Time

**Expected**: Duration shows 0.0. No validation error.

### 12.4 Empty Session (No Participants, No Attendance)

1. Create a session with no expected participants and no attendance

**Expected**: Attendance Count = 0, Attendance Rate = 0.0%. Session functions normally.

### 12.5 Session Type Code Left Blank

1. Create two session types with Code left blank

**Expected**: Both are created successfully. The unique constraint allows multiple blank codes.

---

## Test Summary Checklist

Use this checklist to track testing progress:

- [ ] 1. Module installation and demo data (1.1 - 1.3)
- [ ] 2. Menu structure and navigation (2.1 - 2.3)
- [ ] 3. Session type management (3.1 - 3.7)
- [ ] 4. Session creation and form view (4.1 - 4.8)
- [ ] 5. Session state workflow (5.1 - 5.6)
- [ ] 6. Attendance management (6.1 - 6.6)
- [ ] 7. Session views (7.1 - 7.7)
- [ ] 8. Search and filtering (8.1 - 8.6)
- [ ] 9. Security and access control (9.1 - 9.12)
- [ ] 10. Data integrity constraints (10.1 - 10.3)
- [ ] 11. Cross-module integration (11.1)
- [ ] 12. Edge cases (12.1 - 12.5)
