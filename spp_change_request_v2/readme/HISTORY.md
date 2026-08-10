### 19.0.3.1.2

- fix(security): route and apply the same single field for dynamic-approval change requests, and freeze the proposed change once the request leaves draft. The selected field, its old/new values and the detail pointer were writable after submission, so a requester could re-route an approval or alter the value that had already been approved. Note the mapped-source-field freeze applies to `field_mapping` request types; `custom`-strategy types freeze only the routing selector.

### 19.0.3.1.1

- fix(change_request): enforce the `(cr_type_id, reason)` uniqueness of per-reason Required-Documents rules with `models.Constraint` (#394). The rule was previously declared via the legacy `_sql_constraints` attribute, which Odoo 19 ignores — the constraint was never created, so duplicate rules for the same reason could be saved silently since 19.0.3.0.0 and one WARNING line was logged on every registry load. A pre-migration removes duplicate rules (the lowest-id rule per pair is kept, matching which rule the runtime applied) so the constraint applies cleanly on upgrade.

### 19.0.3.1.0

- revert(change_request): restore the create-a-new-individual **Add Member** and role-field **Change Head of Household** CR flows (#871, #873). Reinstates the Add Member create-new fields (`created_individual_id` / `given_name` / `family_name` / `birthdate` / `gender_id` / `relationship_id`) on `spp.cr.detail.add_member` and the Change HoH `current_head_id` / `new_head_id` fields on `spp.cr.detail.change_hoh`, along with their detail views and strategies, so downstream modules that extend the old flows load and apply again. Create Group (#876), Remove Member (#872), and Split Household (#877) are unchanged, and the per-reason Required-Documents feature added alongside #873 is retained. Note: the removed `spp_dci_demo` Add Member birth-verification extension is **not** restored here; reinstate separately if needed.

### 19.0.3.0.0

- feat(change_request): redesign the group/membership CR flows (#242) — Create Group (#876), Add Member now searches an existing member (#871), Remove Member first-page/review cleanup (#872), Change Head of Household via a per-member role table (#873), and Split Household as a relational member move with single-head validation (#877). Review pages render the real data as tables / detail sections.
- fix(change_request): Split Household "New Household Information" shows a fillable Address field, and the new-household **Latitude/Longitude** are surfaced with an interactive **map** (`spp_gis`, OSM basemap) to pick/preview the location — the two stay in sync and out-of-range coordinates are rejected. The review page surfaces the coordinates plus the new household's Phone / Bank / ID lines as tables (#877)
- **Breaking:** the Add Member detail no longer exposes the create-a-new-individual fields (`created_individual_id`, `given_name`, `family_name`, `birthdate`, `gender_id`, `relationship_id`); downstream modules that extended the old flow must adapt (see #1133).

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
