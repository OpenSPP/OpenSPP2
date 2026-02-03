Integrates vocabulary-aware functions into the CEL (Common Expression Language) expression engine for eligibility rules. Extends the CEL translator to resolve vocabulary codes by URI or alias and translate vocabulary function calls into Odoo domains. Auto-installs when both `spp_cel_domain` and `spp_vocabulary` are present.

### Key Capabilities

- **CEL Function Registration**: Registers vocabulary functions (`code()`, `in_group()`, `code_eq()`, `head()`) with the CEL function registry for use in eligibility expressions
- **Domain Translation**: Extends `spp.cel.translator` to translate vocabulary function calls into Odoo domains that check `uri` and `reference_uri` fields
- **Semantic Helpers**: Provides shorthand functions (`is_female()`, `is_male()`, `is_head()`, `is_pregnant()`) that map to predefined concept groups
- **Concept Group Management**: Creates standard concept groups on installation (gender, household roles, pregnancy status, hazards, age groups, disability)
- **Local Code Support**: Handles semantic equality for local codes that map to standard codes via `reference_uri`

### Key Models

| Model                            | Description                                                             |
| -------------------------------- | ----------------------------------------------------------------------- |
| `spp.cel.vocabulary.functions`   | Manages vocabulary function registration with the CEL function registry |
| `spp.cel.translator` (inherited) | Extended to translate vocabulary function calls into Odoo domains       |

### Configuration

After installing (happens automatically when both dependencies are present):

1. Navigate to **Settings > Vocabularies > Concept Groups**
2. Review the auto-created concept groups: `feminine_gender`, `masculine_gender`, `head_of_household`, `pregnant_eligible`, `climate_hazards`, `geophysical_hazards`, `children`, `adults`, `elderly`, `persons_with_disability`
3. Add vocabulary codes to each group using the **Codes** tab to define which codes belong to each concept

### Usage in CEL Expressions

Example eligibility rules using vocabulary functions:

```javascript
// Code resolution
r.gender_id == code("female")
r.gender_id == code("urn:iso:std:iso:5218#2")

// Group membership
in_group(r.gender_id, "feminine_gender")
members.exists(m, in_group(m.relationship_type, "head_of_household"))

// Semantic helpers
is_female(r.gender_id) && age_years(r.birthdate) >= 18
members.exists(m, is_male(m.gender_id) && is_head(m.relationship_type))

// Head of household check
members.exists(m, head(m) && is_female(m.gender_id))
```

### Security

| Group | Access    |
| ----- | --------- |
| All   | Read-only |

No write access required as function registration happens automatically via `post_init_hook`.

### Extension Points

- Inherit `spp.cel.translator` and override `_to_plan()` to add custom vocabulary function translations
- Add new semantic helper functions to `services/cel_vocabulary_functions.py` and register them in `VOCABULARY_FUNCTIONS` dict
- Create additional concept groups via data files or UI to support domain-specific eligibility patterns

### Dependencies

`spp_cel_domain`, `spp_vocabulary`
