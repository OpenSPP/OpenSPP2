### After installing this module

1. Navigate to **Settings > Technical > DCI > Data Sources** (path may vary by spp_security group).
2. Open the `openg2p_dr` data source.
3. Replace the placeholder `base_url` (`https://openg2p.example.org/api/v1`) with your OpenG2P deployment URL.
4. Change `auth_type` from `none` to whatever OpenG2P requires (typically `oauth2`).
5. Populate `oauth2_token_url`, `oauth2_client_id`, `oauth2_client_secret`.
6. Verify `our_sender_id` matches what your OpenG2P instance expects to see from OpenSPP.
7. Click **Test Connection** to verify reachability.

### Cache TTL

The preset ships with `cache_ttl_seconds = 300` (5 minutes) on the `has_disability` variable so the DCI round-trip is visible during demos. For production:

- Open the `spp_studio.var_has_disability` CEL variable
- Raise `cache_ttl_seconds` to 86400 (24h) or higher, balancing data freshness against DCI request volume

### Identity mapping

The bridge resolves the partner's identifier from `partner.reg_ids` using the first matching id_type. Ensure every registrant in scope carries an identifier the OpenG2P deployment can resolve (UIN, national ID, etc.). Subjects without a resolvable identifier are recorded in `spp.dci.fetch.audit` as `result='not_found'` and are excluded from `has_disability == true` matches under the default null failure policy.

### Switching to a different DCI Disability Registry

This preset can be uninstalled and replaced with a different vendor preset (or hand-configured records) without changing any CEL rule. The semantic `has_disability` accessor stays the same; the data source behind it changes.
