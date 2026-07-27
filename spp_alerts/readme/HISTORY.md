### 19.0.2.0.1

- fix(security): evaluate each alert rule's monitored search as the user who
  configured what the rule targets (new system-managed `eval_as_user_id`, re-bound
  to the editor whenever a targeting field changes) instead of the elevated
  cron/superuser identity, so record rules bound what a rule can surface to that
  user's own visibility. A non-admin Alerts Manager can no longer author — or
  repoint an admin-authored rule — to leak records they are not allowed to see via
  the alerts the cron creates. The search now also runs in that user's own company
  scope rather than the triggering cron's default company.

### 19.0.2.0.0

- Initial migration to OpenSPP2
