# DRIMS UX Gap Analysis Specification

This document identifies missing views, actions, buttons, and wizards required for complete end-to-end (E2E) operations
in the DRIMS module. Each gap is categorized by severity and includes implementation recommendations.

## Document Info

| Field       | Value                                          |
| ----------- | ---------------------------------------------- |
| Version     | 2.0                                            |
| Date        | 2026-01-02                                     |
| Status      | Implemented                                    |
| Author      | UX Review Team                                 |
| Last Review | 2026-01-02 - All gaps implemented and reviewed |

## Severity Levels

| Level    | Icon            | Description                                                       |
| -------- | --------------- | ----------------------------------------------------------------- |
| Critical | :red_circle:    | Blocks core E2E workflow - users cannot complete basic operations |
| High     | :orange_circle: | Significantly impacts realistic field operations                  |
| Medium   | :yellow_circle: | Operational enhancement for improved efficiency                   |

---

## 1. Donation Lifecycle Gaps

**Current Workflow:** Announced → Received → Inspected → Stocked/Rejected

### GAP-DON-001: Missing Inspect Button

| Field     | Value                      |
| --------- | -------------------------- |
| Severity  | :red_circle: Critical      |
| Component | `views/donation_views.xml` |
| Model     | `spp.drims.donation`       |

**Problem:** The donation form has a "Mark Received" button but no buttons for `action_inspect()` or `action_stock()`.
Users cannot progress donations beyond the "received" state.

**Current State:**

```xml
<button name="action_mark_received" string="Mark Received"
        type="object" class="btn-primary"
        invisible="state != 'announced'"/>
<!-- No inspect or stock buttons exist -->
```

**Required Implementation:**

```xml
<button name="action_inspect" string="Mark Inspected"
        type="object" class="btn-primary"
        invisible="state != 'received'"/>

<button name="action_stock" string="Stock Items"
        type="object" class="btn-success"
        invisible="state != 'inspected'"
        confirm="This will add items to warehouse inventory. Continue?"/>

<button name="action_reject" string="Reject"
        type="object" class="btn-outline-danger"
        invisible="state != 'inspected'"
        confirm="Reject this donation? Items will not be added to inventory."/>
```

**Acceptance Criteria:**

- [ ] "Mark Inspected" button visible when state = 'received'
- [ ] "Stock Items" button visible when state = 'inspected'
- [ ] "Reject" button visible when state = 'inspected'
- [ ] State transitions correctly update the statusbar
- [ ] Stock picking is validated when donation is stocked

---

### GAP-DON-002: Missing Cancel Button

| Field     | Value                                            |
| --------- | ------------------------------------------------ |
| Severity  | :orange_circle: High                             |
| Component | `views/donation_views.xml`, `models/donation.py` |
| Model     | `spp.drims.donation`                             |

**Problem:** `DONATION_STATE_CANCELLED` exists in state transitions but there is no UI button or method to cancel a
donation.

**Required Implementation:**

1. Add method to `models/donation.py`:

```python
def action_cancel(self):
    """Cancel the donation before stocking."""
    cancelled_state = self.env["spp.vocabulary.code"].search([
        ("vocabulary_id.namespace_uri", "=", VOCAB_DONATION_STATES),
        ("code", "=", DONATION_STATE_CANCELLED),
    ], limit=1)
    for rec in self:
        if rec.state in (DONATION_STATE_STOCKED, "rejected"):
            raise UserError(_("Cannot cancel a donation that is already stocked or rejected."))
        rec.state_id = cancelled_state
        # Cancel any pending pickings
        rec.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')).action_cancel()
```

2. Add button to `views/donation_views.xml`:

```xml
<button name="action_cancel" string="Cancel"
        type="object" class="btn-secondary"
        invisible="state in ('stocked', 'rejected', 'cancelled')"/>
```

**Acceptance Criteria:**

- [ ] Cancel button visible for announced, received, and inspected states
- [ ] Cancellation cancels any pending stock pickings
- [ ] Cancelled donations cannot be uncancelled (terminal state)

---

### GAP-DON-003: Partial Receipt Handling

| Field     | Value                                           |
| --------- | ----------------------------------------------- |
| Severity  | :orange_circle: High                            |
| Component | `views/donation_views.xml`                      |
| Model     | `spp.drims.donation`, `spp.drims.donation.line` |

**Problem:** When donations arrive partially (e.g., 80 of 100 pledged items), users cannot edit received quantities per
line item. The `quantity_received` field exists but is not visible or editable in the form view.

**Current State:** Donation line list in form does not show `quantity_received`:

```xml
<list editable="bottom">
    <field name="product_id"/>
    <field name="quantity"/>  <!-- This is pledged quantity -->
    <!-- quantity_received not shown -->
</list>
```

**Required Implementation:**

