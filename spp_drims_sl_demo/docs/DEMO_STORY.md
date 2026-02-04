# DRIMS Sri Lanka Demo Story

## Executive Summary

This demo showcases a **Disaster Response Inventory Management System (DRIMS)** for Sri
Lanka, demonstrating how government agencies can manage relief goods during disasters
with full traceability from donor to beneficiary.

**Demo Duration:** 20-30 minutes **Target Audience:** DMC leadership,
provincial/district coordinators, warehouse managers

---

## Demo Users

The demo module creates role-specific users to showcase access control. You can use
**admin** for all steps if you want a simplified demo, or switch users to show
role-based access.

| Login       | Password              | Role            | Use For                                  |
| ----------- | --------------------- | --------------- | ---------------------------------------- |
| `admin`     | (your admin password) | System Admin    | All steps (simplified demo)              |
| `silva`     | `demo`                | Manager         | Full access, dispatches, configuration   |
| `perera`    | `demo`                | Warehouse Staff | Receiving donations, inventory           |
| `kumari`    | `demo`                | Field Officer   | Creating requests, confirming deliveries |
| `rajitha`   | `demo`                | Approver        | Approving/rejecting requests             |
| `fernando`  | `demo`                | Coordinator     | District-level coordination              |
| `secretary` | `demo`                | Viewer          | Dashboard and reports only               |

**Tip:** For a realistic multi-role demo, open separate browser windows/incognito tabs
for each user.

---

## The Story: 2025 Southwest Monsoon Floods

### Setting the Scene

_"It's late May 2025. Heavy monsoon rains have caused severe flooding in the Western and
Southern provinces. Colombo, Gampaha, and Galle districts are heavily affected. Over
50,000 families need immediate assistance."_

The Disaster Management Centre (DMC) activates DRIMS to coordinate the response.

---

## Demo Flow

### Act 1: Dashboard Overview (5 min)

**User:** `admin`, `silva` (Manager), or `secretary` (Viewer)

**Goal:** Show leadership decision-making view

1. **Navigate to:** DRIMS → Dashboard
2. **Show the Kanban view** with incident cards displaying:
   - Active incidents with status badges
   - Real-time KPIs: donations received, requests pending
   - Stock value, distributed value
3. **Click on "2025 Southwest Monsoon Floods"** incident
4. **Highlight the button box** showing:
   - Total donations received
   - Total donation value
   - Request count / pending requests
   - Current stock value

**Talking Points:**

- _"At a glance, leadership can see which disasters are active and their resource
  status"_
- _"The pending request count alerts us to bottlenecks in the approval workflow"_

---

### Act 2: Receiving a Donation (7 min)

**User:** `admin`, `silva` (Manager), or `perera` (Warehouse Staff)

**Goal:** Show donation workflow from announcement to stock

**Scenario:** _"UNICEF has announced a donation of 1,000 hygiene kits and 500 family
tents for flood victims."_

1. **Navigate to:** DRIMS → Operations → Donations
2. **Create new donation:**
   - Donor: UNICEF
   - Donor Type: UN Agency
   - Incident: 2025 Southwest Monsoon Floods
   - Warehouse: Colombo Regional Warehouse
   - Expected arrival: Tomorrow

3. **Add donation lines:**
   - Hygiene Kit (Family): 1,000 units @ LKR 2,000 each
   - Family Tent (4-6 persons): 500 units @ LKR 35,000 each

4. **Walk through state transitions:**
   - **Announced** → Show the pending donation
   - **Mark Received** → Creates stock picking automatically
   - **Mark Inspected** → Quality check step (button now available)
   - **Stock Items** → Items appear in warehouse inventory
   - _(Optional)_ Show **Reject** button for damaged goods
   - _(Optional)_ Show **Cancel** button for cancelled donations

5. **Show the generated stock picking** with lot numbers

**Talking Points:**

- _"Every donation is tracked from announcement to warehouse receipt"_
- _"Lot tracking enables expiry management for perishable items"_
- _"The system automatically creates inventory movements"_

