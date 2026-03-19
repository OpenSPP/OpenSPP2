# OpenSPP Farmer Registry: Vocabularies

FAO-aligned vocabularies for farmer registry including crops, livestock, and aquaculture
classifications.

## Overview

This module provides standardized vocabularies for agricultural data collection aligned
with FAO standards:

- **FAO ICC (Indicative Crop Classification)** - Hierarchical crop classification
- **FAO WCA 2020 (World Census of Agriculture)** - Livestock classification and holder
  types
- **FAO ASFIS (Aquatic Sciences and Fisheries Information System)** - Aquaculture
  species
- **OpenSPP-specific** - Farm types, land tenure, cultivation methods, activity
  purposes, data sources

## Features

### Pre-loaded Vocabularies

#### Farm Type (`urn:openspp:vocab:farm-type`)

- Crop production
- Livestock
- Aquaculture
- Mixed farming

#### Land Tenure (`urn:openspp:vocab:land-tenure`)

- Self-owned
- Family owned
- Community/extended family
- Cooperative
- Government
- Leased
- Unknown

#### Cultivation Method (`urn:openspp:vocab:cultivation-method`)

- Irrigated
- Rainfed

#### Activity Purpose (`urn:openspp:vocab:activity-purpose`)

- Subsistence
- Commercial
- Both

#### Holder Type (`urn:fao:wca:2020:holder-type`)

- Individual
- Joint
- Institutional

#### Data Source (`urn:openspp:vocab:data-source`)

- Census
- Self registration
- Field visit
- External system

#### Crops (`urn:fao:icc:1.1`)

Hierarchical crop classification based on FAO ICC v1.1:

- Cereals (wheat, maize, rice, sorghum, barley, millet)
- Vegetables and melons (tomatoes, onions, cabbages)
- Fruits and nuts (bananas, plantains, mangoes)
- Root/tuber crops (potatoes, sweet potatoes, cassava)
- Leguminous crops (beans, peas, chickpeas, lentils)
- Sugar crops (sugar cane, sugar beet)
- And more...

#### Livestock (`urn:fao:livestock:2020`)

Hierarchical livestock classification:

- Cattle (dairy, beef, draught)
- Buffaloes
- Sheep and goats
- Pigs
- Poultry (chickens, ducks, geese, turkeys)
- Other (horses, donkeys, camels, rabbits, bees)

#### Aquaculture (`urn:fao:asfis:2024`)

ASFIS species with 3-alpha codes:

- Finfish (tilapia, carp, salmon, trout, catfish, milkfish, etc.)
- Crustaceans (prawns, shrimp, crayfish, crabs)
- Molluscs (oysters, mussels, clams, scallops, abalone)
- Aquatic plants (seaweed, kelp, nori)

### AGROVOC Import

Import AGROVOC vocabulary data to extend crop, livestock, and aquaculture vocabularies:

1. **Download AGROVOC RDF**: https://agrovoc.fao.org/download
2. **Upload N-Triples file**: Use the import wizard
3. **Select vocabulary**: Crops, Livestock, or Aquaculture
4. **Set language**: en, es, fr, ar, etc.
5. **Preview**: See what will be imported
6. **Import**: Queue job processes in background

#### AGROVOC URIs

All imported codes include `reference_uri` linking to AGROVOC concepts:

```
http://aims.fao.org/aos/agrovoc/c_12332  (Maize)
http://aims.fao.org/aos/agrovoc/c_6599   (Rice)
http://aims.fao.org/aos/agrovoc/c_8373   (Wheat)
```

## Technical Details

### Dependencies

- `spp_vocabulary` - Core vocabulary infrastructure
- `queue_job` - Background job processing
- `rdflib` (Python) - RDF parsing for AGROVOC import

### Models

- `spp.agrovoc.import` - AGROVOC import job (uses queue_job)
- `spp.agrovoc.import.wizard` - Import wizard (transient)

### Data Files

All vocabularies are loaded as system vocabularies (`is_system=True`):

- `vocab_farm_type.xml`
- `vocab_land_tenure.xml`
- `vocab_cultivation_method.xml`
- `vocab_activity_purpose.xml`
- `vocab_holder_type.xml`
- `vocab_data_source.xml`
- `vocab_crops_default.xml`
- `vocab_livestock_default.xml`
- `vocab_aquaculture_default.xml`

### Extension Pattern

Local codes can be added to system vocabularies using `is_local=True`:

```python
self.env['spp.vocabulary.code'].create({
    'vocabulary_id': vocab.id,
    'code': 'custom_crop_001',
    'display': 'Local Crop Variety',
    'is_local': True,
    'reference_uri': 'http://aims.fao.org/aos/agrovoc/c_12332',
    'equivalence': 'narrower',
})
```

## Usage

### In Farmer Registry Models

```python
class FarmerActivity(models.Model):
    _name = 'spp.farmer.activity'

    farm_type_id = fields.Many2one(
        'spp.vocabulary.code',
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:farm-type')]",
    )

    crop_ids = fields.Many2many(
        'spp.vocabulary.code',
        domain="[('namespace_uri', '=', 'urn:fao:icc:1.1')]",
    )

    livestock_ids = fields.Many2many(
        'spp.vocabulary.code',
        domain="[('namespace_uri', '=', 'urn:fao:livestock:2020')]",
    )
```

### Lookup by Code

```python
# Get code by namespace + code
wheat = self.env['spp.vocabulary.code'].get_code(
    'urn:fao:icc:1.1',
    '0111'
)

# Resolve by URI
crop = self.env['spp.vocabulary.code'].resolve_by_uri(
    'urn:fao:icc:1.1#0111'
)

# Resolve by AGROVOC reference
crop = self.env['spp.vocabulary.code'].search([
    ('reference_uri', '=', 'http://aims.fao.org/aos/agrovoc/c_8373')
], limit=1)
```

## References

- [FAO AGROVOC](https://agrovoc.fao.org/)
- [FAO Indicative Crop Classification](https://www.fao.org/economic/ess/ess-standards/icc/)
- [FAO World Census of Agriculture](https://www.fao.org/world-census-agriculture/)
- [FAO ASFIS Species List](https://www.fao.org/fishery/collection/asfis/)

## License

LGPL-3

## Authors

- OpenSPP.org

## Maintainers

- jeremi
- gonzalesedwin1123
