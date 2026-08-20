### 19.0.4.0.4

- fix(drims): name constants after codes the vocabulary actually ships, and fix the three places that used the wrong ones. An urgent request answered a 24-hour approval SLA instead of 8 hours, the priority badge and list decorations never fired, and the High Priority search filter always returned nothing — all because the code asked for priorities the data does not contain. A test now walks every code constant against its vocabulary, so one naming a code that does not exist fails the build instead of silently matching nothing (#1165)

### 19.0.4.0.3

- fix(drims): show only the states a dispatch can reach on its status bar. A request dispatch is confirmed the moment it is created, so Draft never applies to it; the shared status bar keeps Draft for every other outgoing transfer. Waiting is hidden as a future step but still shows when a dispatch is actually in it (#1086)

### 19.0.4.0.2

- feat(drims): confirm a delivery through a popup rather than the dispatch form. Confirm Delivery now collects the receiver, signature, photos and GPS together with what actually arrived per line, and records the delivered quantities against the request so fulfilment reflects what was received rather than what was sent (#1088)

### 19.0.4.0.1

- fix(drims): only let a dispatch ship what its request approved. Products cannot be added to a request dispatch and quantities cannot be raised past what was allocated — enforced on the model, so imports and API callers are covered too, with the Operations tab's Add a line and delete affordances hidden to match (#1057)

### 19.0.4.0.0

- feat(drims): Donations review — creation, receipt, inspection and follow-up. Donations start in a new **Draft** state; the donor list is limited to organisations whose role is Donor and a donation cannot be recorded against a closed incident; at least one item is required to save, Pledged must be entered and be greater than zero, and Received is entered manually rather than copied from Pledged. Line columns appear progressively through the lifecycle (Received and Variance from Announced; Condition and Action from Inspected), non-accepted items gain a follow-up/disposal trail, and adding an item is blocked once the donation has moved past its editable states (#1055, #1058, #1108, #1163)
- **Breaking:** the donation line's **Description** field is removed. It was replaced by the product and quantity columns during this rework; the database column is left in place, so existing values are retained but no longer readable through the ORM or shown in any view (#1076)

### 19.0.3.1.0

- feat(drims): Incident Management review — incidents are entered as a **Draft** and then flagged Alert or set Active, a closed incident refuses DRIMS operations and no longer accepts lifecycle changes, dashboard KPI cards no longer open the record when a box is clicked, warehouses can be linked to an incident and drive the warehouse choices on donations and requests, and the Impact tab is hidden where it does not apply (#1094, #1123, #1157, #1158, #1159, #1160, #1164)
- fix(drims): incident stock KPIs now count incident-related stock net of allocations, and distributed value is net of confirmed returns. Both are stored computes whose meaning changed, so upgrading recomputes them for every incident — including closed ones, which the refresh cron skips (#1100)

### 19.0.3.0.4

- feat(drims): rework the dispatch page and correct the waybill. **Dispatch & Delivery** leads the form instead of sitting behind Additional Info, a dispatch shows its destination location rather than an empty Delivery Address, and everything the request already decided — operation type, source document, source location and the DRIMS fields — is locked, with Quantity left editable so a partial dispatch and its backorder can still be produced. The waybill prints on one page with the signature block intact and the TO box filled in (#1150, #1151)
- **Deployment note:** the waybill's barcode needs the `rlPyCairo` renderer, added to `docker/requirements.txt` in this change. Upgrading the module is not enough — the container image has to be **rebuilt**, or every report containing a barcode or QR code answers HTTP 500. The waybill itself still prints without it, minus the barcode (#1151)

### 19.0.3.0.1

- fix(drims): a dispatch validated short no longer leaves the request looking fully dispatched. The backorder is announced on the request with a to-do for the coordinators, the request reopens as Ready for Dispatch so the remaining balance can be dispatched again, and the dispatched totals are rebuilt on the allocation rows. Applies however the transfer is validated — the web client, the barcode flow or the API (#1087)

### 19.0.3.0.0

- feat(drims): allocate stock per source warehouse. The Allocate Stock wizard now auto-splits each requested line across the DRIMS warehouses that hold stock (e.g. 70 → 50 @ WH1 + 20 @ WH2) with editable rows; the split is captured on a new per-warehouse allocation record, shown on the request's Allocations tab and summarised in a "Source Warehouse(s)" column on the Requests list; dispatch creates one picking per source warehouse. The single "Source Warehouse" field on the request has been removed — the warehouse(s) are chosen in the wizard. The allocation wizard distinguishes no-stock, stock-shortfall and deliberate partial-allocation cases with clear messages, and the request line's Fulfillment % tracks allocated ÷ requested so the bar reflects allocation progress (#1079)
- feat(drims): Requests review UI/UX overhaul — post-approval fulfillment lanes, allocation shortfall indicators, and a destination-type selector (#1075)

### 19.0.2.0.0

- Initial migration to OpenSPP2
