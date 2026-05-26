# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Household Blueprint Definitions for Deterministic Demo Data Generation

Each blueprint defines the structure of a household type:
- Number and composition of members (roles, genders, age ranges)
- Income bracket and geographic zone
- Program eligibility flags

Blueprints are 100% deterministic — no randomness in definitions.
The SeededVolumeGenerator multiplies each blueprint by its `count`
to produce the target number of households.

Total: ~28 blueprints, ~730 households, ~2555 members
"""

# Program IDs matching DEMO_PROGRAMS in demo_programs.py
_UCG = "universal_child_grant"
_CCG = "conditional_child_grant"
_ESP = "elderly_social_pension"
_ERF = "emergency_relief_fund"
_CTP = "cash_transfer_program"
_FA = "food_assistance"

HOUSEHOLD_BLUEPRINTS = [
    # =========================================================================
    # Young Families (6 blueprints, ~195 households)
    # =========================================================================
    {
        "id": "bp_01_young_couple_1child_urban_low",
        "label": "Young couple, 1 toddler, urban, low income",
        "count": 40,
        "zone": "urban",
        "income_bracket": "low",
        "income_range": (8000, 15000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (25, 35)},
            {"role": "spouse", "gender": "female", "age_range": (23, 33)},
            {"role": "child", "gender": "any", "age_range": (1, 4)},
        ],
        "eligibility": {_UCG: True, _CCG: True, _CTP: True, _ERF: False},
    },
    {
        "id": "bp_02_young_couple_2children_rural_vlow",
        "label": "Young couple, 2 children, rural, very low income",
        "count": 45,
        "zone": "rural",
        "income_bracket": "very_low",
        "income_range": (3000, 8000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (27, 38)},
            {"role": "spouse", "gender": "female", "age_range": (25, 36)},
            {"role": "child", "gender": "any", "age_range": (3, 7)},
            {"role": "child", "gender": "any", "age_range": (6, 10)},
        ],
        "eligibility": {_UCG: True, _CTP: True, _ERF: True},
    },
    {
        "id": "bp_03_single_mother_2children_urban_low",
        "label": "Single mother, 2 children, urban, low income",
        "count": 35,
        "zone": "urban",
        "income_bracket": "low",
        "income_range": (6000, 12000),
        "is_female_headed": True,
        "members": [
            {"role": "head", "gender": "female", "age_range": (25, 40)},
            {"role": "child", "gender": "any", "age_range": (2, 6)},
            {"role": "child", "gender": "any", "age_range": (5, 9)},
        ],
        "eligibility": {_UCG: True, _CTP: True, _ERF: True},
    },
    {
        "id": "bp_04_young_couple_3children_rural_low",
        "label": "Young couple, 3 children, rural, low income",
        "count": 30,
        "zone": "rural",
        "income_bracket": "low",
        "income_range": (5000, 10000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (28, 40)},
            {"role": "spouse", "gender": "female", "age_range": (26, 38)},
            {"role": "child", "gender": "any", "age_range": (1, 4)},
            {"role": "child", "gender": "any", "age_range": (4, 8)},
            {"role": "child", "gender": "any", "age_range": (8, 12)},
        ],
        "eligibility": {_UCG: True, _CCG: True, _CTP: True, _ERF: False},
    },
    {
        "id": "bp_05_single_father_1child_periurban_mod",
        "label": "Single father, 1 child, peri-urban, moderate income",
        "count": 20,
        "zone": "peri_urban",
        "income_bracket": "moderate",
        "income_range": (15000, 25000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (30, 45)},
            {"role": "child", "gender": "any", "age_range": (3, 8)},
        ],
        "eligibility": {_UCG: True, _CTP: False, _ERF: False},
    },
    {
        "id": "bp_06_young_couple_newborn_rural_vlow",
        "label": "Young couple with newborn + toddler, rural, very low income",
        "count": 25,
        "zone": "rural",
        "income_bracket": "very_low",
        "income_range": (2000, 6000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (22, 30)},
            {"role": "spouse", "gender": "female", "age_range": (20, 28)},
            {"role": "child", "gender": "any", "age_range": (0, 1)},
            {"role": "child", "gender": "any", "age_range": (1, 3)},
        ],
        "eligibility": {_UCG: True, _CCG: True, _CTP: True, _ERF: True},
    },
    # =========================================================================
    # Middle-age Families (6 blueprints, ~150 households)
    # =========================================================================
    {
        "id": "bp_07_couple_teen_children_urban_mod",
        "label": "Couple with 2 teenagers, urban, moderate income",
        "count": 40,
        "zone": "urban",
        "income_bracket": "moderate",
        "income_range": (18000, 30000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (40, 50)},
            {"role": "spouse", "gender": "female", "age_range": (38, 48)},
            {"role": "child", "gender": "any", "age_range": (13, 16)},
            {"role": "child", "gender": "any", "age_range": (15, 17)},
        ],
        "eligibility": {_UCG: True, _CTP: False, _ERF: False},
    },
    {
        "id": "bp_08_couple_mixed_ages_rural_low",
        "label": "Couple with children (5-17), rural, low income",
        "count": 35,
        "zone": "rural",
        "income_bracket": "low",
        "income_range": (7000, 14000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (35, 48)},
            {"role": "spouse", "gender": "female", "age_range": (33, 46)},
            {"role": "child", "gender": "any", "age_range": (4, 7)},
            {"role": "child", "gender": "any", "age_range": (10, 14)},
            {"role": "child", "gender": "any", "age_range": (15, 17)},
        ],
        "eligibility": {_UCG: True, _CTP: True, _ERF: False},
    },
    {
        "id": "bp_09_couple_adult_child_periurban_mod",
        "label": "Couple with adult child + teen, peri-urban, moderate income",
        "count": 25,
        "zone": "peri_urban",
        "income_bracket": "moderate",
        "income_range": (16000, 28000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (42, 55)},
            {"role": "spouse", "gender": "female", "age_range": (40, 53)},
            {"role": "adult", "gender": "any", "age_range": (19, 23)},
            {"role": "child", "gender": "any", "age_range": (13, 17)},
        ],
        "eligibility": {_UCG: True, _CTP: False, _ERF: False},
    },
    {
        "id": "bp_10_large_family_6members_rural_vlow",
        "label": "Large family, 4 children, rural, very low income",
        "count": 20,
        "zone": "rural",
        "income_bracket": "very_low",
        "income_range": (2000, 7000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (35, 50)},
            {"role": "spouse", "gender": "female", "age_range": (33, 48)},
            {"role": "child", "gender": "any", "age_range": (2, 5)},
            {"role": "child", "gender": "any", "age_range": (5, 9)},
            {"role": "child", "gender": "any", "age_range": (9, 13)},
            {"role": "child", "gender": "any", "age_range": (13, 17)},
        ],
        "eligibility": {_UCG: True, _CTP: True, _ERF: True},
    },
    # =========================================================================
    # Elderly Households (5 blueprints, ~110 households)
    # =========================================================================
    {
        "id": "bp_13_elderly_couple_urban_low",
        "label": "Elderly couple, urban, low income",
        "count": 30,
        "zone": "urban",
        "income_bracket": "low",
        "income_range": (4000, 10000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (65, 78)},
            {"role": "spouse", "gender": "female", "age_range": (63, 76)},
        ],
        "eligibility": {_UCG: False, _ESP: True, _CTP: False, _ERF: False},
    },
    {
        "id": "bp_14_elderly_single_rural_vlow",
        "label": "Single elderly, rural, very low income",
        "count": 25,
        "zone": "rural",
        "income_bracket": "very_low",
        "income_range": (1000, 5000),
        "members": [
            {"role": "head", "gender": "any", "age_range": (68, 82)},
        ],
        "eligibility": {_UCG: False, _ESP: True, _CTP: False, _ERF: True},
    },
    {
        "id": "bp_15_elderly_couple_grandchild_periurban_low",
        "label": "Elderly couple raising grandchild, peri-urban, low income",
        "count": 20,
        "zone": "peri_urban",
        "income_bracket": "low",
        "income_range": (5000, 12000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (65, 75)},
            {"role": "spouse", "gender": "female", "age_range": (63, 73)},
            {"role": "child", "gender": "any", "age_range": (5, 12)},
        ],
        "eligibility": {_UCG: True, _ESP: True, _CTP: False, _ERF: False},
    },
    {
        "id": "bp_17_elderly_with_adult_child_rural_mod",
        "label": "Elderly with adult child, rural, moderate income",
        "count": 20,
        "zone": "rural",
        "income_bracket": "moderate",
        "income_range": (12000, 22000),
        "members": [
            {"role": "head", "gender": "any", "age_range": (66, 75)},
            {"role": "adult", "gender": "any", "age_range": (35, 48)},
        ],
        "eligibility": {_UCG: False, _ESP: True, _CTP: False, _ERF: False},
    },
    # =========================================================================
    # Working-age Households (6 blueprints, ~125 households)
    # =========================================================================
    {
        "id": "bp_18_couple_no_children_urban_above_mod",
        "label": "Working couple, no children, urban, above moderate (control)",
        "count": 30,
        "zone": "urban",
        "income_bracket": "above_moderate",
        "income_range": (30000, 60000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (28, 45)},
            {"role": "spouse", "gender": "female", "age_range": (26, 43)},
        ],
        "eligibility": {_UCG: False, _CTP: False, _ERF: False},
    },
    {
        "id": "bp_19_couple_no_children_rural_mod",
        "label": "Working couple, no children, rural, moderate (borderline)",
        "count": 25,
        "zone": "rural",
        "income_bracket": "moderate",
        "income_range": (14000, 24000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (30, 50)},
            {"role": "spouse", "gender": "female", "age_range": (28, 48)},
        ],
        "eligibility": {_UCG: False, _CTP: False, _ERF: False},
    },
    {
        "id": "bp_20_single_adult_urban_above_mod",
        "label": "Single working adult, urban (control)",
        "count": 20,
        "zone": "urban",
        "income_bracket": "above_moderate",
        "income_range": (25000, 50000),
        "members": [
            {"role": "head", "gender": "any", "age_range": (25, 50)},
        ],
        "eligibility": {_UCG: False, _CTP: False, _ERF: False},
    },
    {
        "id": "bp_21_extended_family_rural_low",
        "label": "Extended family (head+spouse+elder+2 children), rural, low income",
        "count": 15,
        "zone": "rural",
        "income_bracket": "low",
        "income_range": (6000, 13000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (35, 48)},
            {"role": "spouse", "gender": "female", "age_range": (33, 46)},
            {"role": "elderly", "gender": "any", "age_range": (65, 80)},
            {"role": "child", "gender": "any", "age_range": (4, 9)},
            {"role": "child", "gender": "any", "age_range": (8, 13)},
        ],
        "eligibility": {_UCG: True, _CTP: True, _ERF: False},
    },
    {
        "id": "bp_23_couple_1child_periurban_low",
        "label": "Standard family, 1 child, peri-urban, low income",
        "count": 25,
        "zone": "peri_urban",
        "income_bracket": "low",
        "income_range": (8000, 16000),
        "members": [
            {"role": "head", "gender": "male", "age_range": (30, 45)},
            {"role": "spouse", "gender": "female", "age_range": (28, 43)},
            {"role": "child", "gender": "any", "age_range": (8, 14)},
        ],
        "eligibility": {_UCG: True, _CTP: True, _ERF: False},
    },
    # =========================================================================
    # Special Cases (5 blueprints, ~100 households)
    # =========================================================================
    {
        "id": "bp_24_emergency_displaced_rural_vlow",
        "label": "Displaced family, high vulnerability, rural, very low income",
        "count": 20,
        "zone": "rural",
        "income_bracket": "very_low",
        "income_range": (1000, 4000),
        "is_female_headed": True,
        "members": [
            {"role": "head", "gender": "female", "age_range": (28, 45)},
            {"role": "child", "gender": "any", "age_range": (2, 6)},
            {"role": "child", "gender": "any", "age_range": (5, 10)},
            {"role": "child", "gender": "any", "age_range": (9, 15)},
        ],
        "eligibility": {_UCG: True, _CTP: True, _ERF: True},
    },
    {
        "id": "bp_25_food_only_individual_urban_vlow",
        "label": "Single individual, urban, very low income (food assistance only)",
        "count": 30,
        "zone": "urban",
        "income_bracket": "very_low",
        "income_range": (1000, 5000),
        "members": [
            {"role": "head", "gender": "any", "age_range": (20, 55)},
        ],
        "eligibility": {_UCG: False, _CTP: False, _ERF: False},
        "individual_food_assistance": True,
    },
    {
        "id": "bp_26_food_only_individual_rural_vlow",
        "label": "Single individual, rural, very low income (food assistance only)",
        "count": 25,
        "zone": "rural",
        "income_bracket": "very_low",
        "income_range": (500, 4000),
        "members": [
            {"role": "head", "gender": "any", "age_range": (22, 60)},
        ],
        "eligibility": {_UCG: False, _CTP: False, _ERF: False},
        "individual_food_assistance": True,
    },
    {
        "id": "bp_28_multi_program_household_rural_vlow",
        "label": "Maximum eligibility household, rural, very low income",
        "count": 15,
        "zone": "rural",
        "income_bracket": "very_low",
        "income_range": (1000, 5000),
        "is_female_headed": True,
        "members": [
            {"role": "head", "gender": "female", "age_range": (30, 45)},
            {"role": "child", "gender": "any", "age_range": (2, 6)},
            {"role": "child", "gender": "any", "age_range": (5, 10)},
            {"role": "elderly", "gender": "any", "age_range": (68, 80)},
        ],
        "eligibility": {_UCG: True, _CCG: True, _ESP: True, _CTP: True, _ERF: True},
    },
]


def get_all_blueprints():
    """Return all household blueprint definitions."""
    return HOUSEHOLD_BLUEPRINTS


def get_total_household_count():
    """Return total number of households across all blueprints."""
    return sum(bp["count"] for bp in HOUSEHOLD_BLUEPRINTS)


def get_total_member_estimate():
    """Return estimated total number of individual members."""
    return sum(bp["count"] * len(bp["members"]) for bp in HOUSEHOLD_BLUEPRINTS)


def get_blueprints_by_eligibility(program_id):
    """Return blueprints where households are eligible for the given program."""
    return [bp for bp in HOUSEHOLD_BLUEPRINTS if bp["eligibility"].get(program_id)]
