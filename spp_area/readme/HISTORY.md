### 19.0.2.0.3

- fix(views): follow the `base_user_role` rename of `res.users.role_ids` to `user_role_ids` (OCA/server-backend #428). The user form override inserted the center-areas group before `role_ids`, which no longer exists in the parent view, so the module failed to install.

### 19.0.2.0.2

- fix(security): grant `group_area_viewer` (read-only) to spp_user_roles support roles (Global Support, Global Support Manager, Local Support) so they can browse area records per the OP#951 menu audit.

### 19.0.2.0.1

- fix(security): add a global `ir.rule` on `res.partner` that filters registrants by `area_id` for users with `center_area_ids` set (OP#989). Replaces the limited `search_read` / `web_search_read` override in `models/registrant.py` which missed `name_search` (Many2one dropdowns), `search_count`, `read_group`, and related-field traversal. The rule's conditional domain is a no-op for users without center areas (global roles).

### 19.0.2.0.0

- Initial migration to OpenSPP2
