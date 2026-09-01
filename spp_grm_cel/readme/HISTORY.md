### 19.0.2.0.2

- fix(security): GRM routing and escalation rules now evaluate with the identity of whoever
  defined them (``eval_as_user_id``, system-managed), not as the superuser cron. An officer's
  rule can only route/escalate tickets within that officer's own record-rule scope, closing the
  path where an always-match rule applied by the hourly cron could seize every ticket in the
  database (#379). Existing rules are backfilled from ``create_uid`` by a migration; note that
  a user who owns rules can no longer be deleted (``ondelete="restrict"``) — archive them
  instead, and a rule owned by the superuser (created from a shell, import script, or data
  load) still evaluates without record-rule bounds and is called out with a warning by both
  the migration and the rule engine.
- fix(security): the rule-engine entry points (``apply_routing``, ``apply_escalations``,
  ``apply_escalation``, ``check_escalations``) are marked ``@api.private`` — no longer callable
  over RPC (#381).
- fix(security): drop the portal and internal-user read rows on both rule models. With
  owner-identity evaluation the acting user never reads the rules, so the rows only exposed the
  routing/escalation map (conditions, targets, thresholds) to enumeration (hardening alongside
  #379/#381).
- fix: an escalation is now applied atomically (savepoint): if any post-write step — the
  chatter post, notification, or case creation — is denied because the rule just reassigned
  the ticket out of its owner's own scope, the whole escalation rolls back and is skipped
  instead of persisting half-applied with its chatter message silently lost.
- fix: increment ``match_count`` / ``escalation_count`` with an atomic ``UPDATE`` instead of a
  read-modify-write, avoiding a serialization failure under concurrent cron/UI escalation whose
  dispatch-level retry would re-run the whole cron pass.
- fix: rule CEL validation now reports any parser error as a ``ValidationError`` (previously only
  ``SyntaxError`` was caught).
- fix: the hourly escalation cron searches the active rule set once per pass instead of once per
  open ticket, and the engine logs (instead of silently skipping) rules with no evaluation
  identity and tickets skipped for lack of owner access.

### 19.0.2.0.1

- fix(security): restrict GRM routing and escalation rules to GRM staff. Portal users no longer
  hold write/create on ``spp.grm.routing.rule`` and ``spp.grm.escalation.rule``; these models
  carry no record rules, so the access-control entry was the only boundary. Because portal
  grievance submission runs sudo, a portal-authored rule previously executed its CEL condition
  and actions as superuser.
- fix(grm): increment the escalation counter with elevated rights, matching the routing rule's
  ``match_count`` update, so a caller without write access on the rule cannot leave the counter
  and chatter missing on an otherwise-applied escalation. Other partial-failure modes (a failing
  notification send or case creation is logged and skipped) are pre-existing and unchanged.

### 19.0.2.0.0

- Initial migration to OpenSPP2
