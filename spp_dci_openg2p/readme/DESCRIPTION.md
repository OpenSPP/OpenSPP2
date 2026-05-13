Permanent OpenG2P preset for the CEL <-> DCI bridge. Ships pre-configured `spp.dci.data.source`, `spp.data.provider`, and `spp.cel.variable` records so a deployment targeting an OpenG2P-backed DCI Disability Registry gets the wiring out of the box. Config-only in v1 — zero Python code.

### What this module ships

| Record                                  | Purpose                                                                  |
| --------------------------------------- | ------------------------------------------------------------------------ |
| `spp.dci.data.source` 'openg2p_dr'      | DCI data source: base URL, sender ID, registry_type=DR                   |
| `spp.data.provider` 'openg2p_dr'        | CEL-side provider linked to the DCI source                               |
| `spp_studio.var_has_disability` (override) | The semantic `has_disability` CEL accessor, repointed at the DCI provider |

The CEL accessor name stays vendor-neutral (`has_disability`, per ADR-023 §1a). The OpenG2P-ness lives only in the data source and provider records. Repointing at a different DCI Disability Registry is a configuration change on the data source, never a CEL change.

### What this module does NOT ship

- OAuth2 credentials (admins configure these post-install via the data source form — no secrets in source control)
- A demo program (operators create their own programs using the `has_disability` CEL accessor)
- Python code (any OpenG2P-specific behavioural quirk that emerges in the future would be added here as adapter code; v1 stays pure config)

### Architectural shape

`spp_dci_openg2p` is a vendor preset on top of the registry-type DCI client (`spp_dci_client_dr`), not a DCI client itself:

```
spp_dci_openg2p        (vendor preset — this module)
    depends on
spp_cel_dci_bridge     (registry-agnostic CEL <-> DCI infrastructure)
    depends on
spp_dci_client_dr      (DCI client for the Disability Registry type)
    depends on
spp_dci_client         (base DCI client)
```

Other DCI Disability Registries (e.g., a national DR) would ship as separate sibling preset modules (`spp_dci_<vendor>`), reusing `spp_cel_dci_bridge` and `spp_dci_client_dr`.

### See Also

- ADR-023 — overall design, why the bridge exists, registry-type vs vendor-preset module distinction
- `spp_cel_dci_bridge` — the bridge infrastructure this preset configures
