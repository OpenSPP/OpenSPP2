### 19.0.2.0.1

- fix(security): stop the Key Management Admin group from granting full
  system administration. `implied_ids` grants the implied groups to members,
  so the previous `base.group_system` link escalated any holder of the key
  management role to a Settings/System administrator. The admin group now
  implies Key Operator instead, key admins keep field access to the
  KMS-wrapped key material the cloud providers read in user context, and a
  migration strips the unsafe link from existing databases. The Key
  Management menu moved from Settings to a top-level menu: the Settings
  root is only visible to ERP managers, so key admins who are no longer
  system administrators could not reach it there.

### 19.0.2.0.0

- Initial migration to OpenSPP2
