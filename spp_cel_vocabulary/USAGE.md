# CEL Vocabulary Functions - Usage Guide

This guide provides practical examples of using vocabulary-aware CEL functions in
OpenSPP eligibility rules and filters.

## Quick Reference

| Function                 | Purpose                        | Example                                  |
| ------------------------ | ------------------------------ | ---------------------------------------- |
| `code(id)`               | Resolve code by URI/alias      | `me.gender == code("female")`            |
| `in_group(field, group)` | Check concept group membership | `in_group(me.gender, "feminine_gender")` |
| `code_eq(field, id)`     | Safe code comparison           | `code_eq(me.gender, "female")`           |
| `is_female(field)`       | Check feminine gender          | `is_female(me.gender)`                   |
| `is_male(field)`         | Check masculine gender         | `is_male(me.gender)`                     |
| `is_head(field)`         | Check head of household        | `is_head(me.relationship)`               |
| `is_pregnant(field)`     | Check pregnancy status         | `is_pregnant(me.pregnancy_status)`       |

## Basic Examples

### Example 1: Simple Gender Check

**Use Case:** Filter for female registrants

```cel
is_female(me.gender)
```

**What it does:**

- Checks if `me.gender` is in the `feminine_gender` concept group
- Works with any code in the group (including local codes)
- Returns boolean (true/false)

**Equivalent to:**

```cel
in_group(me.gender, "feminine_gender")
```

### Example 2: Code Comparison

**Use Case:** Check if gender is explicitly "Female"

```cel
code_eq(me.gender, "Female")
```

**What it does:**

- Resolves "Female" to a vocabulary code
- Compares `me.gender` to that code
- Handles local codes via `reference_uri`

**Also works with:**

```cel
me.gender == code("Female")
me.gender == code("urn:iso:std:iso:5218#2")  # By URI
```

### Example 3: Head of Household

**Use Case:** Find heads of households

```cel
is_head(me.relationship_type)
```

**In group context:**

```cel
members.exists(m, is_head(m._link.kind))
```

## Complex Eligibility Rules

### Example 4: 4Ps Pregnant Women Set

**Use Case:** Female registrants who are pregnant

```cel
is_female(me.gender) and is_pregnant(me.pregnancy_status)
```

**What it checks:**

- Gender is in `feminine_gender` group
- Pregnancy status is in `pregnant_eligible` group

### Example 5: Households with Female Head

**Use Case:** Households headed by women

```cel
members.exists(m,
    is_head(m._link.kind) and is_female(m.gender)
)
```

**What it does:**

- Iterates through household members
- Finds members who are both head AND female
- Returns true if at least one exists

### Example 6: Maternal Health Program

**Use Case:** Pregnant women or mothers with infants

```cel
is_pregnant(me.pregnancy_status) or
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
in_group(me.hazard_type, "climate_hazards") and
  me.affected_date >= days_ago(90)
```

**What it checks:**

- Hazard type is climate-related (typhoon, flood, drought)
- Occurred in last 90 days

### Example 8: Vulnerable Households

**Use Case:** Female-headed households with children

```cel
members.exists(head,
    is_head(head._link.kind) and is_female(head.gender)
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
is_female(me.gender)
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
in_group(me.hazard_type, "climate_hazards")
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
    is_head(m._link.kind) and is_female(m.gender)
) and

# With children under 14
members.exists(child,
    age_years(child.birthdate) < 14
) and

# Either pregnant or recently gave birth
(
    is_pregnant(me.pregnancy_status) or
    (me.last_birth_date >= days_ago(180))
) and

# Low income
me.monthly_income < 5000
```

### Example 12: Priority Scoring

**Use Case:** Calculate priority score

```cel
# Base score
50 +

# +20 points for female head
(members.exists(m, is_head(m._link.kind) and is_female(m.gender)) ? 20 : 0) +

# +15 points per child under 5
(members.count(m, age_years(m.birthdate) < 5) * 15) +

# +25 points if pregnant
(is_pregnant(me.pregnancy_status) ? 25 : 0) +

# +10 points for elderly member
(members.exists(m, age_years(m.birthdate) >= 60) ? 10 : 0)
```

