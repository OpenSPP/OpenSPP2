### 19.0.2.0.1

- fix(security): drop the Program Manager → `group_studio_viewer` extension per the OP#951 menu audit (Program Manager should NOT see the Studio top-level menu). Removes `data/user_roles.xml` from the module entirely; System Admin retains Studio visibility via `spp_security.group_spp_admin` → `group_studio_manager` (wired in `spp_studio/security/groups.xml`).

### 19.0.2.0.0

- Initial migration to OpenSPP2