1. Update donation line list in `views/donation_views.xml`:

```xml
<list editable="bottom">
    <field name="product_id" readonly="parent.state != 'announced'"/>
    <field name="quantity_pledged" string="Pledged"/>
    <field name="quantity_received" string="Received"
           readonly="parent.state not in ('announced', 'received')"/>
    <field name="uom_id"/>
    <field name="condition_id" readonly="parent.state != 'inspected'"/>
    <!-- ... -->
</list>
```

2. Add a computed field for receipt variance:

```python
receipt_variance = fields.Float(
    compute="_compute_receipt_variance",
    string="Variance",
    help="Difference between pledged and received quantities"
)
```

**Acceptance Criteria:**

- [ ] `quantity_received` is visible and editable when state = 'received'
- [ ] Default value copies from `quantity_pledged` but can be overridden
- [ ] Variance is displayed (e.g., "-20" if 20 short)
- [ ] Stock picking uses actual received quantities, not pledged

---

### GAP-DON-004: Missing Donation Kanban View

| Field     | Value                      |
| --------- | -------------------------- |
| Severity  | :yellow_circle: Medium     |
| Component | `views/donation_views.xml` |
| Model     | `spp.drims.donation`       |

**Problem:** Donations have list, form, graph, and pivot views but no kanban view for visual state tracking.

**Required Implementation:** Add kanban view grouped by state with visual cards showing donor, warehouse, expected date,
and item count.

**Acceptance Criteria:**

- [ ] Kanban view available in view mode toggle
- [ ] Cards grouped by state (announced, received, inspected, stocked)
- [ ] Visual indicators for overdue expected dates
- [ ] Quick drag-drop for simple state changes

---

## 2. Request Lifecycle Gaps

**Current Workflow:** Draft → Submitted → Pending → Approved/Rejected → Allocated → Dispatched → Delivered

### GAP-REQ-001: Missing Source Warehouse Field in Form

| Field     | Value                     |
| --------- | ------------------------- |
| Severity  | :red_circle: Critical     |
| Component | `views/request_views.xml` |
| Model     | `spp.drims.request`       |

**Problem:** The `source_warehouse_id` field exists in the model but is not displayed in the request form view. Users
cannot select a source warehouse, which is required for allocation.

**Required Implementation:**

Add field to request form in the "Request Details" group (visible after approval):

```xml
<group string="Fulfillment" invisible="approval_state != 'approved'">
    <field name="source_warehouse_id"
           options="{'no_create': True}"
           required="approval_state == 'approved'"/>
</group>
```

**Acceptance Criteria:**

- [ ] Source warehouse field visible when request is approved
- [ ] Field is required before allocation can proceed
- [ ] Only DRIMS-enabled warehouses shown in dropdown

---

### GAP-REQ-002: Missing Allocate Button

| Field     | Value                     |
| --------- | ------------------------- |
| Severity  | :red_circle: Critical     |
| Component | `views/request_views.xml` |
| Model     | `spp.drims.request`       |

**Problem:** The `action_allocate()` method exists but there is no button in the form view to trigger it.

**Required Implementation:**

Add button to form header:

```xml
<button name="action_allocate"
        string="Allocate Stock"
        type="object"
        class="btn-primary"
        invisible="approval_state != 'approved' or state == 'allocated'"
        data-hotkey="l"/>
```

**Acceptance Criteria:**

- [x] "Allocate Stock" button visible when approved and not yet allocated
- [x] Button triggers FIFO allocation logic (oldest stock first by in_date)
- [x] Request state changes to 'allocated' after successful allocation
- [x] Error shown if source warehouse not selected
- [x] Partial allocation shows warning with available quantities

---

### GAP-REQ-003: Missing Create Dispatch Action

| Field     | Value                                          |
| --------- | ---------------------------------------------- |
| Severity  | :red_circle: Critical                          |
| Component | `views/request_views.xml`, `models/request.py` |
| Model     | `spp.drims.request`                            |

**Problem:** After allocation, there is no way to create the dispatch (stock.picking) from the request. The workflow
documentation shows this step but no method or button exists.

**Required Implementation:**

1. Add method to `models/request.py`:

