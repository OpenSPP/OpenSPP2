### 19.0.2.0.0

- Re-add the PII data encryption migration wizard (Settings > Key Management > PII Encryption >
  Data Migration): scans the classification registry (`spp_data_classification`, new dependency)
  for PII fields on encryption-capable models, previews the workload with a dry run, and encrypts
  legacy plaintext values in place, batch by batch, with per-record error isolation
- The wizard intentionally ships without the in-app rollback and plaintext backup table it had in
  openspp-modules: the rollback never worked (it relied on a `skip_encryption` context no code
  implements) and a plaintext backup of the very values being encrypted contradicts ADR-012's
  threat model. Take a database snapshot before migrating
- fix: a migration run now processes every batch until each field is exhausted (previously only
  the first `batch_size` records were touched while the summary claimed completion)
- fix: scanning a model the operator cannot read is logged and skipped instead of aborting the
  whole scan
- fix: give `spp.field.encryption.config`'s `model_name` an explicit "Model Name" label — the
  related field inherited ir.model's "Model" string and made Odoo warn about a label clash on
  every registry load

### 19.0.1.0.0

- Initial migration to OpenSPP2 (encryption core: encrypted-field mixin, blind-index search,
  field configuration, PII access audit log, masked-field widget)
