### 19.0.4.0.0

- feat(drims): Donations review — creation, receipt, inspection and follow-up. Donations start in a new **Draft** state; the donor list is limited to organisations whose role is Donor and a donation cannot be recorded against a closed incident; at least one item is required to save, Pledged must be entered and be greater than zero, and Received is entered manually rather than copied from Pledged. Line columns appear progressively through the lifecycle (Received and Variance from Announced; Condition and Action from Inspected), non-accepted items gain a follow-up/disposal trail, and adding an item is blocked once the donation has moved past its editable states (#1055, #1058, #1108, #1163)
- **Breaking:** the donation line's **Description** field is removed. It was replaced by the product and quantity columns during this rework; the database column is left in place, so existing values are retained but no longer readable through the ORM or shown in any view (#1076)

### 19.0.3.0.0

- feat(drims): allocate stock per source warehouse. The Allocate Stock wizard now auto-splits each requested line across the DRIMS warehouses that hold stock (e.g. 70 → 50 @ WH1 + 20 @ WH2) with editable rows; the split is captured on a new per-warehouse allocation record, shown on the request's Allocations tab and summarised in a "Source Warehouse(s)" column on the Requests list; dispatch creates one picking per source warehouse. The single "Source Warehouse" field on the request has been removed — the warehouse(s) are chosen in the wizard. The allocation wizard distinguishes no-stock, stock-shortfall and deliberate partial-allocation cases with clear messages, and the request line's Fulfillment % tracks allocated ÷ requested so the bar reflects allocation progress (#1079)
- feat(drims): Requests review UI/UX overhaul — post-approval fulfillment lanes, allocation shortfall indicators, and a destination-type selector (#1075)

### 19.0.2.0.0

- Initial migration to OpenSPP2
