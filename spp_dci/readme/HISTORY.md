### 19.0.2.0.2

- fix(security): stop the DCI Administrator group from granting full system
  administration. `implied_ids` grants the implied groups to members, so the
  previous `base.group_system` link escalated any holder of the DCI
  PII-visibility role to a Settings/System administrator. OpenSPP admins now
  imply the group instead (preserving admin visibility of gated PII fields),
  and a migration strips the unsafe link from existing databases.

### 19.0.2.0.0

- Initial migration to OpenSPP2
