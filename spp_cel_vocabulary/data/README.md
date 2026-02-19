# Concept Groups Data Files

This directory contains XML data files for common concept groups used in
vocabulary-aware CEL functions.

## Concept Groups Included

The `concept_groups.xml` file defines the following groups:

- **feminine_gender** / `is_female()` - Feminine gender codes
- **masculine_gender** / `is_male()` - Masculine gender codes
- **head_of_household** / `is_head()` - Head of household relationship codes
- **pregnant_eligible** / `is_pregnant()` - Pregnancy status codes eligible for maternal
  benefits
- **climate_hazards** - Climate-related disaster codes
- **geophysical_hazards** - Earthquake, volcanic, landslide codes
- **children** - Child age group codes
- **adults** - Adult age group codes
- **elderly** - Elderly/senior citizen codes
- **persons_with_disability** - Disability type codes

## Customizing for Your Deployment

These groups are created **empty** by default. You need to add your vocabulary codes to
them.

### Option 1: Through UI

1. Go to **Social Protection → Configuration → Vocabulary → Concept Groups**
2. Open a concept group
3. Click **Edit**
4. In the **Codes** tab, add your vocabulary codes
5. Save

### Option 2: Through Data Files

Create a data file in your deployment module:

```xml
<?xml version="1.0" encoding="utf-8" ?>
<odoo>
  <data noupdate="1">
    <!-- Add gender codes to feminine_gender group -->
    <record
      id="spp_cel_vocabulary.group_feminine_gender"
      model="spp.vocabulary.concept.group"
    >
      <field
        name="code_ids"
        eval="[
                (4, ref('spp_vocabulary.code_female')),
                (4, ref('spp_vocabulary.code_non_binary')),
                (4, ref('my_module.code_babae')),
            ]"
      />
    </record>

    <!-- Add gender codes to masculine_gender group -->
    <record
      id="spp_cel_vocabulary.group_masculine_gender"
      model="spp.vocabulary.concept.group"
    >
      <field
        name="code_ids"
        eval="[
                (4, ref('spp_vocabulary.code_male')),
                (4, ref('my_module.code_lalaki')),
            ]"
      />
    </record>
  </data>
</odoo>
```

### Option 3: Through Python Code

```python
# In a post_init_hook or migration script
def add_codes_to_groups(env):
    # Get concept groups
    feminine_group = env.ref('spp_cel_vocabulary.group_feminine_gender')
    masculine_group = env.ref('spp_cel_vocabulary.group_masculine_gender')

    # Get vocabulary codes
    female_code = env['spp.vocabulary.code'].search([
        ('namespace_uri', '=', 'urn:iso:std:iso:5218'),
        ('code', '=', '2')
    ], limit=1)

    male_code = env['spp.vocabulary.code'].search([
        ('namespace_uri', '=', 'urn:iso:std:iso:5218'),
        ('code', '=', '1')
    ], limit=1)

    # Add codes to groups
    feminine_group.write({'code_ids': [(4, female_code.id)]})
    masculine_group.write({'code_ids': [(4, male_code.id)]})
```

## Example: Philippines 4Ps Deployment

```xml
<?xml version="1.0" encoding="utf-8" ?>
<odoo>
  <data noupdate="1">
    <!-- Gender codes with local terminology -->
    <record
      id="spp_cel_vocabulary.group_feminine_gender"
      model="spp.vocabulary.concept.group"
    >
      <field
        name="code_ids"
        eval="[
                (4, ref('spp_vocabulary_iso.code_female')),
                (4, ref('spp_vocabulary_ph.code_babae')),
            ]"
      />
    </record>

    <record
      id="spp_cel_vocabulary.group_masculine_gender"
      model="spp.vocabulary.concept.group"
    >
      <field
        name="code_ids"
        eval="[
                (4, ref('spp_vocabulary_iso.code_male')),
                (4, ref('spp_vocabulary_ph.code_lalaki')),
            ]"
      />
    </record>

    <!-- Head of household -->
    <record
      id="spp_cel_vocabulary.group_head_of_household"
      model="spp.vocabulary.concept.group"
    >
      <field
        name="code_ids"
        eval="[
                (4, ref('spp_4ps.relationship_head')),
                (4, ref('spp_4ps.relationship_household_head')),
            ]"
      />
    </record>

    <!-- Pregnant eligible -->
    <record
      id="spp_cel_vocabulary.group_pregnant_eligible"
      model="spp.vocabulary.concept.group"
    >
      <field
        name="code_ids"
        eval="[
                (4, ref('spp_4ps.pregnancy_pregnant')),
                (4, ref('spp_4ps.pregnancy_expecting')),
            ]"
      />
    </record>

    <!-- Climate hazards (Philippines specific) -->
    <record
      id="spp_cel_vocabulary.group_climate_hazards"
      model="spp.vocabulary.concept.group"
    >
      <field
        name="code_ids"
        eval="[
                (4, ref('spp_vocabulary_ph.hazard_bagyong')),     # Typhoon (local)
                (4, ref('spp_vocabulary_ph.hazard_pagbaha')),     # Flood (local)
                (4, ref('spp_vocabulary.hazard_typhoon')),        # Standard
                (4, ref('spp_vocabulary.hazard_flood')),          # Standard
                (4, ref('spp_vocabulary.hazard_drought')),        # Standard
            ]"
      />
    </record>
  </data>
</odoo>
```

## Testing Your Configuration

After adding codes to groups, test in CEL expressions:

```python
# In Odoo shell or test
service = env['spp.cel.service']

# Test feminine_gender group
result = service.compile_expression(
    'is_female(me.gender_id)',
    'registry_individuals'
)

# Test climate_hazards group
result = service.compile_expression(
    'in_group(me.hazard_type_id, "climate_hazards")',
    'registry_individuals'
)
```

## Creating New Concept Groups

If you need additional concept groups:

```xml
<record id="my_custom_group" model="spp.vocabulary.concept.group">
  <field name="name">my_custom_group</field>
  <field name="display_name">My Custom Group</field>
  <field name="cel_function">is_my_custom</field>
  <field name="description">Description of what this group represents</field>
  <field
    name="code_ids"
    eval="[
        (4, ref('my_module.code_1')),
        (4, ref('my_module.code_2')),
    ]"
  />
</record>
```

Then use in CEL:

```cel
in_group(me.some_field_id, "my_custom_group")
# Or create a helper function in your module
```

## Best Practices

1. **Use semantic names** - Group names should describe the concept, not the specific
   codes
2. **Document in descriptions** - Explain what codes should be in this group
3. **Include local codes** - Add both standard and local vocabulary codes
4. **Test thoroughly** - Verify groups work in actual CEL expressions
5. **Version control** - Keep group definitions in your deployment module's data files

## Reference

See ADR-016: Vocabulary Profiles and Code URIs for full design documentation.
