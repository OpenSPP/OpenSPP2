### 19.0.2.0.2

- fix(security): stop the DCI Administrator group from granting full system
  administration. `implied_ids` grants the implied groups to members, so the
  previous `base.group_system` link escalated any holder of the DCI
  PII-visibility role to a Settings/System administrator. A migration strips
  the unsafe link from existing databases. The group is deliberately not
  implied by any other group: administrators who need DCI PII rendered on
  screen must be granted it explicitly - a deliberate, reviewable grant on
  the user record instead of an automatic side effect of adminship.

### 19.0.2.0.0

- Initial migration to OpenSPP2
