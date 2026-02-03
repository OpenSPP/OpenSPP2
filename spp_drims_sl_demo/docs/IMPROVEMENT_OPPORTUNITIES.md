# DRIMS Improvement Opportunities

Analysis of current implementation vs Sri Lanka DMC requirements.

> **Last Updated:** 2026-01-06 **Status:** Most critical gaps have been addressed. See "Recently Implemented" section.

## Coverage Matrix

### Fully Implemented ✅

| Requirement                          | Implementation                      | Notes                                           |
| ------------------------------------ | ----------------------------------- | ----------------------------------------------- |
| Centralized real-time inventory      | `spp.drims.donation`, `stock.quant` | Full integration with Odoo stock                |
| Item categorization                  | `product.category` hierarchy        | 7 categories with 33 products                   |
| Real-time stock updates              | Stock picking workflow              | Automatic on donation/dispatch                  |
| Request submission by field officers | `spp.drims.request`                 | Web-based form                                  |
| Multi-level approval workflow        | `approval_state` + security groups  | Draft→Pending→Approved flow                     |
| Issuance with acknowledgment         | Waybill report + signatures         | PDF generation                                  |
| Distribution recording               | Stock picking + destination area    | Area-level tracking                             |
| Role-based access                    | 3 security groups                   | User, Approver, Manager                         |
| Audit logging                        | `mail.tracking` inheritance         | Full change history                             |
| Item master management               | Products with lot tracking          | Relief items catalog                            |
| Warehouse master                     | `stock.warehouse` extension         | 11 Sri Lanka warehouses                         |
| Batch/lot tracking                   | `stock.lot` integration             | For food/medical items                          |
| Expiry tracking                      | Alert engine + product_expiry       | 30-day warning threshold                        |
| Low stock alerts                     | `_cron_check_low_stock()`           | 50% threshold                                   |
| SLA monitoring                       | `_cron_check_sla()`                 | Breach and warning alerts                       |
| **Return management**                | `spp.drims.return` + wizard         | **NEW** - Full workflow with condition tracking |
| **Stock allocation preview**         | `allocation_preview_wizard`         | **NEW** - FIFO allocation with preview          |
| **Inter-warehouse transfers**        | `inter_warehouse_transfer_wizard`   | **NEW** - Easy stock redistribution             |
| **Stock adjustments**                | `stock_adjustment_wizard`           | **NEW** - With reason tracking                  |
| **Request from template**            | `request_from_template_wizard`      | **NEW** - Quick request creation                |
| **SLA status indicator**             | `sla_status` computed field         | **NEW** - Configurable thresholds               |
| **Donation full workflow**           | Inspect/Stock/Reject/Cancel buttons | **NEW** - Complete E2E flow                     |
| **Dispatch creation**                | `action_create_dispatch()`          | **NEW** - From allocated request                |

### Partially Implemented 🟡

| Requirement                     | Current State                    | Gap                                          |
| ------------------------------- | -------------------------------- | -------------------------------------------- |
| **Executive Dashboard**         | Kanban + KPIs on incident        | Missing dedicated dashboard view with charts |
| **Stock by category chart**     | Data available                   | No bar/donut chart visualization             |
| **Request status pie chart**    | Data available                   | No chart visualization                       |
| **Critical/low stock KPI card** | Alert exists                     | Not prominently shown on dashboard           |
| **Expiry KPI card**             | Alert exists                     | Not prominently shown on dashboard           |
| **Geographic filtering**        | Area field exists                | No province/district quick filter            |
| **Date range filtering**        | Date fields exist                | No 24h/7d/30d quick filter                   |
| **Activity feed**               | `mail.message` exists            | No sidebar widget showing recent activity    |
| **Agency directory**            | Partner model                    | No dedicated team/agency listing             |
| **Deployed teams map**          | Area linkage exists              | No GIS visualization                         |
| **Beneficiary count**           | `affected_population` on request | Not aggregated to dashboard                  |

### Not Implemented ❌

| Requirement                     | Priority | Complexity | Notes                         |
| ------------------------------- | -------- | ---------- | ----------------------------- |
| **Warehouse map visualization** | High     | Medium     | Color-coded by stock status   |
| **Stock detail dashboard page** | Medium   | Low        | Dedicated inventory list view |
| **Distribution reports**        | Medium   | Medium     | Beneficiary reach by district |
| **Barcode/QR generation**       | Low      | Medium     | Optional per spec             |
| **GIS team deployment map**     | Low      | High       | Requires GIS integration      |

