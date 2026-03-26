Demo data generator for the OpenSPP Farmer Registry. Creates 8 named farmer personas with complete Philippine farm profiles, 5 agricultural subsidy programs with CEL eligibility expressions, and optionally generates ~730 volume farms from deterministic blueprints using a seeded random generator (seed=42) for reproducible output.

### Key Capabilities

- Generate 8 fixed story farms with complete profiles (Maria Santos, Juan Dela Cruz, Rosa Garcia, Amir Mangudadatu, Sofia Martinez, Ramon dela Cruz, Sittie Pangandaman, Danilo Villanueva)
- Create 5 demo programs (Input Subsidy, Equipment Grant, Livestock Support, Climate Resilience, Aquaculture Support) with CEL-based eligibility
- Generate ~730 deterministic volume farms from 21 blueprints via seeded random generator (seed=42)
- Create 2 farm cooperatives (Nueva Ecija Rice Cooperative, BARMM Farmers Federation) demonstrating group-of-groups hierarchy
- Include 3 edge case personas for testing eligibility boundaries (large commercial, idle land, new farmer)
- Install Logic Packs with CEL expressions for eligibility and benefit calculations
- Distribute farms geographically across 8 Philippine provinces with GPS coordinates

### Key Models

| Model | Description |
| --- | --- |
| `spp.farmer.demo.generator` | Core demo generator with all generation logic |
| `spp.farmer.demo.wizard` | Wizard interface (inherits from generator) |

### Configuration

After installing:

1. Navigate to **Settings > Demo Data > Load Farmer Registry Demo**
2. The wizard opens with options for demo mode (Sales, Training, Testing, Complete)
3. Click "Load Demo Data" to generate

### Dependencies

`spp_starter_farmer_registry`, `spp_demo`, `spp_farmer_registry_cr`, `spp_studio`, `spp_registry_group_hierarchy`, `spp_area`, `spp_programs`
