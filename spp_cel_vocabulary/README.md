# OpenSPP CEL Vocabulary Integration

**ADR-016 Phase 3: CEL Integration for vocabulary-aware expressions**

This module extends the CEL (Common Expression Language) system with vocabulary-aware
functions that enable robust eligibility rules across different deployment vocabularies.

> **Note:** Both `r` and `me` are valid prefixes for the registrant symbol. This guide
> uses `r` (matching ADR-008). The `me` alias is available via YAML profile
> configuration.

## Features

### Core Functions

#### `code(identifier)`

Resolve a vocabulary code by URI or alias.

```cel
r.gender_id == code("urn:iso:std:iso:5218#2")  # By URI
r.gender_id == code("female")                   # By alias
r.gender_id == code("babae")                    # Local alias (Philippines)
```

#### `in_group(code_field, group_name)`

Check if a vocabulary code belongs to a concept group.

```cel
in_group(r.gender_id, "feminine_gender")
members.exists(m, in_group(m.gender_id, "feminine_gender"))
```

#### `code_eq(code_field, identifier)`

Safe code comparison handling local code mappings.

```cel
code_eq(r.gender_id, "female")
```

### Semantic Helpers

User-friendly functions for common checks:

- `is_female(code_field)` - Check if code is in feminine_gender group
- `is_male(code_field)` - Check if code is in masculine_gender group
- `is_head(code_field)` - Check if code is in head_of_household group
- `is_pregnant(code_field)` - Check if code is in pregnant_eligible group
- `head(member)` - Check if a member is the head of household (takes a member record,
  not a code field)

### Example Usage

#### Simple Gender Check

```cel
is_female(r.gender_id)
```

#### Complex Eligibility Rule

```cel
# Pregnant women or mothers with children under 5
# Note: pregnancy_status_id is provided by country-specific modules
is_pregnant(r.pregnancy_status_id) or
  members.exists(m, age_years(m.birthdate) < 5)
```

#### Local Code Support

```cel
# Works in any deployment, even with local terminology
# Note: hazard_type_id is provided by country-specific modules
in_group(r.hazard_type_id, "climate_hazards")
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
in_group(r.gender_id, "feminine_gender")
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

### Concept Groups

Standard concept groups are created automatically via `post_init_hook` on module
installation (search-or-create pattern, safe for upgrades). They have no XML IDs — look
them up by name.

To add codes to a group via data files:

```xml
<!-- Look up by name since groups are created by hook, not XML -->
<function model="spp.vocabulary.concept.group" name="search">
  <!-- Use write() to add codes after finding the group -->
</function>
```

Or via Python:

```python
group = env['spp.vocabulary.concept.group'].search(
    [('name', '=', 'feminine_gender')], limit=1
)
group.write({'code_ids': [Command.link(female_code.id)]})
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
├── __init__.py                                  # post_init_hook, concept group creation
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── cel_vocabulary_functions.py              # Function registration
│   └── cel_vocabulary_translator.py             # Domain translation
├── services/
│   ├── __init__.py
│   ├── cel_vocabulary_functions.py              # Pure Python functions
│   └── vocabulary_cache.py                      # Session-scoped cache
├── tests/
│   ├── __init__.py
│   ├── test_cel_vocabulary.py                   # Core function and translation tests
│   ├── test_vocabulary_cache.py                 # Cache behavior tests
│   ├── test_vocabulary_in_exists.py             # Vocabulary in exists() predicates
│   └── test_init_and_coverage.py                # Init, edge cases, coverage
├── security/
│   └── ir.model.access.csv
└── data/
    ├── concept_groups.xml                       # Documentation (groups created by hook)
    └── README.md                                # Data configuration guide
```

### Design Patterns

1. **Pure Functions** - Services contain stateless Python functions
2. **Environment Injection** - Functions marked with `_cel_needs_env=True`; CEL service
   injects fresh env at evaluation time
3. **Function Registry** - Dynamic registration with CEL system
4. **Domain Translation** - AST transformation to Odoo domains
5. **Two-Layer Caching** - `@ormcache` (registry-scoped) + `VocabularyCache`
   (session-scoped)

## Testing

Run tests:

```bash
./scripts/test_single_module.sh spp_cel_vocabulary
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
r.gender_id == "female"
```

**After (robust):**

```cel
# Option 1: Semantic helper
is_female(r.gender_id)

# Option 2: Concept group
in_group(r.gender_id, "feminine_gender")

# Option 3: Safe comparison
code_eq(r.gender_id, "female")
```

### From Hardcoded Values

**Before:**

```python
if member.pregnancy_status_id.code == "pregnant":
    grant_maternal_benefit()
```

**After:**

```python
group = env['spp.vocabulary.concept.group'].search(
    [('name', '=', 'pregnant_eligible')], limit=1
)
if group.contains(member.pregnancy_status_id):
    grant_maternal_benefit()
```

Or use CEL:

```cel
# Note: pregnancy_status_id is provided by country-specific modules
in_group(r.pregnancy_status_id, "pregnant_eligible")
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
- Session-scoped `VocabularyCache` eliminates N+1 queries during evaluation
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
