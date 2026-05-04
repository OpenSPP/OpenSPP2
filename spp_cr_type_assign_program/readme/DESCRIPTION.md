Adds a single change request type — `assign_program` — that records a registrant
being assigned to a program. The change request runs through the standard
approval, conflict-detection, and document workflow provided by
`spp_change_request_v2`. On apply, an `spp.program.membership` record is
created in the `draft` state for the `(registrant, program)` pair.

### Beneficiary semantics

The CR's registrant **is** the program beneficiary. There is no "select a member
of the household" step.

- Registrant is a group (household) → eligible programs are those with
  `target_type='group'` and `state='active'`. The household itself is enrolled.
- Registrant is an individual → eligible programs are those with
  `target_type='individual'` and `state='active'`. The individual is enrolled.

Standalone individuals (registrants not in any household) are supported.

To enroll a specific member of a household (not the household itself), open
that member's individual record and start a change request from there — the
CR's registrant is the member, and the form filters programs to those
targeting individuals.

### Models defined by this module

| Model | Kind | Purpose |
| ----- | ---- | ------- |
| `spp.cr.detail.assign_program` | Model | Captures the program selection for the CR |
| `spp.cr.apply.assign_program` | AbstractModel | Apply strategy that creates the membership |

### Validation rules (apply-time)

The apply strategy refuses the operation when any of the following hold:

- the registrant is `disabled`
- the program is not in `state='active'`
- the program's `target_type` does not match the registrant
- a membership for the same `(registrant, program)` pair already exists
- the detail record has no `program_id` set

### Conflict detection

Two in-flight `assign_program` change requests targeting the same
`(registrant, program)` pair are treated as conflicting and the second
submission is blocked. Two CRs for the same registrant but different programs
are independent and both proceed.

### Dependencies

- `spp_change_request_v2`
- `spp_programs`
