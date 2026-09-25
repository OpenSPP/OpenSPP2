### 19.0.2.2.0

- fix: search filters fail closed (#554). A filter that names nothing (an unknown `group`, `gender`, `membership-role` or `member`) now returns no results instead of silently dropping out and returning the whole registry. Malformed filters (`identifier`, `group`, `gender`, `birthdate`, `_lastUpdated` without the expected format; `member` not an `Individual/{system}|{value}` reference) return `400` on `GET /Individual` and `GET /Group`.
- fix: multi-condition search filters apply to one related row (#554). `GET /Individual?group=` no longer lists someone who left the group but is active in another; `membership-role=` requires the role on an active membership; `identifier=` requires system and value on the same ID. Behaviour change: `GET /Group?member=` now lists only groups the individual is an active member of.
- fix: returned references can be followed (#554). `Group.member[].entity`, the `group`/`entity` references in `$add-member`, `$remove-member` and member-update responses, membership-history `member`, and `Individual.groupMembership[].group` were built from the identifier type's vocabulary namespace (`urn:openspp:vocab:id-type|…`) and could not be resolved; they now use the full code URI (`urn:openspp:vocab:id-type#<code>|…`), the same value as `identifier[].system`.
- fix: ending a membership "now" takes effect immediately (#554). `$remove-member` without `endedDate`, and the member moves in group merge and split, wrote the end time with microseconds, which the `is_ended`/`status` computes (second precision) treated as a moment in the future: the membership stayed active until the repair cron ran. They now use the ORM's clock (`fields.Datetime.now()`).
- fix: identifiers are resolved to exactly one registrant (#554). `POST /Individual`, `POST /Group`, `$split` and create entries in `$batch` bundles return `409` when an identifier (type + value) is already live on another registrant, instead of creating a second record no lookup could tell apart; an archived registrant still holds its identifiers (mark the ID invalid to free it). Lookups no longer pick one of several registrants holding an identifier: read, update, patch, member operations, merge/split and `$batch`/transaction bundles return `409`; a client that requires consent and may not read every match gets the same `403` as for a registrant that does not exist (bundles, which do no consent filtering, always answer `409`). Search filters naming an ambiguous identifier (`group=`, `member=`) return `409`, or an empty page for such a client; bulk export reports the identifier with item status `error` (or `access_denied`). Individual endpoints and the `member=` filter resolve individuals only, and Group endpoints groups only, so a value held by one individual and one group is not ambiguous, and `GET /Individual/{id}` no longer returns a group. Soft-removed (`invalid`) IDs no longer resolve, are no longer listed in `identifier[]` and are not matched by `identifier=`; references are built from a live ID, and a registrant with no live ID is left out of `Group.member[]`, membership history and `/Individual/{id}/groups`. Searching by `identifier=` still lists every registrant holding a live match.

### 19.0.2.1.1

- chore(api_v2): the API V2 configuration menu moved from Registry > Configuration to Settings > Registry, alongside the other superuser configuration (#1009)

### 19.0.2.1.0

- Add OpenAPI polymorphic schema utilities (`utils/openapi_polymorphic.py`): `polymorphic_body()` for declaring dict-typed fields that accept one of several Pydantic models, plus an app-level OpenAPI hook that injects the corresponding `oneOf` schemas into the generated document
- Auth middleware: replace the plain `HTTPBearer` scheme with an OAuth2 client-credentials security scheme so the OpenAPI document advertises the token endpoint and consumers (Swagger UI, QGIS, etc.) can discover how to authenticate. The advertised `tokenUrl` is absolutized against the endpoint's mount path at generation time so strict RFC 3986 clients resolve it correctly. The `Bearer` prefix is stripped from the Authorization header when present; a raw token without the prefix is also accepted
- Bundle schemas: registrant-serving endpoints document bundle entries as polymorphic Individual/Group bodies via new `RegistrantBundle`/`RegistrantBundleEntry` subtypes, so their payloads are fully described in the OpenAPI document; the shared `BundleEntry` stays generic because other modules reuse it for non-registrant resources
- Add OpenAPI contract tests covering bundle schema rendering, the polymorphic utilities, and the overall OpenAPI document contract

### 19.0.2.0.1

- Fix `SerializationFailure` race when multiple Odoo workers rebuild their routing map simultaneously (e.g. after `-u all`) and all try to sync the same `fastapi.endpoint` rows
- Serialize concurrent sync attempts across workers using a transaction-scoped Postgres advisory lock; workers that don't acquire the lock skip the sync and pick up the freshly synced routes on the next routing-map rebuild (via `endpoint_route_version` cache invalidation)
- Log skipped syncs at INFO and lock-primitive failures at WARNING so cold-start route-availability symptoms and broken-primitive regressions are diagnosable without raising the global log level

### 19.0.2.0.0

- Initial migration to OpenSPP2
