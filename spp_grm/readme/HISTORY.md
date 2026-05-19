### 19.0.2.0.1

- fix(views): gate the "Helpdesk" top-level menu (`spp_grm_ticket_main_menu`) on `group_grm_viewer`. Previously the root menu had no `groups=` attribute and was visible to every logged-in user; the OP#951 menu audit requires several roles to NOT see it (Registry Viewer, Global Finance, Global Program Manager, Program Viewer/Validator/Cycle Approver, Global Registrar, CR roles, Farm User/Manager).

### 19.0.2.0.0

- Initial migration to OpenSPP2
