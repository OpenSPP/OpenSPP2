# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Demo Programs for OpenSPP MIS Demo V2

These programs match the fixed demo stories from spp_demo and provide
predictable program data for sales demos, training, and testing.

Each program is designed to:
1. Work with specific demo personas
2. Demonstrate different CEL expression patterns
3. Link to existing Logic Packs from spp_studio

Program Catalog (6 programs):
1. Universal Child Grant - Member aggregation (child_benefit pack)
2. Elderly Social Pension - Age + constants (social_pension pack)
3. Emergency Relief Fund - Cached metrics (vulnerability_assessment pack)
4. Cash Transfer Program - Poverty threshold (cash_transfer_basic pack)
5. Disability Support Grant - Member existence (disability_assistance pack)
6. Food Assistance - Basic active check (no pack, simple CEL)

CEL Expression Patterns Demonstrated:
- Field comparison: r.active == true
- Computed variables: age >= retirement_age
- Aggregate variables: hh_total_income < poverty_line, child_count > 0
- Compound conditions: dependency_ratio >= 1.5 or (is_female_headed and elderly_count > 0)
- Arithmetic with variables: base_child_grant * child_count, disabled_count * disability_grant_per_member
"""

# Demo programs aligned with spec and Logic Packs
DEMO_PROGRAMS = [
    {
        "id": "universal_child_grant",
        "name": "Universal Child Grant",
        "description": "Cash grant for households with children under 18. "
        "Amount calculated per child using the base_child_grant constant.",
        "target_type": "group",
        "entitlement_amount": 150.0,  # Default, overridden by formula
        # CEL formula: base_child_grant * number of children (using activated variable)
        "entitlement_formula": "base_child_grant * child_count",
        "cycle_duration": 30,  # Monthly
        # CEL: Households with children under 18 (using activated variable)
        # Pattern: Member aggregation via variable
        "cel_expression": "r.is_group == true and child_count > 0",
        # Link to Logic Pack
        "logic_pack": "child_benefit",
        "use_logic_studio": True,
        "logic_name": "Child Benefit Eligibility",
        "expression_type": "filter",
        "stories": ["carlos_elena_morales"],
        "demo_points": [
            "Household-based program",
            "Child-focused eligibility",
            "Dynamic entitlement (per-child calculation)",
            "CEL: Uses child_count variable",
            "Logic Pack: child_benefit",
        ],
    },
    {
        "id": "elderly_social_pension",
        "name": "Elderly Social Pension",
        "description": "Monthly pension for elderly citizens aged 65 and above. "
        "Uses retirement_age constant for eligibility.",
        "target_type": "individual",
        "entitlement_amount": 100.0,
        "entitlement_formula": "elderly_pension_amount",  # Uses constant
        "cycle_duration": 30,
        # CEL: Age >= retirement_age (simplified - no formal pension field exists)
        # Pattern: Age calculation + constant
        "cel_expression": "r.is_group == false and age >= retirement_age",
        # Link to Logic Pack
        "logic_pack": "social_pension",
        "use_logic_studio": True,
        "logic_name": "Social Pension Eligibility",
        "expression_type": "filter",
        "stories": ["rosa_garcia"],
        "demo_points": [
            "Individual targeting",
            "Age-based eligibility",
            "Uses retirement_age constant",
            "Uses age computed variable",
            "Logic Pack: social_pension",
        ],
    },
    {
        "id": "emergency_relief_fund",
        "name": "Emergency Relief Fund",
        "description": "Emergency cash assistance for vulnerable households. "
        "Tiered benefits based on household characteristics.",
        "target_type": "group",
        "entitlement_amount": 400.0,  # Default middle tier
        # CEL formula: Tiered based on household composition
        "entitlement_formula": (
            "dependency_ratio >= 2.0 ? emergency_tier_1 : "
            "dependency_ratio >= 1.0 ? emergency_tier_2 : "
            "emergency_tier_3"
        ),
        "cycle_duration": 15,  # Faster cycles for emergency
        "priority": "high",
        # CEL: High dependency ratio or female-headed with elderly
        # Pattern: Compound conditions using activated variables
        "cel_expression": (
            "r.is_group == true and " "(dependency_ratio >= 1.5 or (is_female_headed and elderly_count > 0))"
        ),
        # Link to Logic Pack
        "logic_pack": "vulnerability_assessment",
        "use_logic_studio": True,
        "logic_name": "Emergency Eligibility",
        "expression_type": "filter",
        "stories": ["ibrahim_hassan"],
        "demo_points": [
            "Emergency response program",
            "Vulnerability-based targeting",
            "Tiered benefit amounts",
            "CEL: dependency_ratio variable",
            "CEL: Compound conditions",
            "Logic Pack: vulnerability_assessment",
        ],
    },
    {
        "id": "cash_transfer_program",
        "name": "Cash Transfer Program",
        "description": "Regular cash transfers to low-income households. "
        "Fixed monthly amount using cash_transfer_amount constant.",
        "target_type": "group",
        "entitlement_amount": 150.0,
        "entitlement_formula": "cash_transfer_amount",  # Uses constant
        "cycle_duration": 30,
        # CEL: Income below poverty line and household size >= 2
        # Pattern: Constant comparison using activated variables
        "cel_expression": "r.is_group == true and hh_total_income < poverty_line and hh_size >= 2",
        # Link to Logic Pack
        "logic_pack": "cash_transfer_basic",
        "use_logic_studio": True,
        "logic_name": "Cash Transfer Eligibility",
        "expression_type": "filter",
        "stories": ["maria_santos", "juan_dela_cruz", "ahmed_said"],
        "demo_points": [
            "Regular cash disbursements",
            "Income-based eligibility",
            "Graduation pathway (Maria Santos)",
            "Uses poverty_line constant",
            "Uses hh_total_income aggregate",
            "Logic Pack: cash_transfer_basic",
        ],
    },
    {
        "id": "disability_support_grant",
        "name": "Disability Support Grant",
        "description": "Support grant for households with disabled members. "
        "Base amount plus per-disabled-member bonus.",
        "target_type": "group",
        "entitlement_amount": 175.0,  # Default: base + 1 member
        # CEL formula: Base + per-member amount (using disabled_count variable)
        "entitlement_formula": "disability_grant_base + (disabled_count * disability_grant_per_member)",
        "cycle_duration": 30,
        # CEL: Household with at least one disabled member (using activated variable)
        # Pattern: Member existence check via variable
        "cel_expression": "r.is_group == true and has_disabled_member",
        # Link to Logic Pack
        "logic_pack": "disability_assistance",
        "use_logic_studio": True,
        "logic_name": "Disability Assistance Eligibility",
        "expression_type": "filter",
        "stories": ["david_martinez"],
        "demo_points": [
            "Disability-focused program",
            "Uses has_disabled_member variable",
            "Per-member benefit calculation",
            "Uses disabled_count aggregate variable",
            "Logic Pack: disability_assistance",
        ],
    },
    {
        "id": "food_assistance",
        "name": "Food Assistance",
        "description": "In-kind food assistance for vulnerable individuals. "
        "Monthly food baskets delivered to eligible beneficiaries.",
        "target_type": "individual",
        "entitlement_type": "in_kind",
        "entitlement_item": "Food Basket",
        "cycle_duration": 30,
        # CEL: Simple active check (no Logic Pack needed)
        # Pattern: Basic field comparison
        "cel_expression": "r.is_registrant == true and r.active == true",
        # No Logic Pack - demonstrates simple inline CEL
        "logic_pack": None,
        "use_logic_studio": False,
        "stories": ["rosa_garcia", "fatima_al_rahman"],
        "demo_points": [
            "In-kind entitlements",
            "Multi-program enrollment",
            "Simple CEL expression",
            "No Logic Pack required",
        ],
    },
]


def get_all_demo_programs():
    """Return all demo program definitions."""
    return DEMO_PROGRAMS


def get_demo_program_by_id(program_id):
    """Get a specific demo program by ID."""
    for program in DEMO_PROGRAMS:
        if program["id"] == program_id:
            return program
    return None


def get_demo_program_by_name(name):
    """Get a specific demo program by name."""
    for program in DEMO_PROGRAMS:
        if program["name"] == name:
            return program
    return None


def get_programs_for_story(story_id):
    """Get all programs that a specific story should be enrolled in."""
    programs = []
    for program in DEMO_PROGRAMS:
        if story_id in program.get("stories", []):
            programs.append(program)
    return programs


def get_programs_by_pack(pack_code):
    """Get all programs that use a specific Logic Pack."""
    programs = []
    for program in DEMO_PROGRAMS:
        if program.get("logic_pack") == pack_code:
            programs.append(program)
    return programs


# Story-to-program enrollment mapping with journey details
STORY_ENROLLMENTS = {
    # Story 1: Maria Santos - Farmer success story with graduation
    # Original Input Subsidy removed; using Cash Transfer to maintain cash-based journey
    "maria_santos": [
        {
            "program": "Cash Transfer Program",
            "enrolled_days_back": 150,
            "graduated_days_back": 30,  # Successfully graduated from the program
            "payments": [
                {"amount": 150, "days_back": 120, "status": "paid"},
                {"amount": 150, "days_back": 90, "status": "paid"},
                {"amount": 150, "days_back": 60, "status": "paid"},
            ],
        }
    ],
    # Story 2: Juan Dela Cruz - Cash Transfer with GRM issue
    "juan_dela_cruz": [
        {
            "program": "Cash Transfer Program",
            "enrolled_days_back": 100,
            "payments": [
                {"amount": 150, "days_back": 70, "status": "paid"},
                {"amount": 150, "days_back": 40, "status": "failed"},
                {"amount": 150, "days_back": 25, "status": "paid"},  # Reprocessed
            ],
        }
    ],
    # Story 3: Rosa Garcia - Elderly Pension + Food Assistance
    "rosa_garcia": [
        {
            "program": "Elderly Social Pension",
            "enrolled_days_back": 180,
            "payments": [
                {"amount": 100, "days_back": 150, "status": "paid"},
                {"amount": 100, "days_back": 120, "status": "paid"},
                {"amount": 100, "days_back": 90, "status": "paid"},
                {"amount": 100, "days_back": 60, "status": "paid"},
            ],
        },
        {
            "program": "Food Assistance",
            "enrolled_days_back": 175,
            "entitlements": [
                {"item": "Food Basket", "days_back": 150, "status": "delivered"},
            ],
        },
    ],
    # Story 6: Carlos Morales - Child Support Grant
    "carlos_elena_morales": [
        {
            "program": "Universal Child Grant",
            "enrolled_days_back": 140,
            "payments": [
                {"amount": 150, "days_back": 100, "status": "paid"},  # 3 children * 50
                {"amount": 150, "days_back": 70, "status": "paid"},
                {"amount": 150, "days_back": 40, "status": "paid"},
                {"amount": 150, "days_back": 10, "status": "paid"},
            ],
        }
    ],
    # Story 7: Ibrahim Hassan - Emergency Relief
    "ibrahim_hassan": [
        {
            "program": "Emergency Relief Fund",
            "enrolled_days_back": 55,
            "payments": [
                {"amount": 400, "days_back": 50, "status": "paid"},  # Tier 2 (score 85)
                {"amount": 400, "days_back": 35, "status": "paid"},
            ],
        }
    ],
    # Story 8: Fatima Al-Rahman - Food Assistance
    "fatima_al_rahman": [
        {
            "program": "Food Assistance",
            "enrolled_days_back": 30,
        }
    ],
    # Story 9: David Martinez - Disability Support Grant (NEW)
    "david_martinez": [
        {
            "program": "Disability Support Grant",
            "enrolled_days_back": 100,
            "payments": [
                {"amount": 175, "days_back": 90, "status": "paid"},  # base 100 + 75*1
                {"amount": 175, "days_back": 60, "status": "paid"},
                {"amount": 175, "days_back": 30, "status": "paid"},
            ],
        }
    ],
    # Background stories
    "ahmed_said": [
        {
            "program": "Cash Transfer Program",
            "enrolled_days_back": 180,
        }
    ],
    "mary_johnson": [
        {
            "program": "Elderly Social Pension",
            "application_days_back": 55,
            "status": "rejected",
            "rejection_reason": "Age requirement not met (55 < 65)",
        }
    ],
}


def get_story_enrollments(story_id):
    """Get enrollment details for a specific story."""
    return STORY_ENROLLMENTS.get(story_id, [])


# Logic Pack codes used by demo programs
DEMO_LOGIC_PACKS = [
    "child_benefit",  # Universal Child Grant
    "social_pension",  # Elderly Social Pension
    "vulnerability_assessment",  # Emergency Relief Fund
    "cash_transfer_basic",  # Cash Transfer Program
    "disability_assistance",  # Disability Support Grant
]


def get_demo_pack_codes():
    """Get list of Logic Pack codes used by demo programs."""
    return DEMO_LOGIC_PACKS.copy()
