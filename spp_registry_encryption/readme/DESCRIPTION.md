Applies OpenSPP's PII display protections to the registry: registrant ID numbers (national IDs, passports, and other `spp.registry.id` values) render masked in the Identity tabs of the individual and group forms, with an audited reveal for authorized users.

### What it does

- ID numbers display as `••••-••••-1234` (mask pattern `****-****-####`) instead of plaintext
- Clicking reveal shows the value only for members of `spp_data_classification.group_pii_full_access_admin` — the PII access group the RESTRICTED classification level points at
- Every reveal is recorded in the PII access audit log (`spp.pii.audit.log`, action `reveal`)

### What it does NOT do

Display masking only. The stored values are not encrypted by this module — applying `spp.encrypted.field.mixin` to `spp.registry.id` (blind-index search, encrypted storage) is a separate change with search/deduplication impact.

### UI Location

- Individual form > Identity tab > Identity Documents
- Group form > Identity tab > Identity Documents

### Security

No models and no ACLs of its own. Reveal authorization uses `spp_data_classification.group_pii_full_access_admin`; grant that group to the officers who legitimately need to read full ID numbers.

### Dependencies

`spp_registry`, `spp_pii_encryption`, `spp_data_classification`