### Recently Implemented ✅ (moved from Not Implemented)

| Requirement                       | Implementation                              | Notes                                 |
| --------------------------------- | ------------------------------------------- | ------------------------------------- |
| ~~Return management workflow~~    | `spp.drims.return` + `create_return_wizard` | Full workflow with condition tracking |
| ~~Priority request highlighting~~ | Decorations + badges in views               | Critical/High visually distinguished  |
| ~~Disaster event selector~~       | Searchpanel on all views                    | Quick filter by incident              |

---

## High-Impact Improvements

### 1. Executive Dashboard Enhancement

**Current:** Kanban view with cards **Needed:** Dedicated dashboard with charts and KPIs

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Total Stock: LKR 45M] [Active Requests: 23] [Low Stock: 5]       │
│  [Expiring Soon: 12]    [Beneficiaries: 52,000] [Teams: 34]        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────────────────────┐  │
│  │  Stock by Category  │  │  Request Status                     │  │
│  │  [Bar Chart]        │  │  [Pie Chart]                        │  │
│  │  Food: 40%          │  │  Pending: 30%                       │  │
│  │  Medical: 25%       │  │  Approved: 45%                      │  │
│  │  Shelter: 20%       │  │  Dispatched: 20%                    │  │
│  │  ...                │  │  Delivered: 5%                      │  │
│  └─────────────────────┘  └─────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  [MAP] Warehouse Status                                      │   │
│  │  🟢 Colombo    🟡 Galle    🔴 Jaffna    🟢 Kandy             │   │
│  └─────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  Recent Activity                    │  High Priority Requests      │
│  • 500 blankets received - Colombo  │  • REQ-2025-0045 - Galle     │
│  • Request approved - Ratnapura     │  • REQ-2025-0042 - Colombo   │
│  • Expiry alert - Paracetamol       │  • REQ-2025-0039 - Gampaha   │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation Approach:**

- Use Odoo's dashboard module or custom view
- Add computed fields for dashboard KPIs
- Consider `owl` components for charts

**Effort:** 3-5 days

---

### 2. Incident Quick Filters

**Current:** Must navigate to incident to see its data **Needed:** Filter all views by active incident

**Implementation:**

```python
# Add to search views
<filter name="incident_filter" string="Incident"
        context="{'group_by': 'incident_id'}"/>

# Add searchpanel for quick incident selection
<searchpanel>
    <field name="incident_id" icon="fa-exclamation-triangle"/>
</searchpanel>
```

**Effort:** 1 day

---

### 3. Dashboard KPI Summary Cards

**Current:** KPIs only on incident form **Needed:** Global KPIs visible on main dashboard

**Add computed fields to a dashboard model:**

```python
class DrimsDashboard(models.Model):
    _name = "spp.drims.dashboard"

    total_stock_value = fields.Float(compute="_compute_totals")
    active_requests = fields.Integer(compute="_compute_totals")
    low_stock_alerts = fields.Integer(compute="_compute_totals")
    expiring_items = fields.Integer(compute="_compute_totals")
    beneficiaries_served = fields.Integer(compute="_compute_totals")
```

**Effort:** 2 days

---

### 4. Priority Visual Enhancement

**Current:** Priority is a field, no visual distinction **Needed:** Critical/high priority requests visually highlighted

**Implementation:**

```xml
<!-- In kanban view -->
<div t-attf-class="#{record.priority.raw_value == 'critical' ? 'bg-danger' :
                     record.priority.raw_value == 'high' ? 'bg-warning' : ''}">
```

**Effort:** 0.5 days

---

### 5. Return Management Workflow ✅ IMPLEMENTED

**Status:** ✅ Fully implemented

**Implementation delivered:**

- `spp.drims.return` model with full state machine (draft→confirmed→received→inspected→restocked)
- `create_return_wizard` for creating returns from dispatches
- Condition tracking per line (good, damaged, unusable)
- Disposition workflow (restock, quarantine, dispose)
- Automatic restocking via stock picking
- Full audit trail via mail.thread

**Original Effort Estimate:** 3-4 days ✅ Completed

---

## Demo Data Improvements

### Current Gaps in Demo Data

1. **No alerts generated** - Cron jobs need to run after demo data creation
2. **All donations from same period** - Need variety in dates
3. **No overdue requests** - Need requests past deadline for SLA demo
4. **No expiring items** - Need lots with near-expiry dates
5. **Limited state variety** - Most records in terminal states