```python
def action_create_dispatch(self):
    """Create a dispatch picking for this allocated request."""
    self.ensure_one()
    if self.state != 'allocated':
        raise UserError(_("Only allocated requests can be dispatched."))
    if not self.source_warehouse_id:
        raise UserError(_("Please select a source warehouse."))

    # Get picking type for outgoing deliveries
    picking_type = self.env['stock.picking.type'].search([
        ('warehouse_id', '=', self.source_warehouse_id.id),
        ('code', '=', 'outgoing'),
    ], limit=1)

    if not picking_type:
        raise UserError(_("No delivery picking type found for warehouse %s")
                        % self.source_warehouse_id.name)

    # Create picking
    picking_vals = {
        'picking_type_id': picking_type.id,
        'location_id': self.source_warehouse_id.lot_stock_id.id,
        'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        'drims_request_id': self.id,
        'drims_type_id': self._get_dispatch_type().id,
        'incident_id': self.incident_id.id,
        'origin': self.reference,
        'scheduled_date': self.date_needed,
        'beneficiary_area_id': self.destination_area_id.id,
    }
    picking = self.env['stock.picking'].create(picking_vals)

    # Create moves for each allocated line
    for line in self.line_ids.filtered(lambda l: l.quantity_allocated > 0):
        self.env['stock.move'].create({
            'product_id': line.product_id.id,
            'product_uom_qty': line.quantity_allocated,
            'product_uom': line.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'drims_request_line_id': line.id,
        })

    picking.action_confirm()

    # Update request state
    dispatched_state = self.env["spp.vocabulary.code"].search([
        ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
        ("code", "=", "dispatched"),
    ], limit=1)
    if dispatched_state:
        self.state_id = dispatched_state

    return self.action_view_pickings()
```

2. Add button to `views/request_views.xml`:

```xml
<button name="action_create_dispatch"
        string="Create Dispatch"
        type="object"
        class="btn-primary"
        invisible="state != 'allocated'"
        data-hotkey="d"/>
```

**Acceptance Criteria:**

- [ ] "Create Dispatch" button visible when state = 'allocated'
- [ ] Creates stock.picking with all allocated line items
- [ ] Sets correct DRIMS type and incident linkage
- [ ] Opens picking form after creation
- [ ] Request state updates to 'dispatched'

---

### GAP-REQ-004: Missing Request from Template Wizard

| Field     | Value                                               |
| --------- | --------------------------------------------------- |
| Severity  | :orange_circle: High                                |
| Component | `wizard/` (new), `views/request_template_views.xml` |
| Model     | `spp.drims.request.template`                        |

**Problem:** Request templates exist and have an `action_create_request()` method, but there's no wizard to:

- Select incident context
- Adjust quantities before creation
- Preview the request before saving

**Required Implementation:**

1. Create wizard model `wizard/request_from_template_wizard.py`:

```python
class RequestFromTemplateWizard(models.TransientModel):
    _name = "spp.drims.request.from.template.wizard"
    _description = "Create Request from Template"

    template_id = fields.Many2one("spp.drims.request.template", required=True)
    incident_id = fields.Many2one("spp.hazard.incident", required=True)
    destination_area_id = fields.Many2one("spp.area", required=True)
    date_needed = fields.Date(required=True)
    line_ids = fields.One2many("spp.drims.request.from.template.wizard.line", "wizard_id")

    @api.onchange('template_id')
    def _onchange_template(self):
        # Populate lines from template with editable quantities
        pass

    def action_create_request(self):
        # Create request with wizard values
        pass
```

2. Create wizard view `wizard/request_from_template_wizard_views.xml`

3. Add "Use Template" button to request list view action

**Acceptance Criteria:**

- [ ] "Create from Template" action available from request list
- [ ] Wizard shows template selection, incident, area, date
- [ ] Line items populated from template with editable quantities
- [ ] Request created with adjusted values
- [ ] Opens created request form

---

### GAP-REQ-005: Missing SLA Status Indicator ✅ IMPLEMENTED

| Field     | Value                                          |
| --------- | ---------------------------------------------- |
| Severity  | :orange_circle: High                           |
| Component | `views/request_views.xml`, `models/request.py` |
| Model     | `spp.drims.request`                            |
| Status    | ✅ **IMPLEMENTED**                             |

**Problem:** Approval SLA definitions exist (Fast-Track: 0 days, Standard: 1 day, etc.) but there is no visual indicator
showing whether a pending request is on-time, at-risk, or breached.

**Implementation:** SLA status is now computed based on priority level and configurable thresholds.

**Configurable System Parameters:**

| Parameter                     | Default | Description                          |
| ----------------------------- | ------- | ------------------------------------ |
| `drims.sla.hours.critical`    | 4       | Hours for critical priority requests |
| `drims.sla.hours.high`        | 8       | Hours for high priority requests     |
| `drims.sla.hours.routine`     | 24      | Hours for routine priority requests  |
| `drims.sla.hours.low`         | 48      | Hours for low priority requests      |
| `drims.sla.warning_threshold` | 0.75    | Warning at 75% of SLA time elapsed   |

Administrators can adjust these via Settings → Technical → System Parameters.

**Acceptance Criteria:**

- [x] SLA status computed based on priority and configurable thresholds
- [x] Visual badge shows green/yellow/red status
- [x] SLA breach triggers alert creation
- [x] Status updates automatically as time passes

---

### GAP-REQ-006: Missing Fulfillment Progress View

