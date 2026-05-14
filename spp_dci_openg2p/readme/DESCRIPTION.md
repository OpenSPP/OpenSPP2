Permanent OpenG2P preset for the CEL <-> DCI bridge. Ships pre-configured `spp.dci.data.source`, `spp.data.provider`, and `spp.cel.variable` records so a deployment targeting an OpenG2P-backed DCI Social Registry gets the wiring out of the box. Config plus a small vendor adapter that absorbs OpenG2P's request-shape quirks (see ADR-024).

### What this module ships

| Record                                  | Purpose                                                                  |
| --------------------------------------- | ------------------------------------------------------------------------ |
| `spp.dci.data.source` 'openg2p_dr'      | DCI data source: base URL, sender ID, registry_type=SR                   |
| `spp.data.provider` 'openg2p_dr'        | CEL-side provider linked to the DCI source                               |
| `spp_studio.var_has_disability` (override) | The semantic `has_disability` CEL accessor, repointed at the DCI provider |
| `OpenG2PDCIClient`                      | DCIClient subclass for OpenG2P's expression query shape, namespaced URI type, hard-coded Individual reg_type, and required consent/authorize blocks |
| `OpenG2PSocialService`                  | SR-shaped lookup: partner identifier → OpenG2P record at `data.reg_records[0]` |

The CEL accessor names stay vendor-neutral (per ADR-023 §1a). The OpenG2P-ness lives only in the data source, provider, and adapter — never in the CEL surface. Repointing at a different SR is a configuration change on the data source, not a CEL change.

### What this module does NOT ship

- OAuth2 credentials (admins configure these post-install via the data source form — no secrets in source control)
- A demo program (operators create their own programs using the relevant CEL accessors)
- Disability data lookups — disability lives in a separate OpenSPP-DR instance over its own DCI link (see ADR-024)

### Architectural shape

`spp_dci_openg2p` is a vendor preset on top of the bridge, not a DCI client itself:

```
spp_dci_openg2p        (vendor preset — this module)
    depends on
spp_cel_dci_bridge     (registry-agnostic CEL <-> DCI infrastructure)
    depends on
spp_dci_client         (base DCI client)
```

Other Social Registries would ship as separate sibling preset modules (`spp_dci_<vendor>`), reusing `spp_cel_dci_bridge`.

### See Also

- ADR-023 — overall design, why the bridge exists, registry-type vs vendor-preset module distinction
- ADR-024 — federated demo topology and OpenG2P's SR role
- `spp_cel_dci_bridge` — the bridge infrastructure this preset configures
