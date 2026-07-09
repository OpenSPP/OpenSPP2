### 19.0.2.0.8

- fix(views): disable inline creation of CR document types on the Change Request Type "Documents" tab — the `Available Documents` field now only selects existing `cr_document_type` vocabulary codes (`no_create` / `no_quick_create`), matching `Required Documents`. This removes the broken "Create Available Documents" modal (missing Name field) that blocked saving (#1125)

### 19.0.2.0.7

- fix(security): align CR Requestor / CR Local Validator / CR HQ Validator roles with the OP#951 menu audit — replace the `spp_registry.group_registry_read` (Tier-3, no menu) link with `spp_registry.group_registry_viewer` so these roles see the Registry menu; add `spp_hazard.group_hazard_viewer` so they retain Hazard visibility once the menu root is gated. Adds `spp_hazard` to module dependencies.

### 19.0.2.0.6

- fix(views): route post-submit CRs (pending / approved / applied / rejected) through the stage review form when opened from the list, matching the Edit Details → Upload Documents → Review & Submit breadcrumb workflow used for fresh CRs (#920 round-2). Demo-generated CRs in "Applied" state previously landed on the legacy main form view from the list — now they open in `spp_change_request_review_form` like manually-created CRs. Adds the missing `_action_open_review_form` / `_action_open_documents_form` helpers and wires `action="action_open_stage_form" type="object"` on the CR list so row-click goes through the stage router.

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