| Field     | Value                                         |
| --------- | --------------------------------------------- |
| Severity  | :orange_circle: High                          |
| Component | `views/request_views.xml`                     |
| Model     | `spp.drims.request`, `spp.drims.request.line` |

**Problem:** Request lines have `quantity_allocated`, `quantity_dispatched`, `quantity_delivered` fields but there's no
summary view showing fulfillment progress across all lines.

**Required Implementation:**

1. Add fulfillment summary to request form:

```xml
<group string="Fulfillment Progress" invisible="approval_state not in ('approved',)">
    <group>
        <field name="total_requested" string="Requested"/>
        <field name="total_allocated" string="Allocated"/>
        <field name="allocation_pct" widget="progressbar"/>
    </group>
    <group>
        <field name="total_dispatched" string="Dispatched"/>
        <field name="total_delivered" string="Delivered"/>
        <field name="fulfillment_pct" widget="progressbar"/>
    </group>
</group>
```

2. Add computed fields to model for totals and percentages

**Acceptance Criteria:**

- [ ] Fulfillment section visible after approval
- [ ] Progress bars show allocation and delivery percentages
- [ ] Totals aggregate from line items
- [ ] Visual indication of partial vs complete fulfillment

---

## 3. Dispatch/Allocation Workflow Gaps

### GAP-DIS-001: Missing Allocation Preview Wizard

| Field     | Value                |
| --------- | -------------------- |
| Severity  | :orange_circle: High |
| Component | `wizard/` (new)      |
| Model     | `spp.drims.request`  |

**Problem:** The FEFO allocation logic runs immediately when `action_allocate()` is called. Users cannot preview what
will be allocated or see stock availability before committing.

**Required Implementation:**

1. Create wizard `wizard/allocation_preview_wizard.py`:

```python
class AllocationPreviewWizard(models.TransientModel):
    _name = "spp.drims.allocation.preview.wizard"
    _description = "Allocation Preview"

    request_id = fields.Many2one("spp.drims.request", required=True)
    warehouse_id = fields.Many2one("stock.warehouse", required=True)
    line_ids = fields.One2many("spp.drims.allocation.preview.line", "wizard_id")

    @api.onchange('warehouse_id')
    def _onchange_warehouse(self):
        # Compute available stock and proposed allocation
        pass

    def action_confirm_allocation(self):
        # Apply the previewed allocation
        pass
```

2. Preview line model showing:
   - Product
   - Requested quantity
   - Available stock (in selected warehouse)
   - Proposed allocation
   - Shortfall (if any)

**Acceptance Criteria:**

- [ ] Wizard opens when clicking "Allocate Stock"
- [ ] Shows stock availability per product in selected warehouse
- [ ] Highlights items with insufficient stock
- [ ] Allows confirmation or cancellation
- [ ] Suggests alternative warehouses if stock insufficient

---

### GAP-DIS-002: Missing Waybill Print Action

| Field     | Value                           |
| --------- | ------------------------------- |
| Severity  | :yellow_circle: Medium          |
| Component | `views/stock_picking_views.xml` |
| Model     | `stock.picking`                 |

**Problem:** `waybill_template.xml` exists as a report template but there's no button in the stock picking form to print
the waybill.

**Required Implementation:**

Add print button to picking form header:

```xml
<button name="action_print_waybill"
        string="Print Waybill"
        type="object"
        class="btn-secondary"
        invisible="drims_type != 'request_dispatch'"/>
```

**Acceptance Criteria:**

- [ ] "Print Waybill" button visible on DRIMS dispatches
- [ ] Generates PDF using waybill_template.xml
- [ ] Includes all picking details, items, signatures

---

### GAP-DIS-003: Missing Dispatch Planning View

| Field     | Value                           |
| --------- | ------------------------------- |
| Severity  | :yellow_circle: Medium          |
| Component | `views/stock_picking_views.xml` |
| Model     | `stock.picking`                 |

**Problem:** No calendar or timeline view to plan dispatches based on `date_needed` from linked requests.

**Required Implementation:**

Add calendar view for dispatch planning:

```xml
<record id="view_picking_calendar_drims" model="ir.ui.view">
    <field name="name">stock.picking.calendar.drims</field>
    <field name="model">stock.picking</field>
    <field name="arch" type="xml">
        <calendar string="Dispatch Planning"
                  date_start="scheduled_date"
                  color="beneficiary_area_id"
                  mode="month">
            <field name="name"/>
            <field name="beneficiary_area_id"/>
            <field name="state"/>
        </calendar>
    </field>
</record>
```

**Acceptance Criteria:**

- [ ] Calendar view available in dispatches action
- [ ] Shows scheduled dates with area color coding
- [ ] Click to open dispatch details
- [ ] Drag to reschedule (updates scheduled_date)

