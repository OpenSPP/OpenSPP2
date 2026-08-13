### 19.0.2.0.2

- fix(security): portal users can now only access their OWN grievance tickets. The
  ``spp.grm.ticket`` portal access was read/write/create with no record rule, so any portal user
  could read and rewrite every grievance in the system over RPC (#380). Added a portal record rule
  scoping to the user's own partner and reduced the portal access-control entry to read-only
  (submission is handled by the sudo'd portal controller, which needs no direct model write).

### 19.0.2.0.1

- fix(views): gate the "Helpdesk" top-level menu (`spp_grm_ticket_main_menu`) on `group_grm_viewer`. Previously the root menu had no `groups=` attribute and was visible to every logged-in user; the OP#951 menu audit requires several roles to NOT see it (Registry Viewer, Global Finance, Global Program Manager, Program Viewer/Validator/Cycle Approver, Global Registrar, CR roles, Farm User/Manager).

### 19.0.2.0.0

- Initial migration to OpenSPP2
