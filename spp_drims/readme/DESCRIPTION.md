Disaster relief inventory management for emergency response operations. Tracks donations from multiple sources, processes supply requests with multi-tier approval workflows, manages warehouse stock, and monitors deliveries to affected areas. Links all transactions to hazard incidents and generates automated alerts for low stock, expiring items, and SLA breaches.

### Key Capabilities

- Record incoming donations with state machine (announced, received, inspected, stocked) and inspection workflow
- Submit supply requests for affected areas with approval workflow, SLA tracking, and priority handling
- Allocate stock using FIFO/FEFO logic and create dispatch pickings with beneficiary area tracking
- Track returned items with condition assessment and disposition routing (restock, repair, dispose)
- Generate alerts automatically for low stock thresholds, expiring inventory, and overdue requests
- Create request templates for rapid response to recurring emergency scenarios
- Monitor fulfillment progress with allocation percentage, dispatch status, and delivery tracking
- Assign personnel to warehouses and service points with role and cluster tracking

### Key Models

| Model                            | Description                                                     |
| -------------------------------- | --------------------------------------------------------------- |
| `spp.drims.donation`             | Incoming donation record with pledged and received quantities   |
| `spp.drims.request`              | Supply request for affected area, includes approval workflow    |
| `spp.drims.request.template`     | Reusable template for common request patterns                   |
| `spp.drims.return`               | Item return from distribution point to warehouse                |
| `spp.drims.alert`                | Extends `spp.alert` with incident, warehouse, and product links |
| `spp.drims.personnel`            | Personnel assignment to warehouses and service points           |
| `stock.picking` (extended)       | Links stock transfers to DRIMS donations, requests, and returns |
| `stock.warehouse` (extended)     | DRIMS warehouse flag and area assignment                        |
| `spp.hazard.incident` (extended) | Links DRIMS transactions to disaster incidents                  |

### Configuration

After installing:

1. Navigate to **DRIMS > Inventory > Warehouses** and mark warehouses as DRIMS warehouses
2. System parameters are in `ir.config_parameter` with prefix `drims.*` (defaults in `data/config_defaults.xml`)
3. To configure via UI, install optional `spp_studio_drims` module for Settings page
4. Verify scheduled actions are active under **Settings > Technical > Scheduled Actions**:
   - DRIMS: Check Low Stock (daily)
   - DRIMS: Check Expiry Dates (daily)
   - DRIMS: Check SLA Breaches (hourly)
5. Create request templates under **DRIMS > Configuration > Request Templates** for common scenarios
6. Assign approval workflows to `spp.drims.request` model under **Social Protection > Configuration > Approval Workflows**

### UI Location

- **Dashboard**: DRIMS > Dashboard (KPIs, recent activity, pending approvals)
- **Donations**: DRIMS > Receive Supplies > Donations
- **Requests**: DRIMS > Fulfill Requests > All Requests
- **Dispatches**: DRIMS > Fulfill Requests > Dispatches
- **Returns**: DRIMS > Receive Supplies > Returns
- **Alerts**: DRIMS > Monitoring > Alerts
- **Personnel**: DRIMS > Monitoring > Personnel
- **Inventory**: DRIMS > Inventory > Stock On Hand, Warehouses, Products

### Security

| Group                                            | Access                                                       |
| ------------------------------------------------ | ------------------------------------------------------------ |
| `spp_drims.group_drims_viewer`                   | Read-only access to donations, requests, dispatches          |
| `spp_drims.group_drims_officer`                  | Create and edit donations, requests, returns (no delete)     |
| `spp_drims.group_drims_approver`                 | Approve or reject supply requests                            |
| `spp_drims.group_drims_manager`                  | Full CRUD including deletion and configuration               |
| `spp_drims.group_drims_warehouse_worker`         | Receive donations, manage stock, process dispatches          |
| `spp_drims.group_drims_field_officer`            | Create requests and confirm deliveries in the field          |
| `spp_drims.group_drims_coordinator_supervisor`   | Coordinate requests and distributions within assigned areas  |

### Extension Points

- Inherit `spp.drims.alert` and override `_cron_check_*` methods to add custom alert types
- Extend `spp.drims.request` and override `_allocate_stock_fifo()` to customize allocation logic
- Add fields to `stock.warehouse` to track additional warehouse metadata for DRIMS operations
- Inherit `spp.drims.donation` and override `_create_receipt_picking()` to customize stock receipt behavior
- Override `spp.drims.request._on_approve()` and `_on_reject()` hooks to add custom approval actions

### Dependencies

`base`, `mail`, `stock`, `spp_alerts`, `spp_security`, `spp_vocabulary`, `spp_area`, `spp_hazard`, `spp_gis`, `spp_gis_report`, `spp_service_points`, `spp_approval`, `spp_cel_domain`, `spp_audit`, `queue_job`