---

## 4. Returns Workflow Gaps

### GAP-RET-001: Incomplete Create Return from Dispatch

| Field     | Value                               |
| --------- | ----------------------------------- |
| Severity  | :orange_circle: High                |
| Component | `models/stock_picking.py`           |
| Model     | `stock.picking`, `spp.drims.return` |

**Problem:** The "Create Return" button exists on completed dispatches but the logic may not properly populate return
lines from the original dispatch quantities.

**Required Verification and Fix:**

1. Verify `action_create_drims_return()` method:

   - Creates return record linked to original picking
   - Populates return lines with dispatched quantities
   - Sets correct condition defaults

2. Add return creation wizard for partial returns:

```python
class CreateReturnWizard(models.TransientModel):
    _name = "spp.drims.create.return.wizard"

    picking_id = fields.Many2one("stock.picking", required=True)
    line_ids = fields.One2many("spp.drims.create.return.wizard.line", "wizard_id")
    return_reason = fields.Text()

    # Allow selecting which items and quantities to return
```

**Acceptance Criteria:**

- [ ] Return lines populated from dispatch with editable quantities
- [ ] Can return partial quantities (not forced to return all)
- [ ] Condition can be set per line
- [ ] Return reason captured

---

### GAP-RET-002: Missing Condition-Based Disposition

| Field     | Value                                         |
| --------- | --------------------------------------------- |
| Severity  | :orange_circle: High                          |
| Component | `views/return_views.xml`, `models/returns.py` |
| Model     | `spp.drims.return.line`                       |

**Problem:** Return lines have `condition_id` but there's no clear workflow for what happens to items based on condition
(good → restock, damaged → dispose, etc.)

**Required Implementation:**

1. Add disposition workflow:

```python
# In return line model
disposition = fields.Selection([
    ('restock', 'Return to Stock'),
    ('quarantine', 'Send to Quarantine'),
    ('dispose', 'Dispose'),
], compute="_compute_disposition", store=True, readonly=False)

@api.depends('condition_id')
def _compute_disposition(self):
    for line in self:
        if line.condition_id.code in ('new', 'used_good'):
            line.disposition = 'restock'
        elif line.condition_id.code == 'damaged':
            line.disposition = 'quarantine'
        else:
            line.disposition = 'dispose'
```

2. Update restock action to handle different dispositions

**Acceptance Criteria:**

- [ ] Disposition auto-computed from condition
- [ ] Can override disposition manually
- [ ] Restock only processes items marked for restock
- [ ] Quarantine items go to quarantine location
- [ ] Disposal items are written off

---

## 5. Alert Management Gaps

> **REVIEW NOTE (2026-01-01):** GAP-ALT-001 and GAP-ALT-002 were initially flagged as critical gaps. Upon deeper review,
> these are **NOT GAPS** - the base `spp_alerts` module provides:
>
> - `action_acknowledge()` method with button in form header
> - `action_resolve()` method with button in form header
> - Resolution tracking fields (`resolved_by_id`, `resolved_at`, `resolution_notes`)
>
> The DRIMS alert views inherit from spp_alerts views, so these buttons are available.

### ~~GAP-ALT-001: Missing Acknowledge Action~~ ✅ RESOLVED

| Field    | Value                                    |
| -------- | ---------------------------------------- |
| Severity | ~~:red_circle: Critical~~ ✅ Not a gap   |
| Status   | **RESOLVED - Inherited from spp_alerts** |

The base `spp.alert` model in `spp_alerts` module provides `action_acknowledge()` method and the button is defined in
`spp_alerts/views/alert_views.xml`. DRIMS alerts inherit this via view inheritance.

---

### ~~GAP-ALT-002: Missing Resolve Action~~ ✅ RESOLVED

| Field    | Value                                    |
| -------- | ---------------------------------------- |
| Severity | ~~:red_circle: Critical~~ ✅ Not a gap   |
| Status   | **RESOLVED - Inherited from spp_alerts** |

The base `spp.alert` model provides:

- `action_resolve(notes=None)` method
- `resolved_by_id`, `resolved_at`, `resolution_notes` fields
- "Resolve" button in form header

---

### GAP-ALT-003: Missing Alert Action Links

| Field     | Value                   |
| --------- | ----------------------- |
| Severity  | :orange_circle: High    |
| Component | `views/alert_views.xml` |
| Model     | `spp.drims.alert`       |

**Problem:** Alerts don't link to corrective actions. For example:

- Low stock alert should link to "Create Donation Request" or "Transfer Stock"
- Expiry alert should link to "Create Disposal"
- SLA breach should link to the overdue request

**Required Implementation:**

Add smart buttons based on alert type:

