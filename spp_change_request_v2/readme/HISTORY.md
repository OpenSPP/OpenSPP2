### 19.0.2.0.4

- fix(views): route post-submit CRs (pending / approved / applied / rejected) through the stage review form when opened from the list, matching the Edit Details → Upload Documents → Review & Submit breadcrumb workflow used for fresh CRs (#920 round-2). Demo-generated CRs in "Applied" state previously landed on the legacy main form view from the list — now they open in `spp_change_request_review_form` like manually-created CRs. Adds the missing `_action_open_review_form` / `_action_open_documents_form` helpers and wires `action="action_open_stage_form" type="object"` on the CR list so row-click goes through the stage router.

### 19.0.2.0.3

- fix: add HTML escaping to all computed Html fields with `sanitize=False` to prevent stored XSS (#50)

### 19.0.2.0.2

- fix: fix batch approval wizard line deletion (#130)

### 19.0.2.0.1

- fix: skip field types before getattr and isolate detail prefetch (#129)

### 19.0.2.0.0

- Initial migration to OpenSPP2
