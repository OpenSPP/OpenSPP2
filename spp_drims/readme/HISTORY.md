### 19.0.3.0.4

- feat(drims): rework the dispatch page and correct the waybill. **Dispatch & Delivery** leads the form instead of sitting behind Additional Info, a dispatch shows its destination location rather than an empty Delivery Address, and everything the request already decided — operation type, source document, source location and the DRIMS fields — is locked, with Quantity left editable so a partial dispatch and its backorder can still be produced. The waybill prints on one page with the signature block intact and the TO box filled in (#1150, #1151)
- **Deployment note:** the waybill's barcode needs the `rlPyCairo` renderer, added to `docker/requirements.txt` in this change. Upgrading the module is not enough — the container image has to be **rebuilt**, or every report containing a barcode or QR code answers HTTP 500. The waybill itself still prints without it, minus the barcode (#1151)

### 19.0.3.0.0

- feat(drims): allocate stock per source warehouse. The Allocate Stock wizard now auto-splits each requested line across the DRIMS warehouses that hold stock (e.g. 70 → 50 @ WH1 + 20 @ WH2) with editable rows; the split is captured on a new per-warehouse allocation record, shown on the request's Allocations tab and summarised in a "Source Warehouse(s)" column on the Requests list; dispatch creates one picking per source warehouse. The single "Source Warehouse" field on the request has been removed — the warehouse(s) are chosen in the wizard. The allocation wizard distinguishes no-stock, stock-shortfall and deliberate partial-allocation cases with clear messages, and the request line's Fulfillment % tracks allocated ÷ requested so the bar reflects allocation progress (#1079)
- feat(drims): Requests review UI/UX overhaul — post-approval fulfillment lanes, allocation shortfall indicators, and a destination-type selector (#1075)

### 19.0.2.0.0

- Initial migration to OpenSPP2