```xml
<div class="oe_button_box" name="button_box">
    <button name="action_view_product_stock"
            type="object"
            class="oe_stat_button"
            icon="fa-cubes"
            invisible="alert_type != 'low_stock'">
        <span>View Stock</span>
    </button>
    <button name="action_create_transfer"
            type="object"
            class="oe_stat_button"
            icon="fa-exchange"
            invisible="alert_type != 'low_stock'">
        <span>Request Transfer</span>
    </button>
    <button name="action_view_request"
            type="object"
            class="oe_stat_button"
            icon="fa-list-alt"
            invisible="request_id == False">
        <span>View Request</span>
    </button>
</div>
```

**Acceptance Criteria:**

- [ ] Low stock alerts: View Stock, Request Transfer buttons
- [ ] Expiry alerts: View Lot, Create Disposal buttons
- [ ] SLA alerts: View Request button
- [ ] Actions open relevant forms/wizards

---

## 6. Inventory Management Gaps

### GAP-INV-001: Missing Stock Adjustment Wizard

| Field     | Value                  |
| --------- | ---------------------- |
| Severity  | :red_circle: Critical  |
| Component | `wizard/` (new)        |
| Model     | `stock.quant` (extend) |

**Problem:** No DRIMS-specific way to adjust stock with incident tracking. Standard Odoo inventory adjustment doesn't
capture DRIMS context (incident, reason, authorization).

**Required Implementation:**

Create wizard `wizard/stock_adjustment_wizard.py`:

```python
class DrimsStockAdjustmentWizard(models.TransientModel):
    _name = "spp.drims.stock.adjustment.wizard"
    _description = "DRIMS Stock Adjustment"

    incident_id = fields.Many2one("spp.hazard.incident", required=True)
    warehouse_id = fields.Many2one("stock.warehouse", required=True)
    reason = fields.Selection([
        ('damage', 'Damaged'),
        ('loss', 'Lost'),
        ('theft', 'Theft'),
        ('expired', 'Expired'),
        ('error', 'Counting Error'),
        ('other', 'Other'),
    ], required=True)
    line_ids = fields.One2many(...)
    notes = fields.Text()
    authorized_by = fields.Many2one("res.users")

    def action_apply_adjustment(self):
        # Create inventory adjustment with DRIMS tracking
        pass
```

**Acceptance Criteria:**

- [ ] Wizard accessible from Inventory menu
- [ ] Captures incident, warehouse, reason
- [ ] Creates audit trail in DRIMS activity feed
- [ ] Updates stock quantities
- [ ] Optionally generates alert for significant losses

---

### GAP-INV-002: Missing Inter-Warehouse Transfer Action

| Field     | Value                 |
| --------- | --------------------- |
| Severity  | :red_circle: Critical |
| Component | `wizard/` (new)       |
| Model     | `stock.picking`       |

**Problem:** No easy way to transfer stock between DRIMS warehouses. Standard Odoo internal transfers don't have DRIMS
context.

**Required Implementation:**

Create wizard `wizard/inter_warehouse_transfer_wizard.py`:

```python
class DrimsInterWarehouseTransfer(models.TransientModel):
    _name = "spp.drims.inter.warehouse.transfer"
    _description = "Inter-Warehouse Transfer"

    incident_id = fields.Many2one("spp.hazard.incident", required=True)
    source_warehouse_id = fields.Many2one("stock.warehouse", required=True)
    dest_warehouse_id = fields.Many2one("stock.warehouse", required=True)
    line_ids = fields.One2many(...)
    reason = fields.Text()

    def action_create_transfer(self):
        # Create internal transfer with DRIMS tracking
        pass
```

**Acceptance Criteria:**

- [ ] Wizard accessible from warehouse form and inventory menu
- [ ] Shows available stock in source warehouse
- [ ] Creates internal transfer picking
- [ ] Links to incident
- [ ] Tracked in activity feed

---

### GAP-INV-003: Missing Expired Item Disposal Workflow

| Field     | Value                |
| --------- | -------------------- |
| Severity  | :orange_circle: High |
| Component | `wizard/` (new)      |
| Model     | `stock.lot`          |

**Problem:** Expiry alerts fire but there's no wizard to dispose of expired items properly.

**Required Implementation:**

Create disposal workflow:

1. Wizard to select expired lots
2. Create scrapping operation
3. Update DRIMS tracking
4. Resolve related expiry alerts

**Acceptance Criteria:**

- [ ] Disposal wizard accessible from lot view and expiry alerts
- [ ] Creates scrap record with incident link
- [ ] Auto-resolves related expiry alerts
- [ ] Audit trail captured

---

## 7. Personnel Management Gaps

### GAP-PER-001: Missing On Leave Action

| Field     | Value                       |
| --------- | --------------------------- |
| Severity  | :orange_circle: High        |
| Component | `views/personnel_views.xml` |
| Model     | `spp.drims.personnel`       |

