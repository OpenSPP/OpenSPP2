### 19.0.3.1.0

- feat(drims): Incident Management review — incidents are entered as a **Draft** and then flagged Alert or set Active, a closed incident refuses DRIMS operations and no longer accepts lifecycle changes, dashboard KPI cards no longer open the record when a box is clicked, warehouses can be linked to an incident and drive the warehouse choices on donations and requests, and the Impact tab is hidden where it does not apply (#1094, #1123, #1157, #1158, #1159, #1160, #1164)
- fix(drims): incident stock KPIs now count incident-related stock net of allocations, and distributed value is net of confirmed returns. Both are stored computes whose meaning changed, so upgrading recomputes them for every incident — including closed ones, which the refresh cron skips (#1100)

### 19.0.3.0.0

- feat(drims): allocate stock per source warehouse. The Allocate Stock wizard now auto-splits each requested line across the DRIMS warehouses that hold stock (e.g. 70 → 50 @ WH1 + 20 @ WH2) with editable rows; the split is captured on a new per-warehouse allocation record, shown on the request's Allocations tab and summarised in a "Source Warehouse(s)" column on the Requests list; dispatch creates one picking per source warehouse. The single "Source Warehouse" field on the request has been removed — the warehouse(s) are chosen in the wizard. The allocation wizard distinguishes no-stock, stock-shortfall and deliberate partial-allocation cases with clear messages, and the request line's Fulfillment % tracks allocated ÷ requested so the bar reflects allocation progress (#1079)
- feat(drims): Requests review UI/UX overhaul — post-approval fulfillment lanes, allocation shortfall indicators, and a destination-type selector (#1075)

### 19.0.2.0.0

- Initial migration to OpenSPP2
