### 19.0.2.0.2

- fix(security): stop granting ``spp_scoring.group_scoring_viewer`` direct read
  on ``spp.program.membership``. Because the membership ``_inherits``
  ``res.partner``, that grant exposed registrant PII (identity, contacts, IDs,
  bank details, relationships, other programs/entitlements) to any scoring
  viewer over RPC, without a program or registry role. Membership access is now
  governed solely by ``spp_programs`` ACLs, as documented; scoring viewers keep
  their scoring-model/result remit and read access to ``spp.program``.

### 19.0.2.0.0

- Initial migration to OpenSPP2
