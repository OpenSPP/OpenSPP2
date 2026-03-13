# CEL Vocabulary Functions - Usage Guide

This guide provides practical examples of using vocabulary-aware CEL functions in
OpenSPP eligibility rules and filters.

> **Note:** Both `r` and `me` are valid prefixes for the registrant symbol. This guide
> uses `r` (matching ADR-008). The `me` alias is available via YAML profile
> configuration.

## Quick Reference

| Function                 | Purpose                           | Example                                           |
| ------------------------ | --------------------------------- | ------------------------------------------------- |
| `code(id)`               | Resolve code by URI/alias         | `r.gender_id == code("female")`                   |
| `in_group(field, group)` | Check concept group membership    | `in_group(r.gender_id, "feminine_gender")`        |
| `code_eq(field, id)`     | Safe code comparison              | `code_eq(r.gender_id, "female")`                  |
| `is_female(field)`       | Check feminine gender             | `is_female(r.gender_id)`                          |
| `is_male(field)`         | Check masculine gender            | `is_male(r.gender_id)`                            |
| `is_head(field)`         | Check head of household code      | `is_head(r.relationship_type)`                    |
| `is_pregnant(field)`     | Check pregnancy status            | `is_pregnant(r.pregnancy_status_id)`              |
| `head(member)`           | Check if member is household head | `head(m)` (takes member record, not a code field) |

### When to Use Which Function

| Need                                        | Use                              | Example                                    |
| ------------------------------------------- | -------------------------------- | ------------------------------------------ |
| Check if a code belongs to a semantic group | `in_group()`                     | `in_group(r.gender_id, "feminine_gender")` |
| Use a predefined semantic check             | `is_female()`, `is_male()`, etc. | `is_female(r.gender_id)`                   |
| Compare a field to a specific code          | `code_eq()`                      | `code_eq(r.gender_id, "female")`           |
| Use a code value in a comparison            | `code()`                         | `r.gender_id == code("female")`            |
| Check if member is head of household        | `head()`                         | `head(m)`                                  |

**`is_female(r.gender_id)`** vs **`in_group(r.gender_id, "feminine_gender")`**:
Identical behavior. Semantic helpers are shortcuts for `in_group()` with standard
concept groups.

**`code_eq(r.gender_id, "female")`** vs **`r.gender_id == code("female")`**: Identical
behavior. `code_eq()` is more concise; the comparison form is more readable for complex
expressions.

**`is_head(code_field)`** vs **`head(member)`**: Different! `is_head()` checks if a
vocabulary code is in the head_of_household group. `head()` checks if a member record is
the head of their household (looks up membership type).

## Basic Examples

### Example 1: Simple Gender Check

**Use Case:** Filter for female registrants

```cel
is_female(r.gender_id)
```

**What it does:**

- Checks if `r.gender_id` is in the `feminine_gender` concept group
- Works with any code in the group (including local codes)
- Returns boolean (true/false)

**Equivalent to:**

```cel
in_group(r.gender_id, "feminine_gender")
```

### Example 2: Code Comparison

**Use Case:** Check if gender is explicitly "Female"

```cel
code_eq(r.gender_id, "Female")
```

**What it does:**

- Resolves "Female" to a vocabulary code
- Compares `r.gender_id` to that code
- Handles local codes via `reference_uri`

**Also works with:**

```cel
r.gender_id == code("Female")
r.gender_id == code("urn:iso:std:iso:5218#2")  # By URI
```

### Example 3: Head of Household

**Use Case:** Find heads of households

```cel
is_head(r.relationship_type)
```

**In group context:**

```cel
members.exists(m, head(m))
```

> **Note:** Functions like `age_years()`, `members.exists()`, and `members.count()` are
> provided by `spp_cel_domain`, not this module.

## Complex Eligibility Rules

### Example 4: 4Ps Pregnant Women Set

**Use Case:** Female registrants who are pregnant

> **Note:** Fields like `pregnancy_status_id` and `hazard_type_id` are provided by
> country-specific modules, not the base registry.

```cel
is_female(r.gender_id) and is_pregnant(r.pregnancy_status_id)
```

**What it checks:**

- Gender is in `feminine_gender` group
- Pregnancy status is in `pregnant_eligible` group

### Example 5: Households with Female Head

**Use Case:** Households headed by women

```cel
members.exists(m,
    head(m) and is_female(m.gender_id)
)
```

**What it does:**

- Iterates through household members
- Finds members who are both head AND female
- Returns true if at least one exists

