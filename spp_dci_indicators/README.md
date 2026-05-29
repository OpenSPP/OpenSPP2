# OpenSPP DCI Indicators

This module provides DCI (Data Collaboration Infrastructure) data integration with OpenSPP's CEL (Common Expression
Language) eligibility system.

## Overview

The module enables clean, readable CEL expressions that access data from external DCI registries:

- **Disability Registry (DR)**: Access disability status and functional assessments
- **Civil Registration and Vital Statistics (CRVS)**: Access vital events (birth, death, marriage)
- **Integrated Beneficiary Registry (IBR)**: Access duplication checks and enrollment status

## CEL Expression Examples

### Disability Registry (DR)

```python
# Check if person has any disability
dr.has_disability == true

# Check for severe vision impairment
dr.severity('Vision') >= 3

# Check for specific disability type
dr.has_type('Mobility')

# Check if functional assessment exists
dr.assessed == true

# Get list of disability types
'Vision' in dr.types
```

### Civil Registration and Vital Statistics (CRVS)

```python
# Check if person is alive
crvs.is_alive == true

# Check if birth was registered
crvs.birth_verified == true

# Check marital status
crvs.is_married == true

# Check for specific event type
crvs.has_event('birth')
```

### Integrated Beneficiary Registry (IBR)

```python
# Check for duplicates in other programs
ibr.has_duplicate == false

# Check if enrolled in specific program
ibr.is_enrolled('Cash Transfer Program') == false

# Check if duplication check was performed
ibr.last_check_date != None

# Get list of programs with matches
len(ibr.matched_programs) == 0
```

## Combined Expressions

You can combine multiple DCI checks in a single eligibility expression:

```python
# Eligible if: alive, has severe disability, no duplicates
crvs.is_alive == true and dr.severity('Vision') >= 3 and ibr.has_duplicate == false

# Eligible if: birth verified, has disability, not enrolled elsewhere
crvs.birth_verified == true and dr.has_disability == true and ibr.is_enrolled('Other Program') == false
```

## Usage in Program Eligibility

1. Navigate to a Program
2. Go to Eligibility Manager
3. Select "CEL Expression" mode
4. Write your eligibility criteria using DCI symbols
5. Test and preview matching beneficiaries

Example eligibility criteria for a disability program:

```python
# Must be alive, have severe disability, and no duplicates
crvs.is_alive == true and
dr.severity('Mobility') >= 3 and
ibr.has_duplicate == false and
age_years(me.birthdate) >= 18
```

## Data Caching

DCI symbols use lazy-loading:

- Data is only fetched when the symbol is accessed in an expression
- Data is cached per-partner during CEL evaluation
- No data is loaded if the symbol is not referenced

This ensures efficient batch eligibility checks across thousands of beneficiaries.

## Predefined Indicators

The module includes predefined indicator definitions for common DCI checks:

### Disability Registry

- `dci.dr.has_disability`: Has any disability
- `dci.dr.vision_severe`: Severe vision impairment (3+)
- `dci.dr.hearing_severe`: Severe hearing impairment (3+)
- `dci.dr.mobility_severe`: Severe mobility impairment (3+)
- `dci.dr.assessed`: Has functional assessment

### CRVS

- `dci.crvs.is_alive`: Is alive (no death event)
- `dci.crvs.birth_verified`: Birth registration exists
- `dci.crvs.is_married`: Currently married

### IBR

- `dci.ibr.has_duplicate`: Duplicates found
- `dci.ibr.no_duplicate`: No duplicates found
- `dci.ibr.checked`: Duplication check performed

## Data Sources

This module reads cached DCI data from:

- `spp.dci.disability.status` (from spp_dci_client_dr)
- `spp.dci.crvs.event` (from spp_dci_client_crvs)
- `spp.dci.duplication.check` (from spp_dci_client_ibr)

Ensure these DCI client modules are installed and data is synced before using DCI symbols in eligibility expressions.

## Architecture

### Components

1. **Symbol Providers** (`symbols/dci_symbols.py`):

   - `DRSymbolProvider`: Disability Registry symbols
   - `CRVSSymbolProvider`: CRVS symbols
   - `IBRSymbolProvider`: IBR symbols

2. **CEL Integration** (`services/cel_integration.py`):

   - Symbol resolution service
   - Documentation service

3. **CEL Extensions** (`models/cel_extension.py`):
   - Extends `spp.cel.executor` to inject DCI symbols
   - Extends `spp.cel.registry` to document symbols

### Symbol Injection

When a CEL expression is evaluated:

1. CEL executor builds symbol context
2. DCI extension checks if root model is `res.partner`
3. If yes, DCI symbol providers are instantiated
4. Providers are added to context as `dr`, `crvs`, `ibr`
5. Expression can access DCI data via these symbols

## Dependencies

- `spp_dci_client_dr`: Disability Registry client
- `spp_dci_client_crvs`: CRVS client
- `spp_dci_client_ibr`: IBR client
- `spp_indicators`: Metrics core
- `spp_cel_domain`: CEL expression engine

## License

LGPL-3

## Author

OpenSPP.org
