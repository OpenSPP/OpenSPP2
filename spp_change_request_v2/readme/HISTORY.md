### 19.0.2.0.5

- fix(security): add a global `ir.rule` on `spp.change.request` that filters by `registrant_id.area_id` against the user's `center_area_ids` (OP#989 round-2). The earlier `_prepare_domain` override only caught `search_read` / `web_search_read` and missed the registrant Many2one picker (which uses `name_search` → `_search`), so users could still select out-of-area registrants. The conditional domain is a no-op for users with no center areas (global roles).

### 19.0.2.0.3

- fix: add HTML escaping to all computed Html fields with `sanitize=False` to prevent stored XSS (#50)

### 19.0.2.0.2

- fix: fix batch approval wizard line deletion (#130)

### 19.0.2.0.1

- fix: skip field types before getattr and isolate detail prefetch (#129)

### 19.0.2.0.0

- Initial migration to OpenSPP2
