### 19.0.1.1.0

- fix: `GET`/`PUT /ProgramMembership/{identifier}` no longer resolve to an arbitrary program's membership when the beneficiary is enrolled in several programs (#554). A new optional `program` query parameter (`Program/{system}|{value}`) selects the membership; without it, a beneficiary with more than one membership returns `409`. For a client without consent, the refusal is `403` before any `409`/`404`, so enrollment is not revealed.
- fix: `PUT /ProgramMembership` can no longer move a membership to another program or beneficiary: a body whose `program` or `beneficiary` differs from the addressed membership returns `422` (#554).
- fix: the `Location` header of `POST /ProgramMembership` is URL-encoded and carries `?program=`, so following it returns the created membership (#554).
- fix: `PUT /ProgramMembership` accepts its own `ETag`/`meta.versionId` in `If-Match`; it previously compared against a different timestamp format and always returned `409` (#554).
- fix: a beneficiary identifier held by more than one registrant is refused (`409`, or `403` for a client that requires consent and lacks it for any of them) on `GET`/`PUT`/`POST /ProgramMembership` and the `beneficiary` search filter, instead of acting on an arbitrary one; membership identifiers, beneficiary references and `Location` use only live (not soft-removed) IDs (#554).

### 19.0.1.0.0

- Split program and program-membership REST endpoints out of `spp_api_v2` into this companion module (#1081), so `spp_api_v2` no longer depends on `spp_programs`.
