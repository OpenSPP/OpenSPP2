Applies OpenSPP's PII display de-emphasis to the registry: registrant ID numbers (national IDs, passports, and other `spp.registry.id` values) render masked in the Identity tabs of the individual and group forms, with an audited reveal control.

### What it does

- ID numbers display as `••••-••••-1234` (mask pattern `****-****-####`, matching the mask the classification registry seeds for national IDs) instead of plaintext
- The reveal control checks membership in `spp_data_classification.group_pii_full_access_admin` — the PII access group the RESTRICTED classification level points at
- Every reveal through the control is recorded in the PII access audit log (`spp.pii.audit.log`, action `reveal`)

### What it is — and is not

This is **display de-emphasis, not an access control** (see the "widget honesty" findings in the `spp_pii_encryption` hardening tracker):

- The masking applies to readonly display. Entering the editable list cell shows the value in the input, without a group check or an audit entry.
- The value is delivered to the browser by the normal record read regardless of mask state; the widget controls presentation, not data access.
- The real access boundary remains the record's ACLs and record rules: whoever can read/write `spp.registry.id` can obtain the value.
- What the mask does buy: protection against shoulder-surfing and casual over-exposure in day-to-day screens, plus an audit trail for deliberate reveals through the control.

Server-side field-level enforcement is tracked in the `spp_pii_encryption` hardening issue; when it lands, this module is where the registry adopts it.

### What it does NOT do

The stored values are not encrypted by this module — applying `spp.encrypted.field.mixin` to `spp.registry.id` (blind-index search, encrypted storage) is a separate change with search/deduplication impact.

### UI Location

- Individual form > Identity tab > Identity Documents
- Group form > Identity tab > Identity Documents

### Security

No models and no ACLs of its own. The reveal control's group is `spp_data_classification.group_pii_full_access_admin`; grant it to officers who legitimately need to read full ID numbers. Note the mask shows the last 4 characters to anyone who can read the record.

### Dependencies

`spp_registry`, `spp_pii_encryption`, `spp_data_classification`