### Example 6: Maternal Health Program

**Use Case:** Pregnant women or mothers with infants

```cel
is_pregnant(r.pregnancy_status_id) or
  members.exists(child,
    age_years(child.birthdate) < 1
  )
```

**What it checks:**

- Registrant is pregnant, OR
- Has at least one child under 1 year old

### Example 7: Disaster Relief - Climate Events

**Use Case:** Households affected by climate hazards

```cel
in_group(r.hazard_type_id, "climate_hazards") and
  r.affected_date >= days_ago(90)
```

**What it checks:**

- Hazard type is climate-related (typhoon, flood, drought)
- Occurred in last 90 days

### Example 8: Vulnerable Households

**Use Case:** Female-headed households with children

```cel
members.exists(head,
    head(head) and is_female(head.gender_id)
) and
members.exists(child,
    age_years(child.birthdate) < 18
)
```

**What it checks:**

- Has female head of household
- Has at least one child under 18

## Working with Local Codes

### Example 9: Philippines - Local Terminology

**Setup:** Local codes with reference URIs

```python
# Code: babae (display: "Babae")
# reference_uri: urn:iso:std:iso:5218#2 (Female)

# Code: lalaki (display: "Lalaki")
# reference_uri: urn:iso:std:iso:5218#1 (Male)
```

**CEL Expression:**

```cel
is_female(r.gender_id)
```

**Works for all of:**