**Problem:** Personnel can be "deployed", "standby", or "returned" via buttons but there's no button to mark someone as
"on_leave".

**Required Implementation:**

1. Add method to `models/personnel.py`:

```python
def action_mark_on_leave(self):
    self.write({'status': 'on_leave'})
```

2. Add button to form:

```xml
<button name="action_mark_on_leave"
        string="On Leave"
        type="object"
        class="btn-secondary"
        invisible="status in ('returned', 'on_leave')"/>
```

**Acceptance Criteria:**

- [ ] "On Leave" button visible for deployed/standby personnel
- [ ] Status changes to 'on_leave'
- [ ] Can return from leave via existing "Mark Deployed" button

---

### GAP-PER-002: Missing Personnel Roster/Calendar View

| Field     | Value                       |
| --------- | --------------------------- |
| Severity  | :orange_circle: High        |
| Component | `views/personnel_views.xml` |
| Model     | `spp.drims.personnel`       |

**Problem:** No calendar or timeline view to see personnel deployment periods.

**Required Implementation:**

Add calendar view:

```xml
<record id="spp_drims_personnel_calendar" model="ir.ui.view">
    <field name="name">spp.drims.personnel.calendar</field>
    <field name="model">spp.drims.personnel</field>
    <field name="arch" type="xml">
        <calendar string="Personnel Roster"
                  date_start="deployment_date"
                  date_stop="expected_return_date"
                  color="organization_id"
                  mode="month">
            <field name="name"/>
            <field name="role_id"/>
            <field name="deployment_area_id"/>
        </calendar>
    </field>
</record>
```

**Acceptance Criteria:**

- [ ] Calendar view shows deployment periods as spans
- [ ] Color coded by organization
- [ ] Click to open personnel form
- [ ] Can create new deployment from calendar

---

## 8. Reporting & Cross-Functional Gaps

### GAP-RPT-001: Missing Executive Summary Dashboard

| Field     | Value                       |
| --------- | --------------------------- |
| Severity  | :orange_circle: High        |
| Component | `views/dashboard_views.xml` |
| Model     | `spp.hazard.incident`       |

**Problem:** The incident kanban shows KPIs but there's no single-page executive summary for coordination meetings.

**Required Implementation:**

Create dedicated dashboard view or report with:

- Incident status overview
- Donations received vs distributed
- Request pipeline (pending, approved, dispatched)
- Stock position summary
- Active alerts
- Beneficiaries reached

**Acceptance Criteria:**

- [ ] One-page summary accessible from Dashboard menu
- [ ] Real-time data refresh
- [ ] Printable format for meetings
- [ ] Filters by incident, date range

---

### GAP-RPT-002: Missing Stock Pipeline Report

| Field     | Value                |
| --------- | -------------------- |
| Severity  | :orange_circle: High |
| Component | `reports/` (new)     |
| Model     | Multiple             |

**Problem:** No view of:

- Expected donations (announced but not received)
- Pending request demand
- Future stock position forecast

**Required Implementation:**

Create pipeline report showing:

- Current stock by product/warehouse
- Incoming (expected donations)
- Outgoing (approved requests)
- Net position

**Acceptance Criteria:**

- [ ] Report accessible from Reports menu
- [ ] Shows current, incoming, outgoing, net columns
- [ ] Filterable by warehouse, product category
- [ ] Highlights shortfall risks

---

## Implementation Priority Matrix

> **Updated 2026-01-01:** Removed GAP-ALT-001, GAP-ALT-002 (not gaps - inherited from spp_alerts)

| Priority | Gap ID          | Description                      | Effort  | Status       |
| -------- | --------------- | -------------------------------- | ------- | ------------ |
| 1        | GAP-DON-001     | Add inspect/stock/reject buttons | Low     | **BLOCKING** |
| 2        | GAP-REQ-001     | Add source_warehouse field       | Low     | **BLOCKING** |
| 3        | GAP-REQ-002     | Add allocate button              | Low     | **BLOCKING** |
| 4        | GAP-REQ-003     | Create dispatch action method    | Medium  | **BLOCKING** |
| 5        | GAP-INV-001     | Stock adjustment wizard          | Medium  | High         |
| 6        | GAP-INV-002     | Inter-warehouse transfer         | Medium  | High         |
| 7        | GAP-DON-002     | Add cancel button + method       | Low     | High         |
| 8        | GAP-DON-003     | Partial receipt handling         | Medium  | High         |
| 9        | GAP-DIS-001     | Allocation preview wizard        | Medium  | Medium       |
| 10       | GAP-REQ-004     | Request from template wizard     | Medium  | Medium       |
| 11       | GAP-REQ-005     | SLA status indicator             | Medium  | Medium       |
| 12       | GAP-RET-001     | Complete return creation         | Medium  | Medium       |
| 13       | GAP-ALT-003     | Alert action links               | Low     | Medium       |
| 14       | GAP-PER-001     | On leave action                  | Low     | Low          |
| ~~5~~    | ~~GAP-ALT-001~~ | ~~Add acknowledge action~~       | ~~Low~~ | ✅ Not a gap |
| ~~6~~    | ~~GAP-ALT-002~~ | ~~Add resolve action~~           | ~~Low~~ | ✅ Not a gap |

