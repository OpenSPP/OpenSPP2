Core farmer registry module providing complete farm data management with vocabulary-based classification, multi-activity tracking, land and irrigation management, GIS integration, and CEL variables for program targeting.

### Key Features

- Vocabulary-based field system replacing V1 Selection fields with `spp.vocabulary.code` references
- Multi-activity type support: crop, livestock, and aquaculture with cascading species selection
- Farm size calculations: total area, under crops, under livestock, aquaculture, leased, and idle land
- Smallholder threshold computation (configurable, default 5ha)
- Farm season state machine (draft → active → closed) controlling activity entry periods
- Farm asset and extension service tracking
- GIS/GeoJSON export with EPSG coordinate transformation for land parcels
- Head of household and female-headed farm indicators
- CEL variables for program eligibility: farm size, smallholder status, experience years, crop/livestock/aquaculture counts, land parcel metrics

### Key Models

| Model | Description |
| --- | --- |
| `spp.farm` | Core farm record (extends res.partner) |
| `spp.farm.details` | Vocabulary-based farm classification and acreage |
| `spp.farm.activity` | Crop/livestock/aquaculture activities |
| `spp.farm.season` | Agricultural season management |
| `spp.farm.asset` | Farm assets and machinery |
