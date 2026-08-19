### 19.0.3.0.2

- fix(drims): only let a dispatch ship what its request approved. Products cannot be added to a request dispatch and quantities cannot be raised past what was allocated — enforced on the model, so imports and API callers are covered too, with the Operations tab's Add a line and delete affordances hidden to match (#1057)

### 19.0.3.0.0

- feat(drims): allocate stock per source warehouse. The Allocate Stock wizard now auto-splits each requested line across the DRIMS warehouses that hold stock (e.g. 70 → 50 @ WH1 + 20 @ WH2) with editable rows; the split is captured on a new per-warehouse allocation record, shown on the request's Allocations tab and summarised in a "Source Warehouse(s)" column on the Requests list; dispatch creates one picking per source warehouse. The single "Source Warehouse" field on the request has been removed — the warehouse(s) are chosen in the wizard. The allocation wizard distinguishes no-stock, stock-shortfall and deliberate partial-allocation cases with clear messages, and the request line's Fulfillment % tracks allocated ÷ requested so the bar reflects allocation progress (#1079)
- feat(drims): Requests review UI/UX overhaul — post-approval fulfillment lanes, allocation shortfall indicators, and a destination-type selector (#1075)

### 19.0.2.0.0

- Initial migration to OpenSPP2
