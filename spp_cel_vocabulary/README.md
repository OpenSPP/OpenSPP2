# OpenSPP CEL Vocabulary Integration

**ADR-016 Phase 3: CEL Integration for vocabulary-aware expressions**

This module extends the CEL (Common Expression Language) system with vocabulary-aware
functions that enable robust eligibility rules across different deployment vocabularies.

## Features

### Core Functions

#### `code(identifier)`

Resolve a vocabulary code by URI or alias.

```cel
me.gender == code("urn:iso:std:iso:5218#2")  # By URI
me.gender == code("female")                   # By alias
me.gender == code("babae")                    # Local alias (Philippines)
```

#### `in_group(code_field, group_name)`

Check if a vocabulary code belongs to a concept group.

```cel
in_group(me.gender, "feminine_gender")
members.exists(m, in_group(m.gender, "feminine_gender"))
```

#### `code_eq(code_field, identifier)`

Safe code comparison handling local code mappings.

```cel
code_eq(me.gender, "female")
```

### Semantic Helpers

User-friendly functions for common checks:

- `is_female(code_field)` - Check if code is in feminine_gender group
- `is_male(code_field)` - Check if code is in masculine_gender group
- `is_head(code_field)` - Check if code is in head_of_household group
- `is_pregnant(code_field)` - Check if code is in pregnant_eligible group

### Example Usage

#### Simple Gender Check

```cel
is_female(me.gender)
```

#### Complex Eligibility Rule

```cel
# Pregnant women or mothers with children under 5
is_pregnant(me.pregnancy_status) or
  members.exists(m, age_years(m.birthdate) < 5)
```

#### Local Code Support

```cel
# Works in any deployment, even with local terminology
in_group(me.hazard_type, "climate_hazards")
```

## How It Works

### Code Resolution

The `code()` function resolves identifiers in this order:

1. Full URI (e.g., `"urn:iso:std:iso:5218#2"`)
2. Code value in active vocabulary
3. Display name
4. Reference URI mapping (for local codes)

### Concept Groups

Concept groups provide semantic abstraction:

- Business logic checks **concepts**, not specific code values
- Works across deployments with different vocabularies
- Supports local codes via `reference_uri` mapping

Example:

```python
# Concept Group: feminine_gender
- urn:iso:std:iso:5218#2 (Female, ISO standard)
- urn:openspp:ph:vocab:gender#babae (Babae, PH local → maps to Female)
```

### Domain Translation

CEL expressions are translated to Odoo domains:

```cel
in_group(me.gender, "feminine_gender")
```

Translates to:

```python
["|",
  ("gender_id.uri", "in", ["urn:iso:std:iso:5218#2", "urn:openspp:ph:vocab:gender#babae"]),
  ("gender_id.reference_uri", "in", ["urn:iso:std:iso:5218#2", ...])
]
```

## Installation

1. Install dependencies: `spp_cel_domain`, `spp_vocabulary`
2. Install this module
3. Functions are automatically registered on installation

## Configuration

### Defining Concept Groups

Create concept groups via UI or data files:

```xml
<record id="group_feminine_gender" model="spp.vocabulary.concept.group">
  <field name="name">feminine_gender</field>
  <field name="display_name">Feminine Gender</field>
  <field name="cel_function">is_female</field>
  <field name="description">Codes representing feminine gender identity</field>
  <field
    name="code_ids"
    eval="[
        (4, ref('spp_vocabulary.code_female')),
        (4, ref('spp_vocabulary_ph.code_babae'))
    ]"
  />
</record>
```

### Local Code Mapping

Map local codes to standard codes:

```xml
<record id="code_babae" model="spp.vocabulary.code">
  <field name="vocabulary_id" ref="vocab_gender_ph" />
  <field name="code">babae</field>
  <field name="display">Babae (Female)</field>
  <field name="is_local">True</field>
  <field name="reference_uri">urn:iso:std:iso:5218#2</field>
  <field name="equivalence">equivalent</field>
</record>
```

## Architecture

### Module Structure

```
spp_cel_vocabulary/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── cel_vocabulary_functions.py    # Function registration
│   └── cel_vocabulary_translator.py   # Domain translation
├── services/
│   ├── __init__.py
│   └── cel_vocabulary_functions.py    # Pure Python functions
├── tests/
│   ├── __init__.py
│   └── test_cel_vocabulary.py         # Comprehensive tests
└── security/
    └── ir.model.access.csv
```

### Design Patterns

1. **Pure Functions** - Services contain stateless Python functions
2. **Environment Injection** - Models wrap functions with Odoo env
3. **Function Registry** - Dynamic registration with CEL system
4. **Domain Translation** - AST transformation to Odoo domains

## Testing

Run tests:

```bash
# From openspp-odoo-19-migration/ directory
invoke test-spp-deps --modules=spp_cel_vocabulary --skip=queue_job --mode=update --db-filter='^devel$'
```

## Related Documentation

- [ADR-016: Vocabulary Profiles and Code URIs](../../docs/architecture/decisions/ADR-016-vocabulary-profiles-and-code-uris.md)
- [ADR-009: Vocabulary System](../../docs/architecture/decisions/ADR-009-terminology-system.md)
- CEL Domain module: `spp_cel_domain`
- Vocabulary module: `spp_vocabulary`

## Migration Guide

### From String Comparisons

**Before (fragile):**

```cel
me.gender == "female"
```

**After (robust):**

```cel
# Option 1: Semantic helper
is_female(me.gender)

# Option 2: Concept group
in_group(me.gender, "feminine_gender")

# Option 3: Safe comparison
code_eq(me.gender, "female")
```

### From Hardcoded Values

**Before:**

```python
if member.pregnancy_status_id.code == "pregnant":
    grant_maternal_benefit()
```

**After:**

```python
pregnant_group = env.ref('spp_vocabulary.group_pregnant_eligible')
if pregnant_group.contains(member.pregnancy_status_id):
    grant_maternal_benefit()
```

Or use CEL:

```cel
in_group(me.pregnancy_status, "pregnant_eligible")
```

## Benefits

1. **Deployment Flexibility** - Works with any vocabulary configuration
2. **Local Terminology** - Supports country-specific codes seamlessly
3. **Semantic Clarity** - Business logic expresses intent, not implementation
4. **Interoperability** - URI-based identification enables data exchange
5. **Maintainability** - Changes to vocabularies don't break logic

## Performance

- Code resolution uses `@ormcache` for fast lookups
- Concept group URIs are pre-computed and stored as JSON
- Domain translation happens once at compile time
- No per-record overhead in query execution

## Security

- All functions validated against CEL security model
- No direct database access from expressions
- Environment injection controlled by module
- Attribute access blocked via CEL's safe evaluation

## Limitations

- Requires `spp_vocabulary` module with URI support
- Concept groups must be defined before use in expressions
- Local codes require explicit reference_uri mapping
- Functions only work with vocabulary code fields (Many2one to spp.vocabulary.code)

## Future Enhancements

- Auto-discovery of concept groups from vocabulary metadata
- Expression linting/validation warnings for non-profile codes
- UI for testing vocabulary functions with sample data
- Performance monitoring and caching statistics
- Additional semantic helpers based on deployment needs

## Contributing

Follow OpenSPP development guidelines:

- Read `CLAUDE.md` in project root
- Follow naming conventions (`spp_*` prefix)
- Write tests (85%+ coverage target)
- Update this README for new functions

## License

LGPL-3

## Authors

OpenSPP.org