---

## Appendix: File Changes Summary

### Files to Modify

| File                            | Changes                                                                      |
| ------------------------------- | ---------------------------------------------------------------------------- |
| `views/donation_views.xml`      | Add inspect/stock/reject/cancel buttons, partial receipt fields              |
| `views/request_views.xml`       | Add source_warehouse, allocate/dispatch buttons, fulfillment progress        |
| `views/alert_views.xml`         | Add action links (acknowledge/resolve already inherited)                     |
| `views/personnel_views.xml`     | Add on_leave button, calendar view                                           |
| `views/stock_picking_views.xml` | Add waybill print button, calendar view                                      |
| `models/donation.py`            | Add cancel method                                                            |
| `models/request.py`             | Add create_dispatch method, SLA fields                                       |
| `models/alert.py`               | ~~Add acknowledge/resolve methods~~ (not needed - inherited from spp_alerts) |

### New Files to Create

| File                                               | Purpose                         |
| -------------------------------------------------- | ------------------------------- |
| `wizard/allocation_preview_wizard.py`              | Allocation preview wizard       |
| `wizard/allocation_preview_wizard_views.xml`       | Wizard views                    |
| `wizard/request_from_template_wizard.py`           | Template-based request creation |
| `wizard/request_from_template_wizard_views.xml`    | Wizard views                    |
| `wizard/stock_adjustment_wizard.py`                | DRIMS stock adjustment          |
| `wizard/stock_adjustment_wizard_views.xml`         | Wizard views                    |
| `wizard/inter_warehouse_transfer_wizard.py`        | Warehouse transfer              |
| `wizard/inter_warehouse_transfer_wizard_views.xml` | Wizard views                    |

---

## Appendix B: Deep Review Findings (2026-01-01)

### What Works Well

The following workflows are **COMPLETE** and require no changes:

| Workflow             | Status           | Notes                                                                    |
| -------------------- | ---------------- | ------------------------------------------------------------------------ |
| **Return Lifecycle** | ✅ Complete      | All 6 buttons present: Confirm, Receive, Inspect, Restock, Cancel, Reset |
| **Alert Management** | ✅ Complete      | Acknowledge/Resolve inherited from spp_alerts; state machine works       |
| **Request Approval** | ✅ Complete      | Submit, Approve, Reject, Request Changes, Reset - all functional         |
| **Security Rules**   | ✅ Comprehensive | Area-based and warehouse-based scoping; multi-company isolation          |

### Critical Blockers (Cannot Complete E2E Without These)

These 4 gaps **MUST** be fixed before the system can be used in emergencies:

1. **GAP-DON-001** - Donation workflow blocked at 50%

   - Users can receive donations but cannot inspect or stock them
   - Methods exist (`action_inspect`, `action_stock`) but no buttons in view

2. **GAP-REQ-001** + **GAP-REQ-002** - Request workflow blocked after approval

   - No source warehouse field visible
   - No allocate button despite method existing

3. **GAP-REQ-003** - Cannot create dispatches from allocated requests
   - No `action_create_dispatch` method exists
   - After allocation, users cannot proceed to dispatch

### Emergency Scenarios Reviewed

| Scenario                                   | Can Complete? | Blocker                |
| ------------------------------------------ | ------------- | ---------------------- |
| Receive urgent donation, stock immediately | ❌ No         | GAP-DON-001            |
| Create request, get approved, dispatch     | ❌ No         | GAP-REQ-001/002/003    |
| Return unused items from field             | ✅ Yes        | -                      |
| Acknowledge and resolve low stock alert    | ✅ Yes        | -                      |
| Transfer stock between warehouses          | ❌ No         | GAP-INV-002            |
| Adjust stock after damage/theft            | ❌ No         | GAP-INV-001            |
| Track personnel deployment                 | ✅ Partial    | GAP-PER-001 (on_leave) |

### Minimum Viable Fix

To get E2E operations working, implement these in order:

```
Priority 1: GAP-DON-001 (add 3 buttons to donation form) - 15 min
Priority 2: GAP-REQ-001 (add source_warehouse field to request form) - 5 min
Priority 3: GAP-REQ-002 (add allocate button to request form) - 5 min
Priority 4: GAP-REQ-003 (implement action_create_dispatch method) - 1 hour
```

**Total time to unblock E2E: ~1.5 hours**