---

### Act 3: Field Request Workflow (7 min)

**User:**

- Steps 1-4 (Create & Submit): `kumari` (Field Officer) or `admin`
- Steps 5-6 (Approve & Allocate): `rajitha` (Approver) or `silva` (Manager) or `admin`

**Goal:** Show request submission and approval process

**Scenario:** _"The Galle District Disaster Management office needs urgent supplies for
3 newly established welfare centres housing 500 families."_

1. **Navigate to:** DRIMS → Operations → Requests
2. **Create new request:**
   - Incident: 2025 Southwest Monsoon Floods
   - Destination: Galle District
   - Priority: **High**
   - Date Needed: Tomorrow
   - Affected Population: 500 families
   - Life Threatening: No (checkbox)
   - Justification: "Three welfare centres established in Hikkaduwa, Ambalangoda, and
     Karandeniya with 500 displaced families requiring immediate assistance"

3. **Add request lines:**
   - Rice (25kg sack): 200 units
   - Bottled Water (1.5L): 1,000 units
   - Sleeping Mat: 500 units
   - Family Tent: 50 units

4. **Submit for approval** → Status changes to "Pending"

5. **Switch to Approver view:**
   - Navigate to: DRIMS → Operations → Pending Approval
   - Review the request
   - **Approve** (can also reject or request revision)

6. **Allocate stock:**
   - Select **Source Warehouse** (field now visible after approval)
   - Click **"Allocate Stock"** button → Opens allocation preview wizard
   - Review stock availability per product in the wizard
   - System uses FIFO allocation (oldest stock first by receipt date)
   - Confirm allocation → Request state changes to "Allocated"

**Talking Points:**

- _"Field officers submit requests through the system - no phone calls or paper forms"_
- _"Multi-level approval ensures accountability"_
- _"The allocation wizard shows exactly what stock will be used before committing"_
- _"FIFO allocation ensures oldest stock is used first"_

---

### Act 4: Dispatch and Delivery (5 min)

**User:** `admin`, `silva` (Manager), or `perera` (Warehouse Staff)

**Goal:** Show logistics tracking and waybill generation

1. **From the allocated request**, click **"Create Dispatch"** button
   - This creates a stock picking linked to the request
   - Opens the dispatch form automatically
2. **Fill dispatch details:**
   - Transport Mode: Road
   - Vehicle Registration: WP-CAB-1234
   - Driver Name: K. Perera
   - Driver Phone: +94 77 123 4567

3. **Generate Waybill Report:**
   - Show the PDF with:
     - Unique waybill number
     - Item list with lot numbers
     - Signature blocks (dispatch, transport, receive)
     - Barcode for scanning

4. **Mark as Delivered** (simulating field confirmation)

**Talking Points:**

- _"Every dispatch has a waybill for chain of custody"_
- _"The driver can confirm delivery, completing the audit trail"_

---

### Act 5: Alert Management (3 min)

**User:** `admin`, `silva` (Manager), or `fernando` (Coordinator)

**Goal:** Show proactive monitoring capabilities

1. **Navigate to:** DRIMS → Operations → Alerts
2. **Show different alert types:**
   - **Low Stock Alert** - Rice below 50% of pending requests
   - **Expiry Alert** - Medicine expiring in 14 days
   - **SLA Warning** - Request deadline approaching
   - **SLA Breach** - Overdue request

3. **Demonstrate alert actions:**
   - Acknowledge (assigns ownership)
   - Resolve (with notes)

**Talking Points:**

- _"The system proactively monitors for issues"_
- _"Leadership is alerted to problems before they become crises"_
- _"Every alert creates an audit trail"_

---

### Act 6: Reporting (3 min)

**User:** `admin`, `silva` (Manager), `fernando` (Coordinator), or `secretary` (Viewer)

**Goal:** Show data availability for decision-making

1. **From Dashboard**, show KPI totals:
   - Total stock value across all warehouses
   - Total distributed value
   - Pending vs completed requests

