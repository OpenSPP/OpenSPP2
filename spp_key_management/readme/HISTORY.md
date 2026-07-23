### 19.0.2.0.1

- fix(security): stop the Key Management Admin group from granting full
  system administration. `implied_ids` grants the implied groups to members,
  so the previous `base.group_system` link escalated any holder of the key
  management role to a Settings/System administrator. The admin group now
  implies Key Operator instead, key admins keep field access to the
  KMS-wrapped key material the cloud providers read in user context, and a
  migration strips the unsafe link from existing databases.

### 19.0.2.0.0

- Initial migration to OpenSPP2
