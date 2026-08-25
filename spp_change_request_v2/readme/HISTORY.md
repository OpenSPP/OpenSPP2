### 19.0.3.1.9

- fix(security): duplicate detection now scores the fields both change requests actually propose to change, instead of demanding the two derived change sets be identical. Because a dynamic-approval type applies only the routed field, a requester could add a throwaway edit to another mapped field, make the two sets unequal and drop similarity to zero, while apply discarded that edit — so the evasion cost nothing. Similarity is now computed over the shared changed fields, proportionally, on the same scale the static path uses, which also stops a mostly identical multi-field request collapsing to zero as soon as one shared field differs. The change set is still derived from the detail-versus-registrant diff and never from the requester-writable `selected_field_name` / `field_to_modify`.

### 19.0.3.1.8

- fix(security): scope the Create-Group member wizards to the parent change request. `spp.cr.detail.create_group.member.wizard` and its `.phone` / `.bank` children are transient models whose access-control entries grant change-request users read, write, create **and** delete, and no record rule covered them. Transient models get no implicit creator-only scoping from the ORM — `ir.rule` applies to them as it does to persistent models, and with no rule the domain resolves to true — so any change-request user could enumerate, read, alter or delete another user's proposed-member data, including names, birthdates, phone numbers and bank account numbers. Each wizard model now carries the same parent-change-request ownership rules as the persistent Create-Group detail rows, scoped on every operation its access-control entry grants.

### 19.0.3.1.7

- fix(security): require change-request manager rights to apply a change request. `action_apply()` runs the apply strategy with elevated rights and is callable over RPC, but the manager restriction existed only on the review button — so a change-request user could apply their own approved request and drive privileged writes such as membership changes. The public entry point is now gated and the mechanism moved to an internal method, so approval-driven auto-apply is unaffected. **Deployments using the API v2 change-request endpoints must grant the API user the change-request manager role to keep using the apply endpoint.**

### 19.0.3.1.6

- fix(security): derive conflict and duplicate detection from the change actually proposed rather than a user-writable label. `selected_field_name` and the detail's `field_to_modify` are both writable by the requester, so either could be re-pointed at an unchanged field to clear a field-scoped conflict or drop duplicate similarity to zero. Detection now compares the detail against the registrant. Types whose apply strategy writes outside the configured field mappings fall back to the full configured field set instead of an empty one, so detection cannot silently disable itself.

### 19.0.3.1.5

- fix(security): scope the CR Requestor, Local Validator and HQ Validator roles to Tier-3 registry read instead of Tier-2 registry viewer. The viewer tier gates the Registry Search portal, a broad registrant-PII enumeration surface these change-request roles do not need; registrant read access is unchanged. A migration re-points the roles and resynchronises existing users, since the role definitions are `noupdate`.

### 19.0.3.1.4

- fix(security): add ownership and area record rules to every concrete change-request detail model. Detail rows were reachable by any `group_cr_user` regardless of who owned the parent change request, so a requester could read or tamper with another user's detail data over RPC. Each detail model now carries user/validator/validator-HQ/manager rules scoped through its parent change request, plus a global rule mirroring the parent's area filter. `spp.cr.detail.split_household.member` is additionally scoped on delete, the one detail model whose access-control entry grants `unlink` to change-request users: requesters may delete member rows only on their own requests, while validators and managers keep the unrestricted delete their access-control entries grant.

### 19.0.3.1.3

- fix(security): route and apply the same single field for dynamic-approval change requests, and freeze the proposed change once the request leaves draft. The selected field, its old/new values and the detail pointer were writable after submission, so a requester could re-route an approval or alter the value that had already been approved. Note the mapped-source-field freeze applies to `field_mapping` request types; `custom`-strategy types freeze only the routing selector.

### 19.0.3.1.2

- fix(change_request_v2): adding an ID now looks for a live one of that type rather than any row at all, so an ID that was removed through a change request no longer blocks adding a replacement of the same type (#1136)

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
