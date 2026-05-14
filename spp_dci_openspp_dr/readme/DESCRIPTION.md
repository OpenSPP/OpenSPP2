Permanent SP-side preset that points the CEL bridge at an OpenSPP-DR (Disability Registry) instance. Ships pre-configured `spp.dci.data.source`, `spp.data.provider`, and the `has_disability` CEL variable binding so an SP-side OpenSPP deployment can ask a sibling OpenSPP-DR for disability data over DCI out of the box.

This is the SP-side counterpart to `spp_dci_server_disability` (which runs on the DR instance). Install this preset on the SP instance; install `spp_dci_server_disability` on the DR instance.

### What this module ships

| Record                                  | Purpose                                                                  |
| --------------------------------------- | ------------------------------------------------------------------------ |
| `spp.dci.data.source` 'openspp_dr'      | DCI data source: base URL, sender ID, registry_type=DR                   |
| `spp.data.provider` 'openspp_dr'        | CEL-side provider linked to the DCI source                               |
| `spp_studio.var_has_disability` (override) | The semantic `has_disability` CEL accessor, repointed at the DR provider |
| `OpenSPPDRService`                      | DR-shaped lookup: partner identifier → OpenSPP-DR record at `data.reg_records[0]` |
| Dispatcher override                     | Routes `vendor=openspp` DR sources to `OpenSPPDRService` instead of upstream `DRService` |

The CEL accessor stays vendor-neutral (`has_disability`, per ADR-023 §1a). The OpenSPP-DR-ness lives only in the data-source/provider/dispatcher-override records — never in the CEL surface.

### Why the vendor override exists

Upstream `spp_dci_client_dr.DRService` reads disability fields from `data` directly, but the SPDCI spec (and our DR server) put records at `data.reg_records[0]`. Until DRService is fixed upstream, this preset's `OpenSPPDRService` takes ownership of the response unwrap. Clearing the `vendor` field on the data source returns the variable to the upstream handler.

### See Also

- ADR-024 — federated demo topology
- `spp_dci_server_disability` — DR-side companion module
- `spp_cel_dci_bridge` — registry-agnostic infrastructure
- `spp_dci_openg2p` — analogous SR-side preset for OpenG2P
