Demo data generator for the OpenSPP Farmer Registry. Creates 8 named farmer personas with complete Philippine farm profiles, 5 agricultural subsidy programs with CEL eligibility expressions, and optionally generates ~730 volume farms from deterministic blueprints using a seeded random generator (`seed=42`) for reproducible output.

### Key Capabilities

- **8 Fixed Story Farms** with hardcoded profiles (Maria Santos, Juan Dela Cruz, Rosa Garcia, Amir Mangudadatu, Sofia Martinez, Ramon dela Cruz, Sittie Pangandaman, Danilo Villanueva)
- **~730 Volume Farms** generated deterministically from 21 blueprints via `SeededFarmGenerator` with `random.Random(seed=42)` — same seed always produces identical farms, members, and activities
- **5 Demo Programs** with CEL-based eligibility and benefit formulas (Input Subsidy, Equipment Grant, Livestock Support, Climate Resilience, Aquaculture Support)
- **2 Farm Cooperatives** demonstrating group-of-groups hierarchy (Nueva Ecija Rice Cooperative, BARMM Farmers Federation)
- **3 Edge Case Personas** for testing eligibility boundaries (AgriCorp Holdings, Idle Land Farm, New Farmer)
- Install Logic Packs from `spp_studio` for eligibility rules
- Create program cycles with entitlements and payments
- Create change requests at various workflow stages
- Geographic distribution across 8 Philippine provinces with GPS coordinates and land parcel polygons

### Key Models

| Model                          | Description                                         |
| ------------------------------ | --------------------------------------------------- |
| `spp.farmer.demo.generator`   | Core demo generator wizard with all generation logic |

### Configuration

After installing:

1. Navigate to **Settings > Demo Data > Load Farmer Demo**
2. Click "Load Demo Data" to generate

### Demo Programs

All programs use CEL expressions with activated registry variables:

- **Input Subsidy Program**: Per-hectare scaling for smallholders with productive land
- **Equipment Grant Program**: Experience-based grant for farmers with 2+ years
- **Livestock Support Program**: Per-head scaling for livestock owners
- **Climate Resilience Program**: Targets farms with idle land
- **Aquaculture Support Program**: Activity-specific support for aquaculture farmers

### Seeded Volume Generation

The `SeededFarmGenerator` uses `random.Random(seed=42)` for all structural choices:

- Farm names from Filipino last name pools
- Member names (given + family) from locale-specific pools
- Farm sizes, experience years, GPS coordinates
- Activity quantities (crop areas, livestock counts, aquaculture)

Running the generator twice with the same seed produces identical output.

### Security

| Group                          | Access    |
| ------------------------------ | --------- |
| `spp_security.group_spp_admin` | Full CRUD |

### Dependencies

`spp_starter_farmer_registry`, `spp_demo`, `spp_farmer_registry_cr`, `spp_studio`, `spp_registry_group_hierarchy`, `spp_area`, `spp_programs`
