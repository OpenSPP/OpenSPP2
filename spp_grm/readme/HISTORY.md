### 19.0.2.0.2

- fix(security): portal users can now only access their OWN grievance tickets. The
  ``spp.grm.ticket`` portal access was read/write/create with no record rule, so any portal user
  could read and rewrite every grievance in the system over RPC (#380). Added a portal record rule
  scoping to the user's own partner and reduced the portal access-control entry to read-only
  (submission is handled by the sudo'd portal controller, which needs no direct model write). The
  rule covers all four operations, so the scoping also holds if a future access-control change
  ever re-grants portal write.
- fix: SLA-breach handling (auto-escalation and the breach chatter note) no longer runs inside
  the stored ``sla_status`` compute. It is deferred to the end of the triggering transaction, so
  the escalation engine's writes, savepoints and flushes never execute mid-computation. Same
  transaction, same outcome. An unsaved form edit queues nothing: the compute also runs on the
  pseudo-record of an onchange, whose ids resolve back to the real ticket, which would have
  escalated it for a change the user never saved.

### 19.0.2.0.1

- fix(views): gate the "Helpdesk" top-level menu (`spp_grm_ticket_main_menu`) on `group_grm_viewer`. Previously the root menu had no `groups=` attribute and was visible to every logged-in user; the OP#951 menu audit requires several roles to NOT see it (Registry Viewer, Global Finance, Global Program Manager, Program Viewer/Validator/Cycle Approver, Global Registrar, CR roles, Farm User/Manager).

### 19.0.2.0.0

- Initial migration to OpenSPP2
