# OpenSPP DRIMS - Disaster Response Inventory Management

DRIMS is a comprehensive disaster relief inventory management system built on OpenSPP. It manages the full lifecycle of
emergency supplies from donation receipt through distribution to affected populations.

## Features

### Core Workflows

- **Donations** - Track pledged and received donations from UN agencies, NGOs, governments, and private donors
- **Requests** - Multi-tier approval workflow for relief supply requests from field locations
- **Dispatches** - Warehouse picking operations with waybill generation and proof of delivery
- **Returns** - Handle damaged, expired, or excess items returned from distribution points

### Inventory Management

- **Warehouse Dashboard** - Real-time visibility into stock levels across all warehouses
- **Stock Health Indicators** - Color-coded health status (critical/warning/good) based on alerts
- **Lot Tracking** - Batch and expiry date tracking for perishable items
- **Multi-warehouse** - Central, regional, and mobile warehouse support

### Alerts & Monitoring

- **Low Stock Alerts** - Automatic detection when inventory falls below thresholds
- **SLA Monitoring** - Track request fulfillment against delivery deadlines
- **Expiry Alerts** - Warnings for items approaching expiration
- **Activity Feed** - Real-time audit trail of all DRIMS operations

### Coordination

- **Incident Linking** - All operations tied to specific disaster incidents
- **OCHA Clusters** - Standard humanitarian sector classification
- **Multi-agency** - Coordination modes for lead agency, cluster, or consortium responses
- **Personnel Directory** - Track deployed staff by role, organization, and location

### Reporting

- **4W Reports** - Who does What, Where, When - standard humanitarian reporting
- **Dashboard KPIs** - Stock value, distributed value, beneficiaries served
- **Waybill Generation** - Printable dispatch documents

## Installation

### Dependencies

DRIMS requires the following OpenSPP modules:

- `spp_hazard` - Hazard incident management
- `spp_area` - Geographic area hierarchy
- `spp_vocabulary` - Controlled vocabularies
- `spp_approval` - Approval workflow engine
- `spp_audit` - Audit trail logging
- `spp_alerts` - Alert management
- `stock` - Odoo inventory (included in Odoo)

### Install

```bash
# Install via Odoo Apps or module installation
# Ensure all dependencies are installed first
```

After installation, access DRIMS from the main menu.

## Quick Start

### 1. Configure Warehouses

Navigate to **DRIMS > Inventory > Warehouses** and mark warehouses for DRIMS use:

- Enable "DRIMS Warehouse" checkbox
- Set warehouse tier (Central, Regional, Mobile)
- Assign to geographic area

### 2. Create an Incident

DRIMS operations are linked to disaster incidents. Create one in **DRIMS > Dashboard** or via the Hazard module.

### 3. Receive a Donation

1. Go to **DRIMS > Operations > Donations**
2. Click "Create"
3. Select incident and receiving warehouse
4. Add donor and pledged items
5. Progress through states: Announced → Received → Inspected → Stocked

### 4. Submit a Request

1. Go to **DRIMS > Operations > Requests**
2. Click "Create"
3. Select incident and destination area
4. Add requested items with quantities
5. Submit for approval

### 5. Approve and Dispatch

1. Approvers review in **DRIMS > Operations > Pending Approval**
2. Approve or reject with comments
3. Warehouse staff create dispatch from approved request
4. Complete picking and confirm proof of delivery

## Security Roles

| Role                 | Description          | Key Permissions                                     |
| -------------------- | -------------------- | --------------------------------------------------- |
| Viewer               | Read-only access     | View all DRIMS data                                 |
| Officer              | Field operations     | Create donations, requests, dispatches              |
| Warehouse Staff      | Inventory operations | Receive donations, manage stock, process dispatches |
| Field Officer        | Field operations     | Create requests, confirm deliveries                 |
| District Coordinator | Area coordination    | Coordinate within assigned districts                |
| Request Approver     | Approval workflow    | Approve/reject requests                             |
| Manager              | Full administration  | All permissions + configuration                     |

## Module Structure

```
spp_drims/
├── models/
│   ├── donation.py          # Donation management
│   ├── request.py           # Relief requests
│   ├── alert.py             # Alert engine
│   ├── personnel.py         # Personnel directory
│   ├── returns.py           # Return handling
│   ├── stock_picking.py     # Dispatch extensions
│   └── stock_warehouse.py   # Warehouse extensions
├── wizard/
│   ├── bulk_approve_wizard.py
│   └── report_4w_wizard.py
├── views/
├── data/
│   ├── vocabulary_*.xml     # Controlled vocabularies
│   ├── ir_cron.xml          # Scheduled jobs
│   └── audit_rules.xml      # Audit configuration
├── security/
│   ├── groups.xml           # Security groups
│   ├── ir.model.access.csv  # Model permissions
│   └── rules.xml            # Record rules
└── docs/
    ├── README.md            # This file
    ├── WORKFLOWS.md         # Workflow documentation
    ├── ALERTS.md            # Alert engine
    ├── COORDINATION.md      # Multi-agency coordination
    └── ...
```

## Country Modules

DRIMS can be extended with country-specific modules:

- `spp_drims_sl` - Sri Lanka configuration (areas, warehouses, hazard types)
- `spp_drims_sl_demo` - Sri Lanka demo data generator

## Documentation

- [Workflows](docs/WORKFLOWS.md) - Donation, request, and dispatch workflows
- [Alerts](docs/ALERTS.md) - Alert engine configuration
- [Coordination](docs/COORDINATION.md) - OCHA clusters and multi-agency coordination
- [Security](docs/SECURITY.md) - Groups and access rights
- [4W Reporting](docs/4W_REPORTING.md) - Humanitarian reporting
- [Dashboards](docs/DASHBOARDS.md) - KPIs and metrics
- [Integration](docs/INTEGRATION.md) - Module dependencies
- [Data Model](docs/DATA_MODEL.md) - Entity relationships

## License

LGPL-3.0 - See LICENSE file for details.

## Maintainers

- [@jeremi](https://github.com/jeremi)
- [@gonzalesedwin1123](https://github.com/gonzalesedwin1123)
