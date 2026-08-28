### 19.0.1.0.3

- fix(security): validate server-side that the user selecting a program on
  `spp.cr.detail.assign_program` can actually access it. The `program_id`
  domain only constrained the UI, so a raw RPC write could target a hidden or
  cross-company program; on apply the strategy runs under `sudo`, which would
  assign the membership and leak the program name via preview while bypassing
  program record rules and multi-company scope. An `@api.constrains` now rejects
  a program the writing user cannot see (record rules) or that is outside their
  company scope.
- fix(security): re-assert program access at the apply sink (defense in depth).
  The write-time constraint cannot cover a value it never saw — a record
  written before the constraint shipped (the module is in released tags), an
  import, or a future sudo prefill. The apply strategy now re-checks the
  program against the change-request requester's company scope before creating
  the membership, so a pre-existing out-of-scope `program_id` cannot be applied
  cross-company, and `preview()` (which runs under sudo) redacts the program
  name for such a record rather than leaking it. No-op in single-company
  deployments.

### 19.0.1.0.2

- fix(security): add record rules to `spp.cr.detail.assign_program` enforcing parent change-request ownership and area scope. The model previously had an ACL granting `group_cr_user` write/create but no record rule, so a CR user could re-point `program_id` on assign-program details of change requests they do not own via RPC.

### 19.0.1.0.0

- New module `spp_cr_type_assign_program` with the `assign_program` change request type.
- Detail model `spp.cr.detail.assign_program` with live program-domain filtering based on the registrant's target type.
- Apply strategy `spp.cr.apply.assign_program` that creates a draft `spp.program.membership` record on apply.
- Conflict rule that blocks duplicate in-flight assignments to the same `(registrant, program)` pair.
