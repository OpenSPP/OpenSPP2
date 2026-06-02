Notary evidence integration for CEL external data providers.

This module adds Notary evidence support:

- `notary` provider kind on `spp.data.provider`
- `spp.notary.claim` catalog rows
- Preview-and-confirm catalog sync with internal variable collision checks
- User-facing CEL evidence paths such as `r.evidence.<provider>.<claim>`
- Stable internal claim-to-variable naming for provider-scoped cache keys
- Live Notary evaluate and batch-evaluate hooks
- Provider-scoped cache writes, stale-cache-with-audit fallback, raise, and null policies
- Security groups, ACLs, forms, menus, and sync wizard

Use Notary claims in CEL with explicit evidence paths, for example
`r.evidence.registry_lab_civil_notary.person_is_alive == true` or
`members.exists(m, m.evidence.registry_lab_civil_notary.person_is_alive == true)`.

The generated flat `notary_<provider>_<claim>` variable remains an internal
metric/cache key. It is shown for debugging, but new eligibility expressions
should use the explicit `r.evidence...` or `m.evidence...` form.

When a registrant has no local subject ID, or the upstream Notary returns
subject-not-found for that ID, the claim evaluates as no evidence for that
registrant instead of failing the whole preview or enrollment run.