### Recommended Demo Data Enhancements

```python
# In drims_demo_generator.py

def _create_demo_alerts(self):
    """Create sample alerts for demo purposes."""
    # Low stock alert
    self.env["spp.drims.alert"].create({
        "alert_type_id": low_stock_type.id,
        "priority": "high",
        "title": "Low Stock: Rice (25kg)",
        "description": "Stock at Colombo warehouse below 50% of pending requests",
        "warehouse_id": colombo_wh.id,
        "product_id": rice_product.id,
        "current_value": 50,
        "threshold_value": 200,
    })

def _create_expiring_lots(self):
    """Create lots with near-expiry dates."""
    expiry_date = fields.Date.today() + timedelta(days=14)
    lot = self.env["stock.lot"].create({
        "name": "DEMO-EXP-001",
        "product_id": medicine_product.id,
        "expiration_date": expiry_date,
    })

def _create_overdue_requests(self):
    """Create requests past their deadline for SLA breach demo."""
    request = self.env["spp.drims.request"].create({
        "date_needed": fields.Date.today() - timedelta(days=5),
        "state": "approved",
        "approval_state": "approved",
        # ...
    })
```

### Demo Scenario Enhancement

Add more realistic scenarios:

1. **Scenario: Stock Shortage Crisis**

   - Multiple requests for same item
   - Low stock alert triggered
   - Show allocation conflict resolution

2. **Scenario: Expiry Management**

   - Items nearing expiry
   - FEFO allocation prioritizing oldest stock
   - Donation with expired items (rejection flow)

3. **Scenario: Multi-Incident Coordination**
   - Two concurrent disasters
   - Resource sharing between incidents
   - Priority-based allocation

---

## Implementation Roadmap

### Phase 1: Quick Wins (1 week) ✅ COMPLETE

- [x] Incident quick filter on all views (searchpanel)
- [x] Priority visual highlighting (decorations + badges)
- [ ] Add demo alerts and expiring lots
- [ ] Add overdue requests to demo data

### Phase 2: Dashboard Enhancement (2 weeks) - IN PROGRESS

- [ ] KPI summary cards on main dashboard
- [ ] Stock by category chart
- [ ] Request status pie chart
- [ ] Recent activity feed widget

### Phase 3: Advanced Features (3 weeks) ✅ MOSTLY COMPLETE

- [x] Return management workflow
- [ ] Warehouse map visualization
- [ ] Distribution reports by district
- [ ] Beneficiary aggregation

**Additional completed items (not in original roadmap):**

- [x] Stock allocation preview wizard
- [x] Inter-warehouse transfer wizard
- [x] Stock adjustment wizard
- [x] Request from template wizard
- [x] SLA status indicator with configurable thresholds
- [x] Complete donation workflow (all buttons)
- [x] Dispatch creation from request

### Phase 4: Future Enhancements

- [ ] Mobile-optimized views
- [ ] Offline capability
- [ ] Barcode/QR scanning
- [ ] GIS integration for team deployment

---

## Technical Debt

### Issues to Address

1. **Dashboard KPIs use computed fields**

   - May be slow with large datasets
   - Consider SQL views or stored computeds

2. **Alert cron jobs use raw SQL**

   - Good for performance
   - Need to maintain when schema changes

3. **Demo generator creates lots inline**

   - Works but verbose
   - Consider extracting to helper methods

4. **No pagination on dashboard**
   - Could be slow with many incidents
   - Add default limit or infinite scroll

---

## Summary

**Strengths of Current Implementation:**

- Solid core workflows (donation, request, dispatch) - **now complete E2E**
- Good Odoo integration (stock, picking, lots)
- Proper security model
- Alert engine foundation
- **NEW:** Return management workflow
- **NEW:** Stock allocation preview wizard
- **NEW:** Inter-warehouse transfers
- **NEW:** Stock adjustments with reason tracking
- **NEW:** SLA status with configurable thresholds
- **NEW:** Request from template wizard

**Remaining Gaps for SL DMC:**

- Executive dashboard visualization (charts, KPI cards)
- ~~Quick filtering by incident/date~~ ✅ Done (searchpanel)
- ~~Return management~~ ✅ Done
- ~~Visual priority emphasis~~ ✅ Done (decorations + badges)
- Warehouse map visualization
- Distribution reports by district

**Recommended Next Steps:**

1. Enhance demo data with alerts and realistic scenarios
2. Build executive dashboard view with charts
3. Add warehouse map visualization
4. Create distribution reports by district
