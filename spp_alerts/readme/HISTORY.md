### 19.0.2.0.1

- fix(security): evaluate each alert rule's monitored search as the rule's owner
  (`create_uid`) instead of the elevated cron/superuser identity, so record rules
  bound what a rule can surface to whoever configured it. A non-admin Alerts
  Manager can no longer author a rule that leaks records they are not allowed to
  see via the alerts the cron creates.

### 19.0.2.0.0

- Initial migration to OpenSPP2
