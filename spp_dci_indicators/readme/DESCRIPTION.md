Extends CEL expression evaluation to inject DCI registry symbols for eligibility rules. Provides lazy-loaded access to Disability Registry, Civil Registration, Integrated Beneficiary Registry, and Social Registry data through CEL expressions. Creates predefined variables for common DCI-based eligibility criteria.

### Key Capabilities

- Inject DCI symbols (`dr`, `crvs`, `ibr`, `sr`) into CEL context when evaluating `res.partner` records
- Query Disability Registry via `dr.has_disability`, `dr.severity('Vision')`, `dr.types`, `dr.assessed`
- Query Civil Registration via `crvs.is_alive`, `crvs.birth_verified`, `crvs.is_married`, `crvs.has_event()`
- Query IBR duplication checks via `ibr.has_duplicate`, `ibr.last_check_date`, `ibr.matched_programs`
- Query external Social Registry via `sr.is_registered`, `sr.program_count`, `sr.household_size`
- Lazy-load DCI data only when symbols are accessed in expressions
- Support live queries to DCI registries via `query_live()` methods on symbol providers

### Key Models

| Model                      | Description                                                  |
| -------------------------- | ------------------------------------------------------------ |
| `spp.cel.executor`         | Extended to inject DCI symbols during expression compilation |
| `spp.cel.registry`         | Extended to document DCI symbols in profile configurations   |
| `spp.dci.cel.integration`  | Service that resolves DCI symbols and provides documentation |

### Configuration

After installing:

1. Configure DCI data sources in dependent modules (`spp_dci_client_dr`, `spp_dci_client_crvs`, `spp_dci_client_ibr`)
2. Sync DCI data to local cache using scheduled actions or manual sync
3. Verify cached records exist in `spp.dci.disability.status`, `spp.dci.crvs.event`, `spp.dci.duplication.check`
4. Use predefined variables under **DCI Integration** category when building eligibility rules

### Data

Creates a **DCI Integration** variable category and 16 predefined variables:

- **DR variables**: `dci.dr.has_disability`, `dci.dr.vision_severe`, `dci.dr.hearing_severe`, `dci.dr.mobility_severe`, `dci.dr.assessed`
- **CRVS variables**: `dci.crvs.is_alive`, `dci.crvs.birth_verified`, `dci.crvs.is_married`
- **IBR variables**: `dci.ibr.has_duplicate`, `dci.ibr.no_duplicate`, `dci.ibr.checked`
- **SR variables**: `dci.sr.is_registered`, `dci.sr.program_count`, `dci.sr.has_programs`, `dci.sr.household_size`, `dci.sr.is_head_of_household`, `dci.sr.large_household`

### UI Location

DCI symbols appear automatically in CEL expression editors when evaluating eligibility for `res.partner` records. No dedicated menu entries.

### Security

No access control rules defined in this module. Access to DCI symbols inherits from cached DCI models in dependent modules.

### Extension Points

- Override `_build_symbol_context()` in `spp.cel.executor` to add custom DCI symbols
- Inherit symbol provider classes (`DRSymbolProvider`, `CRVSSymbolProvider`, `IBRSymbolProvider`, `SRSymbolProvider`) to add computed properties
- Create `spp.cel.variable` records that reference DCI symbols in `cel_accessor` field

### CEL Expression Examples

```python
# Disability-based eligibility
dr.has_disability == true and dr.severity('Mobility') >= 3

# Vital statistics verification
crvs.is_alive == true and crvs.birth_verified == true

# Duplication prevention
ibr.has_duplicate == false

# Multi-registry combined criteria
crvs.is_alive == true and dr.has_disability == true and ibr.has_duplicate == false

# Social Registry integration (requires spp_dci_client_sr)
sr.is_registered == true and sr.household_size > 5
```

### Dependencies

`spp_dci_client_dr`, `spp_dci_client_crvs`, `spp_dci_client_ibr`, `spp_cel_domain`, `spp_studio`
