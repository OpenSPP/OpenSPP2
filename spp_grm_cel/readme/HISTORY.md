### 19.0.2.0.2

- fix(security): GRM routing and escalation rules now evaluate with the identity of whoever
  defined them (``eval_as_user_id``, system-managed), not as the superuser cron. An officer's
  rule can only route/escalate tickets within that officer's own record-rule scope, closing the
  path where an always-match rule applied by the hourly cron could seize every ticket in the
  database (#379). Existing rules are backfilled from ``create_uid`` by a migration. A user who
  owns rules can no longer be deleted (``ondelete="restrict"``) — archive them instead; a rule
  whose owner is archived stops firing (logged) until someone takes ownership of it. A rule
  owned by the superuser (created from a shell, import script, or data load) still evaluates
  without record-rule bounds and is called out with a warning by both the migration and the
  rule engine. The new **Take Ownership** button on the rule form re-binds a rule to yourself;
  saving the form without changing what the rule targets does not.
- fix(security): the rule-engine entry points (``apply_routing``, ``apply_escalations``,
  ``apply_escalation``, ``check_escalations``) are marked ``@api.private`` — no longer callable
  over RPC (#381).
- fix(security): drop the portal and internal-user read rows on both rule models. The engine
  now loads the active rule set with elevated rights and applies each rule with its owner's
  identity, so no acting user needs read access on the rules; the rows only exposed the
  routing/escalation map (conditions, targets, thresholds) to enumeration (hardening alongside
  #379/#381). The ticket form's "Check Escalation" button is limited to GRM officers and above,
  enforced on the method itself — a view ``groups=`` does not bind an RPC call — by requiring
  write access on the ticket, which also keeps an officer to their own ticket scope.
- fix: an escalation is now applied atomically (savepoint). The ticket write, the chatter post
  and the counter succeed or roll back together, and if the rule owner is denied any effect the
  rule produces — posting to a ticket just reassigned out of their own scope, sending the
  configured template, or creating the configured case — the whole escalation rolls back and is
  skipped instead of persisting half-applied. The notification is sent last, after every effect
  that can still be denied, because delivery is the one step a rollback cannot take back — and a
  ghost mail would repeat, the rolled-back rule link no longer suppressing the rule on the next
  pass. Delivery or data errors in the notification and case steps remain best effort: logged,
  skipped, and isolated so they cannot abort the pass.
- fix: applying a routing rule is atomic in the same way. The ticket write and the match counter
  succeed or roll back together, and a database error while routing (a rule pointing at a
  since-deleted user) no longer leaves the transaction aborted: the ticket create that triggered
  the routing swallows the error, so every later statement of the same request — the rest of a
  portal submission — used to fail behind it.
- fix: a rule applies at most once per ticket. Previously the hourly cron re-escalated every
  still-open matching ticket on every pass, repeating the counter increment, the chatter post
  and the notification each hour.
- fix: one failing ticket no longer aborts the whole escalation pass; the failure is logged and
  the remaining tickets are processed.
- fix: case creation from an escalation rule never worked (it passed a field ``spp.case`` does
  not have and omitted the required case worker); it now fills ``presenting_issue`` and assigns
  the ticket assignee or the rule owner as case worker.
- fix: increment ``match_count`` / ``escalation_count`` with an atomic ``UPDATE`` instead of a
  read-modify-write, avoiding a serialization failure under concurrent cron/UI escalation whose
  dispatch-level retry would re-run the whole cron pass.
- fix: rule CEL validation now reports any parser error as a ``ValidationError`` (previously only
  ``SyntaxError`` was caught).
- fix: the hourly escalation cron resolves the active rule set and each rule's evaluation owner
  once per pass instead of once per open ticket (so owner warnings are logged once, not once
  per ticket), and the engine logs (instead of silently skipping) rules with no evaluation
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
