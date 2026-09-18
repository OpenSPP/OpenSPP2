### 19.0.2.0.3

- fix: make the menu-icon decoration run by `ir.module.module.next()` best-effort (#383). The pass now runs in its own savepoint and any `psycopg2.Error` is logged and skipped instead of propagating out of the module operation and leaving the transaction aborted; missing menu xmlids use `raise_if_not_found=False`. Decorating app icons is cosmetic and must never take down the process that triggered it.

### 19.0.2.0.2

- test: add a regression test guarding the PDF backend selected by `odoo.tools.pdf`. The Docker image accidentally shipped legacy PyPDF2 3.x next to pypdf; Odoo prefers PyPDF2 when importable, and its removed 1.x API (`numPages`/`getPage`) crashes multi-record PDF printing with a `DeprecationError` (OP#1168). The fix is in `docker/Dockerfile` (`--no-deps` on the Odoo editable install); this test fails on any image that regresses.

### 19.0.2.0.1

- fix(security): add `groups="base.group_system"` to the existing `<menuitem id="base.menu_management" />` override in `views/main_view.xml`. Out of the box the Apps top-level menu has no group restriction and is visible to every logged-in user, violating the OP#951 audit's `Apps: no` rows. The override here is the single authoritative declaration for this menu's attributes in the OpenSPP install (sequence, custom OpenSPP icon, and now group_ids); doing the gating anywhere upstream (e.g. a `post_init_hook` in `spp_security`) is unreliable because this `<menuitem>` reload re-writes the record without a `groups` attribute and resets `group_ids` to empty.

### 19.0.2.0.0

- Initial migration to OpenSPP2