### Example 13: Disaster Vulnerability Assessment

**Use Case:** Households vulnerable to specific hazards

```cel
# In flood-prone area
in_group(me.location_hazard_risk, "climate_hazards") and
in_group(me.location_hazard_type, "water_related") and

# With vulnerable members
(
    # Children
    members.exists(m, age_years(m.birthdate) < 5) or
    # Elderly
    members.exists(m, age_years(m.birthdate) >= 60) or
    # Pregnant women
    members.exists(m, is_pregnant(m.pregnancy_status)) or
    # Persons with disability
    members.exists(m, in_group(m.disability_type, "persons_with_disability"))
)
```

## Integration with Other CEL Functions

### Example 14: Age and Gender

**Use Case:** Women of reproductive age

```cel
is_female(me.gender) and
age_years(me.birthdate) >= 15 and
age_years(me.birthdate) <= 49
```

### Example 15: Time-based Eligibility

**Use Case:** Recently affected households

```cel
in_group(me.hazard_type, "climate_hazards") and
days_since(me.affected_date) <= 90
```

### Example 16: Enrollment Status

**Use Case:** Unenrolled eligible individuals

```cel
is_female(me.gender) and
age_years(me.birthdate) >= 18 and
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

```python
service = env['spp.cel.service']
result = service.validate_expression(
    'is_female(me.gender)',
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
in_group(me.hazard_type, "climate_hazards")
```

✅ **Cache code resolution** (automatic via `@ormcache`)

```cel
is_female(me.gender)  # First call resolves, subsequent calls cached
```

✅ **Combine conditions efficiently**

```cel
# Good: Short-circuit evaluation
is_female(me.gender) and is_pregnant(me.pregnancy_status)
```

### Don'ts

❌ **Avoid redundant code() calls**

```cel
# Bad: Multiple lookups
me.gender == code("female") and me.gender == code("F")

# Good: Use concept group
in_group(me.gender, "feminine_gender")
```

❌ **Don't nest complex expressions**

```cel
# Bad: Hard to read and maintain
members.exists(m, in_group(m.gender, "feminine_gender") and
    age_years(m.birthdate) < 5 and
    members.exists(n, n.id != m.id and age_years(n.birthdate) < 10))

# Good: Break into separate conditions
members.exists(m,
    in_group(m.gender, "feminine_gender") and
    age_years(m.birthdate) < 5
) and
members.count(m, age_years(m.birthdate) < 10) >= 2
```

## Common Pitfalls

### Pitfall 1: Missing Concept Group

**Problem:**

```cel
in_group(me.status, "nonexistent_group")
```

**Result:** Always returns false, domain matches nothing

**Solution:** Check group exists and has codes

### Pitfall 2: Wrong Field Type

**Problem:**

```cel
is_female(me.name)  # name is Char, not Many2one to vocabulary.code
```

**Result:** Type error or unexpected behavior

**Solution:** Use vocabulary code fields only

### Pitfall 3: Empty Concept Group

**Problem:**

```cel
in_group(me.gender, "feminine_gender")  # Group exists but has no codes
```

**Result:** Always returns false

**Solution:** Add codes to the concept group

### Pitfall 4: Case Sensitivity

**Problem:**

```cel
code_eq(me.gender, "FEMALE")  # Wrong case
```

**Result:** May not match if vocabulary uses "Female"

**Solution:** Check exact code/display values, or use concept groups

## Migration Examples

### Before: String Comparison

```cel
# Old (fragile)
me.gender.code == "F" or me.gender.code == "female"
```

```cel
# New (robust)
is_female(me.gender)
```

### Before: Hardcoded Values

```python
# Old (fragile)
if member.gender_id.code == "F":
    eligible = True
```

```cel
# New (robust)
is_female(me.gender)
```

### Before: No Local Code Support

```cel
# Old (doesn't work with local codes)
me.gender.code == "F"
```

```cel
# New (works with "F", "Female", "babae", etc.)
is_female(me.gender)
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
