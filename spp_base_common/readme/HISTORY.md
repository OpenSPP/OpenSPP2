### 19.0.2.0.3

- fix(ui): the form view's **New** button respects Odoo's create guard again. The `web.FormView` extension that lets a module hide the button with `hideFormCreateButton` replaced the button's condition instead of extending it, dropping Odoo's `canCreate`. As a result every form opened with create disabled — `{'create': False}` in the action context, `create="0"` on the form arch, a role without create access, or `preventCreate` — still rendered a working **New** button that opened a blank editable record, or failed with an access error on save. The condition is now `canCreate and !hideFormCreateButton`: the flag can only hide the button, never show it, and modules using it keep working unchanged. Forms shown in dialogs use a separate template and were never affected (#582).

### 19.0.2.0.2

- test: add a regression test guarding the PDF backend selected by `odoo.tools.pdf`. The Docker image accidentally shipped legacy PyPDF2 3.x next to pypdf; Odoo prefers PyPDF2 when importable, and its removed 1.x API (`numPages`/`getPage`) crashes multi-record PDF printing with a `DeprecationError` (OP#1168). The fix is in `docker/Dockerfile` (`--no-deps` on the Odoo editable install); this test fails on any image that regresses.

### 19.0.2.0.1

- fix(security): add `groups="base.group_system"` to the existing `<menuitem id="base.menu_management" />` override in `views/main_view.xml`. Out of the box the Apps top-level menu has no group restriction and is visible to every logged-in user, violating the OP#951 audit's `Apps: no` rows. The override here is the single authoritative declaration for this menu's attributes in the OpenSPP install (sequence, custom OpenSPP icon, and now group_ids); doing the gating anywhere upstream (e.g. a `post_init_hook` in `spp_security`) is unreliable because this `<menuitem>` reload re-writes the record without a `groups` attribute and resets `group_ids` to empty.

### 19.0.2.0.0

- Initial migration to OpenSPP2
