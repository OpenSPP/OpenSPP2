### 19.0.2.2.0

- fix: search filters fail closed (#554). A filter that names nothing (an unknown `group`, `gender`, `membership-role` or `member`) now returns no results instead of silently dropping out and returning the whole registry. Malformed filters (`identifier`, `group`, `gender`, `birthdate`, `_lastUpdated` without the expected format; `member` not an `Individual/{system}|{value}` reference) return `400` on `GET /Individual` and `GET /Group`.
- fix: multi-condition search filters apply to one related row (#554). `GET /Individual?group=` no longer lists someone who left the group but is active in another; `membership-role=` requires the role on an active membership; `identifier=` requires system and value on the same ID. Behaviour change: `GET /Group?member=` now lists only groups the individual is an active member of.
- fix: returned references can be followed (#554). `Group.member[].entity`, the `group`/`entity` references in `$add-member`, `$remove-member` and member-update responses, membership-history `member`, and `Individual.groupMembership[].group` were built from the identifier type's vocabulary namespace (`urn:openspp:vocab:id-type|…`) and could not be resolved; they now use the full code URI (`urn:openspp:vocab:id-type#<code>|…`), the same value as `identifier[].system`.
- fix: ending a membership "now" takes effect immediately (#554). `$remove-member` without `endedDate`, and the member moves in group merge and split, wrote the end time with microseconds, which the `is_ended`/`status` computes (second precision) treated as a moment in the future: the membership stayed active until the repair cron ran. They now use the ORM's clock (`fields.Datetime.now()`).
- fix: identifiers are resolved to exactly one registrant (#554). `POST /Individual` and `POST /Group` return `409` when an identifier (type + value) is already live on another registrant, instead of creating a second record no lookup could tell apart. Lookups (read, update, patch, member operations, merge/split, search filters, bulk export, batch/transaction bundles) no longer pick one of several registrants holding an identifier: they return `409`, or, for a client that requires consent and lacks it for any of the matches, the same `403` as a registrant that does not exist. Soft-removed (`invalid`) IDs no longer resolve, and references are built from a live ID. Searching by `identifier=` still lists every match.

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
