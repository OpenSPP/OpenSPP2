## 19.0.1.0.0 (2026-05-04)

### Added

- New module `spp_cr_type_assign_program` with the `assign_program` change
  request type.
- Detail model `spp.cr.detail.assign_program` with live program-domain
  filtering based on the registrant's target type.
- Apply strategy `spp.cr.apply.assign_program` that creates a draft
  `spp.program.membership` record on apply.
- Conflict rule that blocks duplicate in-flight assignments to the same
  `(registrant, program)` pair.
