### 19.0.2.0.1

- fix(security): restrict GRM routing and escalation rules to GRM staff. Portal users no longer
  hold write/create on ``spp.grm.routing.rule`` and ``spp.grm.escalation.rule``; these models
  carry no record rules, so the access-control entry was the only boundary. Because portal
  grievance submission runs sudo, a portal-authored rule previously executed its CEL condition
  and actions as superuser.
- fix(grm): increment the escalation counter with elevated rights, matching the routing rule's
  ``match_count`` update, so a caller without write access cannot leave an escalation applied
  half-way (notification sent and case created, counter and chatter missing).

### 19.0.2.0.0

- Initial migration to OpenSPP2
