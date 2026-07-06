### 19.0.3.0.0

- feat(change_request): redesign the group/membership CR flows (#242) — Create Group (#876), Add Member now searches an existing member (#871), Remove Member first-page/review cleanup (#872), Change Head of Household via a per-member role table (#873), and Split Household as a relational member move with single-head validation (#877). Review pages render the real data as tables / detail sections.
- **Breaking:** the Add Member detail no longer exposes the create-a-new-individual fields (`created_individual_id`, `given_name`, `family_name`, `birthdate`, `gender_id`, `relationship_id`); downstream modules that extended the old flow must adapt (see #1133).

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
