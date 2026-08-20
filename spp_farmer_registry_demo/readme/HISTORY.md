### 19.0.2.1.3

- fix(farmer_demo): type demo farm groups as FARM. Farm groups were created with no group type, so they did not read as farms in the registry; a farm stays typed FARM even when it joins a cooperative, and only the cooperative container is typed COOPERATIVE (#1120)

### 19.0.2.1.2

- fix(demo): put the Input Subsidy Program on **manual** entitlement approval (`auto_approve_entitlements=False`) so a demo user can walk the full cycle → entitlement approval chain, not just cycle approval. The flag is now per-program (every other demo program stays auto-approve), and historically seeded cycles are unaffected because the generator force-approves their pending entitlements (#1122)

### 19.0.2.1.1

- fix(demo): name each farm after its head member and give every member the head's family name so a household reads as one family; farm names and registry IDs stay unique and generation remains seed-deterministic, resolving duplicate farm names and duplicate Tax/National IDs (#1114)
- fix(demo): resolve the head's gender once (up front) for blueprints with `head_gender="any"` and use it for both the head's name pool and the head member's gender, so a head's name always matches their recorded gender (no more e.g. a male-gendered head named "Maria") (#1114)

### 19.0.2.1.0

- feat(demo): add GIS + irrigation scenario (FM4) with reservoir + canal network seed; FM4's idle hectare is now narratively explained as the downstream consequence of reduced reservoir capacity
- feat(demo): seed farm assets (hand tractor on FM1, water pump on FM8) and a `manage_farm_asset` change request in the CR lifecycle
- feat(demo): add a closed prior-year farm season alongside the active one to demonstrate the `draft → active → closed` state machine
- chore(deps): declare `spp_gis`, `spp_land_record`, `spp_irrigation`, `spp_farmer_registry_vocabularies` explicitly — these were used at runtime but never listed
- docs(demo): add Scenario 10 (GIS + irrigation walk for FM4); document AGROVOC species selection (rice / tilapia) in Scenario 1; add farm-season state-machine sub-step; refresh FM1/FM4/FM8 farm story tables and the CR overview

### 19.0.2.0.0

- Initial migration to OpenSPP2
