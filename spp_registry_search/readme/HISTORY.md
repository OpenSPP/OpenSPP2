### 19.0.2.1.1

- fix(security): gate the Registry Search "New Individual/Group" buttons on the registry create-permission roles instead of generic `res.partner` create access, so roles without registrant-create rights (e.g. validators) can no longer initiate creation (#1124)

### 19.0.2.0.0

- Initial migration to OpenSPP2