- Standard code: "Female" (code: F, uri: urn:iso:std:iso:5218#2)
- Local code: "Babae" (code: babae, reference_uri: urn:iso:std:iso:5218#2)

### Example 10: Hazard Mapping

**Setup:**

```python
# Standard: "Typhoon" (urn:openspp:vocab:hazard#typhoon)
# Local: "Bagyong" (urn:openspp:ph:vocab:hazard#bagyong)
#        reference_uri: urn:openspp:vocab:hazard#typhoon
```

**CEL Expression:**

```cel
in_group(r.hazard_type_id, "climate_hazards")
```

**Matches:**

- "Typhoon" (standard)
- "Bagyong" (local Philippine term)
- "Cyclone" (if added to group with reference to typhoon)

## Advanced Patterns

### Example 11: Multi-condition Eligibility

**Use Case:** Complex social protection program

```cel
# Female head of household
members.exists(m,
    head(m) and is_female(m.gender_id)
) and

# With children under 14
members.exists(child,
    age_years(child.birthdate) < 14
) and

# Either pregnant or recently gave birth
(
    is_pregnant(r.pregnancy_status_id) or
    (r.last_birth_date >= days_ago(180))
) and

# Low income
r.monthly_income < 5000
```

### Example 12: Priority Scoring

**Use Case:** Calculate priority score

```cel
# Base score
50 +

# +20 points for female head
(members.exists(m, head(m) and is_female(m.gender_id)) ? 20 : 0) +

# +15 points per child under 5
(members.count(m, age_years(m.birthdate) < 5) * 15) +

# +25 points if pregnant
(is_pregnant(r.pregnancy_status_id) ? 25 : 0) +

# +10 points for elderly member
(members.exists(m, age_years(m.birthdate) >= 60) ? 10 : 0)
```

### Example 13: Disaster Vulnerability Assessment

**Use Case:** Households vulnerable to specific hazards

```cel
# In flood-prone area
in_group(r.location_hazard_risk, "climate_hazards") and
in_group(r.location_hazard_type, "water_related") and

# With vulnerable members
(
    # Children
    members.exists(m, age_years(m.birthdate) < 5) or
    # Elderly
    members.exists(m, age_years(m.birthdate) >= 60) or
    # Pregnant women
    members.exists(m, is_pregnant(m.pregnancy_status_id)) or
    # Persons with disability
    members.exists(m, in_group(m.disability_type_id, "persons_with_disability"))
)
```

## Integration with Other CEL Functions

### Example 14: Age and Gender

**Use Case:** Women of reproductive age

```cel
is_female(r.gender_id) and
age_years(r.birthdate) >= 15 and
age_years(r.birthdate) <= 49
```

### Example 15: Time-based Eligibility

**Use Case:** Recently affected households

```cel
in_group(r.hazard_type_id, "climate_hazards") and
days_since(r.affected_date) <= 90
```

### Example 16: Enrollment Status

**Use Case:** Unenrolled eligible individuals

```cel
is_female(r.gender_id) and
age_years(r.birthdate) >= 18 and
enrollments.count(e, e.state == "enrolled") == 0
```

## Debugging Tips

### Check if Code is in Group

```python
# In Odoo shell
group = env['spp.vocabulary.concept.group'].search([('name', '=', 'feminine_gender')])
code = env['spp.vocabulary.code'].search([('code', '=', 'F')], limit=1)

print(group.contains(code))  # Should print True/False
print(group.get_code_uris())  # List all URIs in group
```

### Test Code Resolution

```python
# By alias
code = env['spp.vocabulary.code'].resolve_alias('female')
print(code.uri)  # urn:iso:std:iso:5218#2

# By URI
code = env['spp.vocabulary.code'].resolve_by_uri('urn:iso:std:iso:5218#2')
print(code.display)  # Female
```

### Validate Expression

> **Note:** `validate_expression()` checks whether an expression is syntactically and
> semantically valid and returns `{valid: True/False, error: ...}`. Use
> `compile_expression()` to compile an expression to a domain/plan and return the full
> translation result.

```python
service = env['spp.cel.service']
result = service.validate_expression(
    'is_female(r.gender_id)',
    'registry_individuals'
)

print(result['valid'])    # True/False
print(result['explain'])  # Human-readable explanation
print(result['error'])    # Error message if invalid
```

## Performance Considerations

### Do's

✅ **Use concept groups for semantic checks**

```cel
in_group(r.hazard_type_id, "climate_hazards")
```

✅ **Cache code resolution** (automatic via `@ormcache`)

```cel
is_female(r.gender_id)  # First call resolves, subsequent calls cached
```

✅ **Combine conditions efficiently**

```cel
# Good: Short-circuit evaluation
is_female(r.gender_id) and is_pregnant(r.pregnancy_status_id)
```

### Don'ts

❌ **Avoid redundant code() calls**

```cel
# Bad: Multiple lookups
r.gender_id == code("female") and r.gender_id == code("F")

# Good: Use concept group
in_group(r.gender_id, "feminine_gender")
```

❌ **Don't nest complex expressions**

```cel
# Bad: Hard to read and maintain
members.exists(m, in_group(m.gender_id, "feminine_gender") and
    age_years(m.birthdate) < 5 and
    members.exists(n, n.id != m.id and age_years(n.birthdate) < 10))

# Good: Break into separate conditions
members.exists(m,
    in_group(m.gender_id, "feminine_gender") and
    age_years(m.birthdate) < 5
) and
members.count(m, age_years(m.birthdate) < 10) >= 2
```

## Common Pitfalls

### Pitfall 1: Missing Concept Group

**Problem:**

```cel
in_group(r.status, "nonexistent_group")
```

**Result:** Always returns false, domain matches nothing

**Solution:** Check group exists and has codes

### Pitfall 2: Wrong Field Type

**Problem:**

```cel
is_female(r.name)  # name is Char, not Many2one to vocabulary.code
```

**Result:** Type error or unexpected behavior

**Solution:** Use vocabulary code fields only

### Pitfall 3: Empty Concept Group

**Problem:**

```cel
in_group(r.gender_id, "feminine_gender")  # Group exists but has no codes
```

**Result:** Always returns false

**Solution:** Add codes to the concept group

### Pitfall 4: Case Sensitivity

**Problem:**

```cel
code_eq(r.gender_id, "FEMALE")  # Wrong case
```

**Result:** May not match if vocabulary uses "Female"

**Solution:** Check exact code/display values, or use concept groups

## Migration Examples

### Before: String Comparison

```cel
# Old (fragile)
r.gender_id.code == "F" or r.gender_id.code == "female"
```

```cel
# New (robust)
is_female(r.gender_id)
```

### Before: Hardcoded Values

```python
# Old (fragile)
if member.gender_id.code == "F":
    eligible = True
```

```cel
# New (robust)
is_female(r.gender_id)
```

### Before: No Local Code Support

```cel
# Old (doesn't work with local codes)
r.gender_id.code == "F"
```

```cel
# New (works with "F", "Female", "babae", etc.)
is_female(r.gender_id)
```

## References

- [Module README](README.md) - Module overview and installation
- [ADR-016](../../docs/architecture/decisions/ADR-016-vocabulary-profiles-and-code-uris.md) -
  Design documentation
- [Data README](data/README.md) - Configuring concept groups

## Getting Help

1. Check logs: Look for `[CEL Vocabulary]` entries
2. Test in shell: Use Odoo shell to test functions directly
3. Validate expressions: Use `spp.cel.service.validate_expression()`
4. Check concept groups: Verify codes are added to groups
