Notary evidence catalog skeleton for CEL external data providers.

This module adds catalog-only plumbing for Notary evidence:

- `notary` provider kind on `spp.data.provider`
- `spp.notary.claim` catalog rows
- Stable claim-to-variable naming helper
- Mockable catalog sync entry point
- Security groups, ACLs, views, and sync wizard

It deliberately does not add executor behavior or live Notary evaluation.
