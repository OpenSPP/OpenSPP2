# DRIMS Review Feedback

**Date:** 2025-01-06 **Reviewer:** Jeremi **Updated:** 2025-01-06

---

## Status Summary

| Status          | Count |
| --------------- | ----- |
| ✅ Fixed        | 9     |
| ❌ Not an Issue | 4     |
| 🔄 Deferred     | 0     |

---

## 1. Demo Data Issues (spp_drims_sl_demo)

| ID       | Issue                    | Status          | Details                                 |
| -------- | ------------------------ | --------------- | --------------------------------------- |
| DEMO-001 | Currency not LKR         | ✅ Fixed        | Enabled LKR and set as company currency |
| DEMO-002 | "Galle District" invalid | ❌ Not an Issue | Galle IS a valid Sri Lanka district     |
| DEMO-003 | Duplicate "Sleeping Mat" | ❌ Not an Issue | Only one exists in demo_products.xml    |
| DEMO-004 | Transport mode "Truck"   | ✅ Fixed        | Changed to "Road" in DEMO_STORY.md      |

---

## 2. Donation Workflow Issues (spp_drims)

| ID      | Issue                    | Status   | Details                                                 |
| ------- | ------------------------ | -------- | ------------------------------------------------------- |
| DON-001 | Wrong form for new donor | ✅ Fixed | Added context for company + DRIMS organization defaults |
| DON-002 | No partial accept/reject | ✅ Fixed | Inspection wizard with line splitting                   |

**DON-001 Fix:**

- File: `spp_drims/views/donation_views.xml`
- Changed `options="{'no_create_edit': True}"` to
  `context="{'default_is_company': True, 'default_is_drims_organization': True}"` with
  `options="{'no_quick_create': True}"`
- Now opens full partner form with proper defaults when creating new donor

---

## 3. Request Form Issues (spp_drims)

| ID      | Issue                       | Status          | Details                                                |
| ------- | --------------------------- | --------------- | ------------------------------------------------------ |
| REQ-001 | Priority field not editable | ❌ Not an Issue | IS editable in draft/revision state (correct behavior) |
| REQ-002 | Justification field cramped | ❌ Not an Issue | Uses full-width group with nolabel - layout is correct |

---

## 4. Dispatch/Delivery Issues (spp_drims)

| ID      | Issue                      | Status   | Details                      |
| ------- | -------------------------- | -------- | ---------------------------- |
| DSP-001 | Beneficiaries field UX     | ✅ Fixed | Renamed + made optional      |
| DSP-002 | Departure/Arrival editable | ✅ Fixed | Made readonly                |
| DSP-003 | Signature blocks too small | ✅ Fixed | Increased from 60px to 120px |

**DSP-001 Fix:**

- File: `spp_drims/models/stock_picking.py`
- Renamed "Beneficiaries Served" → "Estimated Beneficiaries Reached"
- Updated help text to clarify estimates are acceptable
- File: `spp_drims/views/stock_picking_views.xml`
- Removed `required` attribute (now optional)

**DSP-002 Fix:**

- File: `spp_drims/views/stock_picking_views.xml`
- Added `readonly="1"` to `date_departed` and `date_arrived` fields
- Values set via "Confirm Departure" and "Confirm Delivery" buttons

**DSP-003 Fix:**

- File: `spp_drims/report/waybill_template.xml`
- Increased signature block margin-top from 60px to 120px
- Increased padding-top from 5px to 8px

---

## 5. Alert UI Issues (spp_drims)

| ID      | Issue                       | Status   | Details                                      |
| ------- | --------------------------- | -------- | -------------------------------------------- |
| ALT-001 | List view needs improvement | ✅ Fixed | Urgency labels, color badges, age indicators |
| ALT-002 | Alert UI confusing          | ✅ Fixed | Kanban view, improved form, bulk actions     |

**ALT-001/002 Fixes:**

1. ✅ Color-coded badges for alert types (red=critical, yellow=warning, blue=info)
2. ✅ Kanban view grouped by state with drag-and-drop workflow
3. ✅ Age/staleness indicators ("2h ago", "3d ago")
4. ✅ Urgency labels ("Today", "2 days overdue") with color highlighting
5. ✅ Bulk acknowledge/resolve server actions
6. ✅ Calendar view for deadline tracking
7. ✅ Graph and pivot views for analysis
8. ✅ Alert assignment to team members
9. ✅ Search panel filters for urgency and incident
10. ✅ Form urgency banners (red for overdue, yellow for urgent)
11. ✅ Quick navigation buttons in form view

---

## Files Modified

1. `spp_drims_sl_demo/docs/DEMO_STORY.md` - Transport mode fix
2. `spp_drims_sl_demo/data/demo_currency.xml` - LKR currency setup (NEW)
3. `spp_drims/models/stock_picking.py` - Beneficiaries field rename
4. `spp_drims/views/stock_picking_views.xml` - Beneficiaries optional, datetime readonly
5. `spp_drims/report/waybill_template.xml` - Larger signature blocks
6. `spp_drims/views/donation_views.xml` - Donor quick-create, inspection wizard button
7. `spp_drims/wizard/inspection_wizard.py` - Inspection wizard (NEW)
8. `spp_drims/wizard/inspection_wizard_views.xml` - Inspection wizard view (NEW)
9. `spp_drims/models/constants.py` - Added item condition/disposition vocab constants
10. `spp_drims/security/ir.model.access.csv` - Inspection wizard access rights
11. `spp_drims/models/alert.py` - UX enhancement fields (urgency, age, assignment)
12. `spp_drims/views/alert_views.xml` - Complete UI overhaul (kanban, calendar, bulk actions)

---

**DON-002 Fix:**

- Created inspection wizard (`spp.drims.inspection.wizard`)
- Allows splitting donation lines by condition/disposition
- Example: 1000 received → 800 accept (good), 200 reject (damaged)
- Each split creates a new donation line with its own condition/disposition
- Files: `spp_drims/wizard/inspection_wizard.py`, `inspection_wizard_views.xml`

---

**ALT-001/002 Fix:**

- Added computed fields: `urgency_label`, `urgency_state`, `alert_type_color`, `deadline_date`, `age_hours`,
  `age_label`, `assigned_to_id`
- Added Kanban view with visual workflow management (drag between Active/Acknowledged/Resolved)
- Added Calendar view for deadline-based alerts
- Added Graph and Pivot views for analysis
- Enhanced List view with color-coded badges, urgency indicators, age display
- Enhanced Form view with urgency banners, quick navigation buttons
- Added bulk acknowledge/resolve server actions
- Added comprehensive search filters (urgency, assignment, date ranges)
- Added dashboard action with graph/pivot default views

---

## All Items Now Complete ✅
