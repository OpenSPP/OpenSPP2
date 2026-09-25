### 19.0.1.1.0

- fix: `GET`/`PUT /ProgramMembership/{identifier}` no longer resolve to an arbitrary program's membership when the beneficiary is enrolled in several programs (#554). A new optional `program` query parameter (`Program/{system}|{value}`) selects the membership (a malformed value returns `400`, an unknown program `404`); without it, a beneficiary with more than one membership returns `409`. When no single membership resolves, a client that requires consent and may not read the beneficiary gets `403` whatever the reason (unknown beneficiary, not enrolled in that program, several memberships), so neither the registry's contents nor enrollments are revealed; the `409` message does not give the number of memberships.
- fix: `PUT /ProgramMembership` can no longer move a membership to another program or beneficiary: a body whose `program` or `beneficiary` differs from the addressed membership returns `422` (#554).
- fix: the `Location` header of `POST /ProgramMembership` is URL-encoded and carries `?program=`, so following it returns the created membership (#554).
- fix: `PUT /ProgramMembership` accepts its own `ETag`/`meta.versionId` in `If-Match`; it previously compared against a different timestamp format and always returned `409` (#554).
- fix: a beneficiary identifier held by more than one registrant is refused on `GET`/`PUT`/`POST /ProgramMembership` (`409`, or `403` for a client that requires consent and may not read every match) and in the `beneficiary` search filter (`409`, or an empty page for such a client), instead of acting on an arbitrary one; `Individual/` and `Group/` beneficiary references resolve only that kind. Membership identifiers, beneficiary references and `Location` use only live (not soft-removed) IDs (#554).

### 19.0.1.0.0

- Split program and program-membership REST endpoints out of `spp_api_v2` into this companion module (#1081), so `spp_api_v2` no longer depends on `spp_programs`.
