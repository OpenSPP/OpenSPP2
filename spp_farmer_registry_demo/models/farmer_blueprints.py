# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Farmer Blueprint Definitions for Deterministic Demo Data Generation

Each blueprint defines the structure of a farm archetype:
- Farm type, size range, experience range
- Head gender and household members (roles, genders, age ranges)
- Agricultural activities (crops, livestock, aquaculture)
- Land tenure and zone (rural/peri-urban)
- Program eligibility flags

Blueprints are 100% deterministic definitions — no randomness here.
The SeededFarmGenerator multiplies each blueprint by its `count`
to produce the target number of farms.

Total: ~21 blueprints, ~730 farms
"""

# Program IDs matching DEMO_PROGRAMS in demo_programs.py
_INPUT_SUBSIDY = "input_subsidy"
_EQUIPMENT_GRANT = "equipment_grant"
_LIVESTOCK = "livestock_support"
_CLIMATE = "climate_resilience"
_AQUACULTURE = "aquaculture_support"

FARMER_BLUEPRINTS = [
    # =========================================================================
    # Small Crop Farmers (6 blueprints, ~210 farms)
    # =========================================================================
    {
        "id": "bp_01_small_rice_farmer_female",
        "label": "Small female rice farmer, 1-2ha, lowland",
        "count": 40,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (1.0, 2.0),
        "experience_range": (5, 15),
        "head_gender": "female",
        "members": [
            {"role": "head", "gender": "female", "age_range": (30, 50)},
            {"role": "spouse", "gender": "male", "age_range": (30, 55)},
        ],
        "activities": [
            {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.8},
        ],
        "land_tenure": "self",
        "land_use": "cultivation",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_02_small_rice_farmer_male",
        "label": "Small male rice farmer, 1-3ha, lowland",
        "count": 45,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (1.0, 3.0),
        "experience_range": (3, 20),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (28, 55)},
            {"role": "spouse", "gender": "female", "age_range": (25, 50)},
            {"role": "child", "gender": "any", "age_range": (5, 18)},
        ],
        "activities": [
            {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.7},
            {"type": "crop", "species_code": "vegetables", "area_pct": 0.2},
        ],
        "land_tenure": "family",
        "land_use": "cultivation",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_03_small_maize_farmer",
        "label": "Small maize farmer, 1-2ha, upland",
        "count": 35,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (1.0, 2.5),
        "experience_range": (4, 18),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (30, 55)},
            {"role": "spouse", "gender": "female", "age_range": (28, 50)},
        ],
        "activities": [
            {"type": "crop", "species_code": "maize", "area_pct": 0.9},
        ],
        "land_tenure": "self",
        "land_use": "cultivation",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_04_vegetable_farmer_female",
        "label": "Small female vegetable farmer, 0.5-1.5ha",
        "count": 30,
        "zone": "peri_urban",
        "farm_type": "crop",
        "size_range": (0.5, 1.5),
        "experience_range": (2, 12),
        "head_gender": "female",
        "members": [
            {"role": "head", "gender": "female", "age_range": (25, 45)},
            {"role": "child", "gender": "any", "age_range": (3, 15)},
        ],
        "activities": [
            {"type": "crop", "species_code": "vegetables", "area_pct": 0.9},
        ],
        "land_tenure": "leased",
        "land_use": "cultivation",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_05_rice_and_vegetable_farmer",
        "label": "Rice and vegetable farmer, 2-4ha",
        "count": 35,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (2.0, 4.0),
        "experience_range": (8, 25),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (35, 58)},
            {"role": "spouse", "gender": "female", "age_range": (32, 55)},
            {"role": "child", "gender": "any", "age_range": (8, 20)},
            {"role": "child", "gender": "any", "age_range": (5, 16)},
        ],
        "activities": [
            {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.5},
            {"type": "crop", "species_code": "vegetables", "area_pct": 0.3},
        ],
        "land_tenure": "family",
        "land_use": "cultivation",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_06_highland_crop_farmer",
        "label": "Highland crop farmer, 1-2ha, Cordillera",
        "count": 25,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (1.0, 2.0),
        "experience_range": (5, 20),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (30, 55)},
            {"role": "spouse", "gender": "female", "age_range": (28, 52)},
            {"role": "child", "gender": "any", "age_range": (6, 18)},
        ],
        "activities": [
            {"type": "crop", "species_code": "vegetables", "area_pct": 0.6},
            {"type": "crop", "species_code": "maize", "area_pct": 0.3},
        ],
        "land_tenure": "self",
        "land_use": "cultivation",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    # =========================================================================
    # Mixed Farmers - Crop + Livestock (4 blueprints, ~130 farms)
    # =========================================================================
    {
        "id": "bp_07_mixed_rice_chicken",
        "label": "Mixed rice + chicken farmer, 2-3ha",
        "count": 35,
        "zone": "rural",
        "farm_type": "mixed",
        "size_range": (2.0, 3.5),
        "experience_range": (5, 20),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (30, 55)},
            {"role": "spouse", "gender": "female", "age_range": (28, 52)},
            {"role": "child", "gender": "any", "age_range": (5, 18)},
        ],
        "activities": [
            {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.5},
            {"type": "livestock", "species_code": "chickens", "quantity_range": (20, 80)},
        ],
        "land_tenure": "family",
        "land_use": "mixed",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: True,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_08_mixed_maize_goat",
        "label": "Mixed maize + goat farmer, 1.5-3ha",
        "count": 30,
        "zone": "rural",
        "farm_type": "mixed",
        "size_range": (1.5, 3.0),
        "experience_range": (4, 18),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (28, 50)},
            {"role": "spouse", "gender": "female", "age_range": (25, 48)},
        ],
        "activities": [
            {"type": "crop", "species_code": "maize", "area_pct": 0.6},
            {"type": "livestock", "species_code": "goats", "quantity_range": (5, 25)},
        ],
        "land_tenure": "self",
        "land_use": "mixed",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: True,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_09_mixed_rice_cattle_female",
        "label": "Female-headed mixed rice + cattle, 2-4ha",
        "count": 30,
        "zone": "rural",
        "farm_type": "mixed",
        "size_range": (2.0, 4.0),
        "experience_range": (8, 22),
        "head_gender": "female",
        "members": [
            {"role": "head", "gender": "female", "age_range": (35, 55)},
            {"role": "child", "gender": "any", "age_range": (10, 22)},
            {"role": "child", "gender": "any", "age_range": (8, 18)},
        ],
        "activities": [
            {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.5},
            {"type": "livestock", "species_code": "cattle", "quantity_range": (3, 12)},
        ],
        "land_tenure": "family",
        "land_use": "mixed",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: True,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_10_mixed_vegetable_chicken",
        "label": "Mixed vegetable + chicken, 1-2ha, peri-urban",
        "count": 35,
        "zone": "peri_urban",
        "farm_type": "mixed",
        "size_range": (1.0, 2.0),
        "experience_range": (3, 15),
        "head_gender": "female",
        "members": [
            {"role": "head", "gender": "female", "age_range": (28, 48)},
            {"role": "spouse", "gender": "male", "age_range": (30, 52)},
        ],
        "activities": [
            {"type": "crop", "species_code": "vegetables", "area_pct": 0.6},
            {"type": "livestock", "species_code": "chickens", "quantity_range": (10, 40)},
        ],
        "land_tenure": "leased",
        "land_use": "mixed",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: True,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    # =========================================================================
    # Livestock-Focused Farmers (3 blueprints, ~90 farms)
    # =========================================================================
    {
        "id": "bp_11_goat_farmer",
        "label": "Goat farmer, 1-2ha pasture",
        "count": 30,
        "zone": "rural",
        "farm_type": "livestock",
        "size_range": (1.0, 2.5),
        "experience_range": (5, 20),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (30, 55)},
            {"role": "spouse", "gender": "female", "age_range": (28, 52)},
        ],
        "activities": [
            {"type": "livestock", "species_code": "goats", "quantity_range": (10, 40)},
        ],
        "land_tenure": "self",
        "land_use": "pasture",
        "eligibility": {
            _INPUT_SUBSIDY: False,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: True,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_12_cattle_rancher",
        "label": "Cattle rancher, 3-6ha pasture",
        "count": 25,
        "zone": "rural",
        "farm_type": "livestock",
        "size_range": (3.0, 6.0),
        "experience_range": (10, 30),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (35, 60)},
            {"role": "spouse", "gender": "female", "age_range": (32, 55)},
            {"role": "child", "gender": "any", "age_range": (10, 22)},
        ],
        "activities": [
            {"type": "livestock", "species_code": "cattle", "quantity_range": (5, 20)},
            {"type": "livestock", "species_code": "chickens", "quantity_range": (10, 30)},
        ],
        "land_tenure": "family",
        "land_use": "pasture",
        "eligibility": {
            _INPUT_SUBSIDY: False,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: True,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_13_chicken_farmer_female",
        "label": "Female chicken farmer, 0.5-1.5ha",
        "count": 35,
        "zone": "peri_urban",
        "farm_type": "livestock",
        "size_range": (0.5, 1.5),
        "experience_range": (2, 12),
        "head_gender": "female",
        "members": [
            {"role": "head", "gender": "female", "age_range": (25, 50)},
        ],
        "activities": [
            {"type": "livestock", "species_code": "chickens", "quantity_range": (30, 100)},
        ],
        "land_tenure": "leased",
        "land_use": "pasture",
        "eligibility": {
            _INPUT_SUBSIDY: False,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: True,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    # =========================================================================
    # Aquaculture Farmers (2 blueprints, ~55 farms)
    # =========================================================================
    {
        "id": "bp_14_fishpond_farmer",
        "label": "Fishpond farmer, 0.5-2ha, tilapia",
        "count": 30,
        "zone": "rural",
        "farm_type": "aquaculture",
        "size_range": (0.5, 2.0),
        "experience_range": (3, 15),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (30, 55)},
            {"role": "spouse", "gender": "female", "age_range": (28, 52)},
        ],
        "activities": [
            {"type": "aquaculture", "species_code": "tilapia", "quantity_range": (2000, 8000)},
        ],
        "land_tenure": "leased",
        "land_use": "aquaculture",
        "eligibility": {
            _INPUT_SUBSIDY: False,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: True,
        },
    },
    {
        "id": "bp_15_mixed_fishpond_rice",
        "label": "Mixed fish + rice farmer, 1-3ha",
        "count": 25,
        "zone": "rural",
        "farm_type": "mixed",
        "size_range": (1.0, 3.0),
        "experience_range": (5, 18),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (32, 55)},
            {"role": "spouse", "gender": "female", "age_range": (30, 52)},
            {"role": "child", "gender": "any", "age_range": (5, 18)},
        ],
        "activities": [
            {"type": "aquaculture", "species_code": "tilapia", "quantity_range": (1000, 5000)},
            {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.4},
        ],
        "land_tenure": "self",
        "land_use": "mixed",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: True,
        },
    },
    # =========================================================================
    # Large / Commercial Farms (2 blueprints, ~50 farms)
    # =========================================================================
    {
        "id": "bp_16_large_commercial_crop",
        "label": "Large commercial crop farm, 5-10ha",
        "count": 25,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (5.0, 10.0),
        "experience_range": (15, 35),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (40, 65)},
            {"role": "spouse", "gender": "female", "age_range": (38, 60)},
            {"role": "child", "gender": "any", "age_range": (15, 28)},
            {"role": "child", "gender": "any", "age_range": (12, 25)},
        ],
        "activities": [
            {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.4},
            {"type": "crop", "species_code": "maize", "area_pct": 0.3},
            {"type": "crop", "species_code": "vegetables", "area_pct": 0.2},
        ],
        "land_tenure": "self",
        "land_use": "cultivation",
        "eligibility": {
            _INPUT_SUBSIDY: False,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_17_large_mixed_commercial",
        "label": "Large mixed commercial farm, 5-8ha",
        "count": 25,
        "zone": "rural",
        "farm_type": "mixed",
        "size_range": (5.0, 8.0),
        "experience_range": (12, 30),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (38, 60)},
            {"role": "spouse", "gender": "female", "age_range": (35, 58)},
            {"role": "child", "gender": "any", "age_range": (12, 25)},
        ],
        "activities": [
            {"type": "crop", "species_code": "maize", "area_pct": 0.4},
            {"type": "livestock", "species_code": "cattle", "quantity_range": (10, 30)},
            {"type": "livestock", "species_code": "goats", "quantity_range": (15, 40)},
        ],
        "land_tenure": "family",
        "land_use": "mixed",
        "eligibility": {
            _INPUT_SUBSIDY: False,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: True,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    # =========================================================================
    # Climate-Affected / Idle Land (2 blueprints, ~55 farms)
    # =========================================================================
    {
        "id": "bp_18_drought_affected",
        "label": "Drought-affected farmer, 2-4ha, idle land",
        "count": 30,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (2.0, 4.0),
        "experience_range": (8, 25),
        "head_gender": "male",
        "idle_pct": 0.3,
        "members": [
            {"role": "head", "gender": "male", "age_range": (35, 60)},
            {"role": "spouse", "gender": "female", "age_range": (32, 55)},
            {"role": "child", "gender": "any", "age_range": (8, 20)},
        ],
        "activities": [
            {"type": "crop", "species_code": "maize", "area_pct": 0.5},
        ],
        "land_tenure": "family",
        "land_use": "fallow",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: False,
            _CLIMATE: True,
            _AQUACULTURE: False,
        },
    },
    {
        "id": "bp_19_flood_affected_female",
        "label": "Flood-affected female farmer, 1-2ha",
        "count": 25,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (1.0, 2.5),
        "experience_range": (5, 18),
        "head_gender": "female",
        "idle_pct": 0.4,
        "members": [
            {"role": "head", "gender": "female", "age_range": (30, 55)},
            {"role": "child", "gender": "any", "age_range": (5, 18)},
        ],
        "activities": [
            {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.4},
        ],
        "land_tenure": "self",
        "land_use": "fallow",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: False,
            _CLIMATE: True,
            _AQUACULTURE: False,
        },
    },
    # =========================================================================
    # New / Young Farmers (1 blueprint, ~40 farms)
    # =========================================================================
    {
        "id": "bp_20_young_farmer",
        "label": "Young farmer, <2ha, <3yr experience",
        "count": 40,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (0.5, 2.0),
        "experience_range": (0, 3),
        "head_gender": "any",
        "members": [
            {"role": "head", "gender": "any", "age_range": (18, 30)},
        ],
        "activities": [
            {"type": "crop", "species_code": "vegetables", "area_pct": 0.7},
        ],
        "land_tenure": "leased",
        "land_use": "cultivation",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: False,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
    # =========================================================================
    # Elderly Farmers (1 blueprint, ~30 farms)
    # =========================================================================
    {
        "id": "bp_21_elderly_farmer",
        "label": "Elderly farmer, 1-3ha, 20+ yr experience",
        "count": 30,
        "zone": "rural",
        "farm_type": "crop",
        "size_range": (1.0, 3.0),
        "experience_range": (20, 40),
        "head_gender": "male",
        "members": [
            {"role": "head", "gender": "male", "age_range": (60, 78)},
            {"role": "spouse", "gender": "female", "age_range": (55, 75)},
        ],
        "activities": [
            {"type": "crop", "species_code": "rice_irrigated", "area_pct": 0.6},
        ],
        "land_tenure": "self",
        "land_use": "cultivation",
        "eligibility": {
            _INPUT_SUBSIDY: True,
            _EQUIPMENT_GRANT: True,
            _LIVESTOCK: False,
            _CLIMATE: False,
            _AQUACULTURE: False,
        },
    },
]


def get_total_farm_count():
    """Return total number of farms that will be generated."""
    return sum(bp["count"] for bp in FARMER_BLUEPRINTS)


def get_total_member_count():
    """Return estimated total number of individual members."""
    return sum(bp["count"] * len(bp["members"]) for bp in FARMER_BLUEPRINTS)
