# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Demo Programs for OpenSPP Farmer Registry Demo

These programs provide farmer subsidy program data for the Philippines
demo context. Each program is designed to:
1. Work with specific farmer personas
2. Demonstrate CEL expression patterns for agricultural eligibility
3. Link to Logic Packs from spp_studio

Program Catalog (5 programs):
1. Input Subsidy Program - Seed/fertilizer subsidy for smallholders
2. Equipment Grant Program - Farm equipment for experienced farmers
3. Livestock Support Program - Support for livestock farmers
4. Climate Resilience Program - Adaptation support for climate-affected farms
5. Aquaculture Support Program - Support for aquaculture farmers
"""

DEMO_PROGRAMS = [
    {
        "id": "input_subsidy",
        "name": "Input Subsidy Program",
        "description": "Seed and fertilizer subsidy for smallholder farmers. "
        "Eligibility: Farms ≤5 hectares with productive land. "
        "Benefit: Base amount plus per-hectare top-up.",
        "target_type": "group",
        # OP#1122: keep this program on MANUAL entitlement approval (cycles
        # still go through their own approval stage) so the demo can show the
        # full cycle -> entitlement approval chain, not just cycle approval.
        # Every other demo program stays auto-approve.
        "auto_approve_entitlements": False,
        "entitlement_amount": 200.0,
        "entitlement_formula": "input_subsidy_base + (farm_size_hectares * per_hectare_subsidy)",
        # Benefit lines: ₱100 base + ₱50 per hectare. Example: a 2 ha farm gets
        # 100 + (2 * 50) = ₱200. farm_size_hectares is a Float, wired as a
        # multiplier in code (the picker UI lists integer fields only).
        "entitlement_items": [
            {"amount": 100.0},
            {"amount": 50.0, "multiplier_field": "farm_size_hectares"},
        ],
        "cycle_duration": 1,
        "rrule_type": "monthly",
        "cel_expression": "r.is_group == true and is_smallholder and has_productive_land",
        # Compliance: a beneficiary must still operate productive land at the
        # start of each cycle. Lets a farm fall non-compliant mid-program if
        # they stop farming productively (admin marks the farm inactive, all
        # productive segments drop to 0, etc.) — re-evaluation moves them out
        # of the next cycle without a manual de-enrollment.
        "compliance_cel_expression": "has_productive_land == true and farm_size_hectares > 0",
        "logic_pack": "farmer_input_subsidy",
        "use_logic_studio": True,
        "logic_name": "Smallholder Eligibility",
        "expression_type": "filter",
        "stories": [
            "maria_santos",
            "juan_dela_cruz",
            "sofia_martinez",
            "sittie_pangandaman",
        ],
        "demo_points": [
            "Per-hectare benefit scaling",
            "Smallholder targeting",
            "CEL: is_smallholder and has_productive_land",
            "Compliance: ongoing productive-land check",
            "Logic Pack: farmer_input_subsidy",
        ],
    },
    {
        "id": "equipment_grant",
        "name": "Equipment Grant Program",
        "description": "Farm equipment grants for experienced smallholder farmers. "
        "Eligibility: Smallholder farms with 2+ years experience. "
        "Benefit: Fixed equipment grant amount.",
        "target_type": "group",
        "entitlement_amount": 500.0,
        "entitlement_formula": "equipment_grant_amount",
        "cycle_duration": 1,
        "rrule_type": "monthly",
        "cel_expression": "r.is_group == true and is_smallholder and experience_years >= 2",
        # Compliance: the equipment grant is targeted at smallholders with
        # productive land. If the recipient grows past the smallholder
        # threshold or abandons productive land, they should stop receiving
        # disbursements. Re-evaluated per cycle.
        "compliance_cel_expression": "is_smallholder == true and has_productive_land == true",
        "logic_pack": "farmer_equipment_grant",
        "use_logic_studio": True,
        "logic_name": "Experienced Farmer Eligibility",
        "expression_type": "filter",
        "stories": ["juan_dela_cruz", "sittie_pangandaman"],
        "demo_points": [
            "Experience-based eligibility",
            "Fixed grant amount",
            "Multi-criteria targeting",
            "Compliance: must remain smallholder with productive land",
            "Logic Pack: farmer_equipment_grant",
        ],
    },
    {
        "id": "livestock_support",
        "name": "Livestock Support Program",
        "description": "Support program for livestock farmers. "
        "Eligibility: Farms with livestock activities. "
        "Benefit: Base amount plus per-head bonus.",
        "target_type": "group",
        "entitlement_amount": 275.0,
        "entitlement_formula": "livestock_base + (total_livestock_heads * per_head_amount)",
        # Benefit lines: ₱75 base + ₱10 per head. Example: a 20-head farm gets
        # 75 + (20 * 10) = ₱275. total_livestock_heads is an Integer field.
        "entitlement_items": [
            {"amount": 75.0},
            {"amount": 10.0, "multiplier_field": "total_livestock_heads"},
        ],
        "cycle_duration": 1,
        "rrule_type": "monthly",
        "cel_expression": "r.is_group == true and livestock_count > 0",
        "logic_pack": "farmer_livestock_support",
        "use_logic_studio": True,
        "logic_name": "Livestock Farmer Eligibility",
        "expression_type": "filter",
        "stories": ["rosa_garcia", "juan_dela_cruz", "danilo_villanueva"],
        "demo_points": [
            "Activity-based eligibility",
            "Per-head benefit calculation",
            "Livestock count targeting",
            "Logic Pack: farmer_livestock_support",
        ],
    },
    {
        "id": "climate_resilience",
        "name": "Climate Resilience Program",
        "description": "Climate adaptation support for affected smallholders. "
        "Eligibility: Smallholder farms with idle/fallow land. "
        "Benefit: Fixed climate adaptation amount.",
        "target_type": "group",
        "entitlement_amount": 200.0,
        "entitlement_formula": "climate_adaptation_amount",
        "cycle_duration": 1,
        "rrule_type": "monthly",
        "cel_expression": "r.is_group == true and is_smallholder and farm_size_idle > 0",
        "logic_pack": "farmer_climate_resilience",
        "use_logic_studio": True,
        "logic_name": "Climate Vulnerability Eligibility",
        "expression_type": "filter",
        "stories": ["amir_mangudadatu"],
        "demo_points": [
            "Climate vulnerability targeting",
            "Idle land as eligibility indicator",
            "Fixed emergency benefits",
            "Logic Pack: farmer_climate_resilience",
        ],
    },
    {
        "id": "aquaculture_support",
        "name": "Aquaculture Support Program",
        "description": "Support program for aquaculture farmers. "
        "Eligibility: Farms with aquaculture activities. "
        "Benefit: Fixed aquaculture support amount.",
        "target_type": "group",
        "entitlement_amount": 250.0,
        "entitlement_formula": "aquaculture_support_amount",
        "cycle_duration": 1,
        "rrule_type": "monthly",
        "cel_expression": "r.is_group == true and aquaculture_count > 0",
        "logic_pack": "farmer_aquaculture_support",
        "use_logic_studio": True,
        "logic_name": "Aquaculture Farmer Eligibility",
        "expression_type": "filter",
        "stories": ["ramon_dela_cruz"],
        "demo_points": [
            "Aquaculture-specific targeting",
            "Non-crop farming support",
            "Fixed support amount",
            "Logic Pack: farmer_aquaculture_support",
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
    return [p for p in DEMO_PROGRAMS if story_id in p.get("stories", [])]


# Story-to-program enrollment mapping with journey details
STORY_ENROLLMENTS = {
    # Maria Santos - Rice farmer, graduated from Input Subsidy
    "maria_santos": [
        {
            "program": "Input Subsidy Program",
            "enrolled_days_back": 150,
            "graduated_days_back": 30,
            "payments": [
                {"amount": 200, "days_back": 120, "status": "paid"},
                {"amount": 200, "days_back": 90, "status": "paid"},
                {"amount": 200, "days_back": 60, "status": "paid"},
            ],
        }
    ],
    # Juan Dela Cruz - Mixed farmer, active in Input Subsidy + Livestock Support
    "juan_dela_cruz": [
        {
            "program": "Input Subsidy Program",
            "enrolled_days_back": 100,
            "payments": [
                {"amount": 250, "days_back": 70, "status": "paid"},
                {"amount": 250, "days_back": 40, "status": "paid"},
            ],
        },
        {
            "program": "Livestock Support Program",
            "enrolled_days_back": 80,
            "payments": [
                {"amount": 275, "days_back": 50, "status": "paid"},
            ],
        },
    ],
    # Rosa Garcia - Livestock farmer
    "rosa_garcia": [
        {
            "program": "Livestock Support Program",
            "enrolled_days_back": 120,
            "payments": [
                {"amount": 275, "days_back": 90, "status": "paid"},
                {"amount": 275, "days_back": 60, "status": "paid"},
                {"amount": 275, "days_back": 30, "status": "paid"},
            ],
        }
    ],
    # Amir Mangudadatu - Climate-affected farmer
    "amir_mangudadatu": [
        {
            "program": "Climate Resilience Program",
            "enrolled_days_back": 55,
            "payments": [
                {"amount": 200, "days_back": 50, "status": "paid"},
                {"amount": 200, "days_back": 35, "status": "paid"},
            ],
        }
    ],
    # Sofia Martinez - Organic transition farmer
    "sofia_martinez": [
        {
            "program": "Input Subsidy Program",
            "enrolled_days_back": 70,
            "payments": [
                {"amount": 200, "days_back": 45, "status": "paid"},
            ],
        }
    ],
    # Ramon dela Cruz - Aquaculture farmer
    "ramon_dela_cruz": [
        {
            "program": "Aquaculture Support Program",
            "enrolled_days_back": 90,
            "payments": [
                {"amount": 250, "days_back": 60, "status": "paid"},
                {"amount": 250, "days_back": 30, "status": "paid"},
            ],
        }
    ],
    # Sittie Pangandaman - Female farmer, Input Subsidy + Equipment Grant
    "sittie_pangandaman": [
        {
            "program": "Input Subsidy Program",
            "enrolled_days_back": 130,
            "payments": [
                {"amount": 175, "days_back": 100, "status": "paid"},
                {"amount": 175, "days_back": 70, "status": "paid"},
            ],
        },
        {
            "program": "Equipment Grant Program",
            "enrolled_days_back": 60,
            "payments": [
                {"amount": 500, "days_back": 30, "status": "paid"},
            ],
        },
    ],
    # Danilo Villanueva - Edge case, large smallholder
    "danilo_villanueva": [
        {
            "program": "Livestock Support Program",
            "enrolled_days_back": 180,
            "payments": [
                {"amount": 275, "days_back": 150, "status": "paid"},
                {"amount": 275, "days_back": 120, "status": "paid"},
            ],
        }
    ],
}


def get_story_enrollments(story_id):
    """Get enrollment details for a specific story."""
    return STORY_ENROLLMENTS.get(story_id, [])


def _get_cycles_needed_per_program():
    """Derive the number of cycles needed per program from story data."""
    needed = {}
    for enrollments in STORY_ENROLLMENTS.values():
        for enrollment in enrollments:
            program_name = enrollment.get("program", "")
            payment_count = len(enrollment.get("payments", []))
            needed[program_name] = max(needed.get(program_name, 0), payment_count)
    return needed


# Logic Pack codes used by demo programs
DEMO_LOGIC_PACKS = [
    "farmer_input_subsidy",
    "farmer_equipment_grant",
    "farmer_livestock_support",
    "farmer_climate_resilience",
    "farmer_aquaculture_support",
]
