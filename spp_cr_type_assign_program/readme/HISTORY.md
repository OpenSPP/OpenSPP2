### 19.0.1.0.2

- fix(security): add record rules to `spp.cr.detail.assign_program` enforcing parent change-request ownership and area scope. The model previously had an ACL granting `group_cr_user` write/create but no record rule, so a CR user could re-point `program_id` on assign-program details of change requests they do not own via RPC.

### 19.0.1.0.0

- New module `spp_cr_type_assign_program` with the `assign_program` change request type.
- Detail model `spp.cr.detail.assign_program` with live program-domain filtering based on the registrant's target type.
- Apply strategy `spp.cr.apply.assign_program` that creates a draft `spp.program.membership` record on apply.
- Conflict rule that blocks duplicate in-flight assignments to the same `(registrant, program)` pair.
