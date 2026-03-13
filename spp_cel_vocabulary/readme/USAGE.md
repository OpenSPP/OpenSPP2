### Quick Reference

| Function                           | Purpose                                    | Example                                          |
| ---------------------------------- | ------------------------------------------ | ------------------------------------------------ |
| `code(identifier)`                 | Resolve code by URI or alias               | `r.gender_id == code("female")`                  |
| `in_group(field, group)`           | Check if code is in a concept group        | `in_group(r.gender_id, "feminine_gender")`        |
| `code_eq(field, identifier)`       | Safe code comparison with local support    | `code_eq(r.gender_id, "female")`                  |
| `is_female(field)`                 | Check feminine_gender group                | `is_female(r.gender_id)`                          |
| `is_male(field)`                   | Check masculine_gender group               | `is_male(r.gender_id)`                            |
| `is_head(field)`                   | Check head_of_household group              | `is_head(r.relationship_type)`                    |
| `is_pregnant(field)`               | Check pregnant_eligible group              | `is_pregnant(r.pregnancy_status_id)`              |
| `head(member)`                     | Check if member is head of household       | `members.exists(m, head(m))`                      |

> **Note:** Both `r` and `me` are valid prefixes for the registrant symbol. This guide
> uses `r` (matching ADR-008).

### Basic Examples

```javascript
// Simple gender check
is_female(r.gender_id)

// Code comparison
code_eq(r.gender_id, "female")

// Group membership check
in_group(r.gender_id, "feminine_gender")

// Head of household who is female
members.exists(m, head(m) && is_female(m.gender_id))
```

### When to Use Which Function

| Need                                          | Use                           |
| --------------------------------------------- | ----------------------------- |
| Check if code belongs to a semantic group     | `in_group()`                  |
| Use a predefined semantic check               | `is_female()`, `is_male()`   |
| Compare a field to a specific code            | `code_eq()`                   |
| Use a code value in a comparison              | `code()`                      |
| Check if member is head of household          | `head()`                      |

**`is_female(r.gender_id)`** vs **`in_group(r.gender_id, "feminine_gender")`**: Identical
behavior. Semantic helpers are shortcuts for `in_group()` with standard concept groups.

**`is_head(code_field)`** vs **`head(member)`**: Different! `is_head()` checks if a vocabulary
code is in the head_of_household group. `head()` checks if a member record is the head of
their household by looking up membership type.

For the complete usage guide with advanced examples, see the root `USAGE.md` file.