2. **Export capabilities:**
   - List views can export to Excel/CSV
   - Waybill reports as PDF

**Talking Points:**

- _"Real-time data for situation reports"_
- _"Full audit trail for donor accountability"_

---

### Optional: Advanced Features (if time permits)

#### Returns Management

**User:** `admin`, `silva` (Manager), or `perera` (Warehouse Staff)

1. **Navigate to:** DRIMS → Operations → Returns
2. **Show how to create a return from a dispatch:**
   - Open a completed dispatch
   - Click "Create Return" → Opens wizard
   - Select items and quantities being returned
   - Set condition for each item (good, damaged, unusable)
3. **Process the return:**
   - Confirm → Receive → Inspect → Restock
   - Items in good condition go back to inventory

**Talking Point:** _"Non-consumables like tents and generators can be recovered and
reused"_

#### Stock Adjustments

**User:** `admin`, `silva` (Manager), or `perera` (Warehouse Staff)

1. **Navigate to:** DRIMS → Inventory → Stock On Hand
2. **Use action:** "Adjust Stock" (or from warehouse form)
3. **Show adjustment wizard:**
   - Select incident and warehouse
   - Choose reason (damage, loss, theft, expired)
   - Enter quantities and notes

**Talking Point:** _"Every stock adjustment is tracked with reason and audit trail"_

#### Inter-Warehouse Transfers

**User:** `admin`, `silva` (Manager), or `perera` (Warehouse Staff)

1. **Navigate to:** From any warehouse form
2. **Click:** "Transfer Stock"
3. **Show transfer wizard:**
   - Select destination warehouse
   - Choose products and quantities
   - Creates internal transfer picking

**Talking Point:** _"Stock can be redistributed between warehouses as needs change"_

---

## Demo Checklist

Before the demo:

- [ ] Run demo generator in "standard" mode (2 incidents, balanced data)
- [ ] Verify at least one incident has donations in various states
- [ ] Verify at least one incident has requests in various states (including allocated)
- [ ] Check that alerts exist (or trigger cron jobs manually)
- [ ] Verify at least one return exists for demo
- [ ] Prepare user accounts: Admin, Approver, Field Officer

During the demo:

- [ ] Start with Dashboard overview
- [ ] Create one donation live → walk through to "Stocked"
- [ ] Create one request live → approve → allocate → create dispatch
- [ ] Generate a waybill
- [ ] Show alerts (acknowledge and resolve one)
- [ ] _(Optional)_ Show returns, stock adjustment, or transfer
- [ ] End with KPI summary

---

## Key Messages

### For DMC Leadership:

- Real-time visibility across all disasters and warehouses
- Accountability through approval workflows and audit trails
- Proactive alerting prevents stockouts and waste

### For Warehouse Managers:

- Streamlined receiving with automatic inventory updates
- Lot tracking and FEFO allocation
- Professional waybill documentation

### For Field Officers:

- Easy request submission from any device
- Clear status tracking
- Faster response through digital workflows

### For Donors:

- Full traceability from donation to distribution
- Professional reporting for accountability
- Visibility into how contributions are used

---

## Frequently Asked Questions

**Q: Can field officers use this on mobile?** A: The system is web-based with responsive
design. Full mobile app is Phase 2.

**Q: How do we handle offline scenarios?** A: Current version requires connectivity.
Offline capability planned for Phase 2.

**Q: Can we track distribution to individual beneficiaries?** A: Current version tracks
distribution to areas/welfare centres. Individual beneficiary registration integrates
with OpenSPP's registry module.

**Q: How do we handle returns of non-consumable items?** A: Use DRIMS → Operations →
Returns. You can create a return directly from any completed dispatch using the "Create
Return" wizard. The system tracks item conditions (good, damaged, unusable) and
automatically restocks items based on their disposition.

**Q: Can multiple disasters be managed simultaneously?** A: Yes, each incident is
tracked separately with its own inventory and requests.
