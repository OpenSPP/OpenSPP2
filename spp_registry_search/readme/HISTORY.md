### 19.0.2.1.2

- fix(security): enforce the configured Registry Search controls server-side in the
  `search_registrants` RPC method. The minimum-character requirement (counting effective,
  non-wildcard characters), the administrator's maximum result limit, and the targeted
  search mode (no fallback to unified search when the field is missing or invalid) are now
  applied on the server instead of only in the JavaScript client, and malformed RPC inputs
  are rejected instead of raising errors.

### 19.0.2.1.1

- fix(security): gate the Registry Search "New Individual/Group" buttons on the registry create-permission roles instead of generic `res.partner` create access, so roles without registrant-create rights (e.g. validators) can no longer initiate creation (#1124)

### 19.0.2.0.0

- Initial migration to OpenSPP2
