# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Fixed Demo Stories for OpenSPP Demo Generator V2

These stories provide predictable, documented personas for:
- Sales demos ("Search for Maria Santos...")
- Partner onboarding/training
- CI/Testing verification

Each story demonstrates a specific workflow or feature set.
Names are locale-aware: fil_PH (default), si_LK, fr_TG.
"""

import copy

# Reserved names that should not be used for random volume generation
RESERVED_NAMES = [
    # Household group names (family name only)
    "Santos",
    "Dela Cruz",
    "Morales",
    "Aquino",
    "Reyes",
    "Bautista",
    "Pangilinan",
    "Navarro",
    "Gutierrez",
    "Martinez",
    "Castillo",
    # Individual story names
    "Maria Santos",
    "Juan Dela Cruz",
    "Rosa Garcia",
    "Pedro Reyes",
    "Ana Mendoza",
    "Cara Okafor",
    "Carlos Morales",
    "Elena Morales",
    "Ramon Gutierrez",
    "Teresa Villanueva",
    "Luis Fernandez",
    "Lorna Pascual",
    "Roberto Castillo",
    "Maricel Ramos",
    "Eduardo Tan",
    # Additional household members
    "Marco Morales",
    "Sofia Morales",
    "Luis Morales",
    # Aquino household (amina_osman_household)
    "Rosario Aquino",
    "Daniel Aquino",
    "Angela Aquino",
    "Rafael Aquino",
    # Reyes multigenerational household
    "Jose Reyes Sr",
    "Carmen Reyes",
    "Miguel Reyes",
    "Teresa Reyes",
    "Jose Reyes Jr",
    "Lucia Reyes",
    "Antonio Reyes",
    "Isabella Reyes",
    "Eduardo Bautista",
    "Carmen Bautista",
    "Patricia Bautista",
    "Fernando Bautista",
    "Lucia Bautista",
    "Rosalie Bautista",
    "Antonio Bautista",
    "Manuel Pangilinan",
    "Gloria Pangilinan",
    "Ricardo Navarro",
    "Lourdes Navarro",
    "Eduardo Navarro",
    "Cristina Navarro",
    # Story 9 - Martinez household
    "David Martinez",
    "Sofia Martinez",
    "Miguel Martinez",
    # Tutorial families (Get Started > first_program)
    "Garcia Family",
    "Roberto Garcia",
    "Maria Garcia",
    "Carlos Garcia",
    "Tolentino Family",
    "Jose Tolentino",
    "Ana Tolentino",
    "Mia Tolentino",
    "Salazar Family",
    "Pedro Salazar",
    "Teresa Salazar",
    "Juan Salazar",
    "Maria Salazar",
    "Mercado Family",
    "Ramon Mercado",
    "Elena Mercado",
    "Lucia Mercado",
    "Ramos Family",
    "Antonio Ramos",
    "Rosa Ramos",
    "Diego Ramos",
    "Carla Ramos",
]

DEMO_STORIES = [
    {
        "id": "maria_santos",
        "name": "Santos",
        "type": "household",
        "story_title": "The Success Story",
        "story_description": "Happy path from registration to graduation",
        "profile": {
            "ids": [{"type": "household_id", "value": "HH-100"}],
            "head": {"name": "Maria Santos", "gender": "female", "age": 42},
            "spouse": {"name": "Ricardo Santos", "gender": "male", "age": 44},
            "children": [
                {"name": "Sofia Santos", "gender": "female", "age": 14},
                {
                    "name": "Miguel Santos",
                    "gender": "male",
                    "age": 10,
                    "birthdate": "2016-01-15",
                    "ids": [
                        {"type": "national_id", "value": "NID-1001"},
                        {"type": "birth_certificate", "value": "BC-1001"},
                    ],
                },
            ],
            "adults": [
                {
                    "name": "Lola Santos",
                    "gender": "female",
                    "age": 68,
                    "birthdate": "1958-01-15",
                    "relation": "parent",
                    "ids": [{"type": "national_id", "value": "NID-1007"}],
                },
            ],
            "district": "Northern District",
            "marital_status": "married",
            "household_size": 5,
        },
        "journey": [
            {"action": "register_household", "days_back": 180},
            {"action": "add_household_members", "days_back": 175},
            {
                "action": "verify_eligibility",
                "program": "Cash Transfer Program",
                "cel_check": "income",
                "days_back": 152,
            },
            {"action": "enroll_program", "program": "Cash Transfer Program", "days_back": 150},
            {"action": "create_event", "event_type": "training", "days_back": 145},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 120},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 90},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 60},
            {"action": "graduate_program", "days_back": 30},
        ],
        "demo_points": [
            "Complete household profile with all members",
            "Program enrollment with full cycle",
            "Payment history showing successful disbursements",
            "Graduation status",
        ],
    },
    {
        "id": "juan_dela_cruz",
        "name": "Dela Cruz",
        "type": "household",
        "story_title": "GRM Resolution",
        "story_description": "Demonstrate grievance handling workflow",
        "profile": {
            "ids": [{"type": "household_id", "value": "HH-200"}],
            "head": {"name": "Juan Dela Cruz", "gender": "male", "age": 38},
            "spouse": {"name": "Ana Dela Cruz", "gender": "female", "age": 35},
            "children": [
                {"name": "Paolo Dela Cruz", "gender": "male", "age": 12},
                {
                    "name": "Maria Dela Cruz",
                    "gender": "female",
                    "age": 8,
                    "birthdate": "2018-01-15",
                    "ids": [{"type": "national_id", "value": "NID-1002"}],
                },
            ],
            "marital_status": "married",
            "household_size": 4,
        },
        "journey": [
            {"action": "register_household", "days_back": 120},
            {"action": "add_household_members", "days_back": 115},
            {"action": "enroll_program", "program": "Cash Transfer Program", "days_back": 100},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 70},
            {"action": "create_payment", "amount": 150, "status": "failed", "days_back": 40},
            {
                "action": "create_grm_ticket",
                "title": "Payment not received",
                "description": "My second payment was not received. Bank shows no deposit.",
                "days_back": 38,
            },
            {"action": "assign_ticket", "days_back": 35},
            {"action": "add_ticket_note", "note": "Investigation: Bank details were incorrect", "days_back": 32},
            {"action": "resolve_ticket", "resolution": "Bank details corrected", "days_back": 30},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 25},
        ],
        "demo_points": [
            "GRM ticket with full conversation history",
            "Resolution workflow",
            "Payment recovery after issue",
        ],
    },
    {
        "id": "rosa_garcia",
        "name": "Rosa Garcia",
        "type": "individual",
        "story_title": "Vulnerable Beneficiary",
        "story_description": "Demonstrate targeting and multi-program enrollment",
        "profile": {
            "gender": "female",
            "age": 72,
            "birthdate": "1954-01-15",
            "ids": [{"type": "national_id", "value": "NID-1008"}],
            "education": "none",
            "marital_status": "widowed",
            "household_size": 1,
            "vulnerability": ["elderly", "low_income", "lives_alone"],
            "vulnerability_score": 75,  # CEL: High vulnerability for elderly pension
            "has_formal_pension": False,  # CEL: Elderly pension eligibility
        },
        "journey": [
            {"action": "register", "days_back": 200},
            {"action": "vulnerability_assessment", "score": "high", "days_back": 195},
            {
                "action": "verify_eligibility",
                "program": "Elderly Social Pension",
                "cel_check": "age_retirement",
                "days_back": 182,
            },
            {"action": "enroll_program", "program": "Elderly Social Pension", "days_back": 180},
            {"action": "enroll_program", "program": "Food Assistance", "days_back": 175},
            {
                "action": "create_payment",
                "amount": 100,
                "status": "paid",
                "program": "Elderly Social Pension",
                "days_back": 150,
            },
            {"action": "create_in_kind", "item": "Food Basket", "days_back": 150},
            {
                "action": "create_payment",
                "amount": 100,
                "status": "paid",
                "program": "Elderly Social Pension",
                "days_back": 120,
            },
            {
                "action": "create_payment",
                "amount": 100,
                "status": "paid",
                "program": "Elderly Social Pension",
                "days_back": 90,
            },
            {
                "action": "create_payment",
                "amount": 100,
                "status": "paid",
                "program": "Elderly Social Pension",
                "days_back": 60,
            },
        ],
        "demo_points": [
            "Multiple program enrollment",
            "Vulnerability indicators",
            "Mixed entitlements (cash + in-kind)",
        ],
    },
    {
        "id": "pedro_reyes",
        "name": "Pedro Reyes",
        "type": "individual",
        "story_title": "Community Leader",
        "story_description": "Demonstrate community engagement and extension visits",
        "profile": {
            "gender": "male",
            "age": 55,
            "birthdate": "1971-01-15",
            "ids": [{"type": "national_id", "value": "NID-1010"}],
            "education": "tertiary",
            "district": "Central District",
            "marital_status": "married",
            "household_size": 6,
            "role": "community_leader",
        },
        "journey": [
            {"action": "register", "days_back": 365},
            {"action": "create_event", "event_type": "extension_visit", "days_back": 250},
            {"action": "create_event", "event_type": "extension_visit", "days_back": 200},
        ],
        "demo_points": [
            "Community leadership role",
            "Extension service history",
        ],
    },
    {
        "id": "ana_mendoza",
        "name": "Ana Mendoza",
        "type": "individual",
        "story_title": "Young Registrant",
        "story_description": "Demonstrate digital registration and verification",
        "profile": {
            "gender": "female",
            "age": 28,
            "birthdate": "1998-01-15",
            "ids": [{"type": "national_id", "value": "NID-1009"}],
            "education": "university",
            "district": "Eastern District",
            "marital_status": "single",
            "household_size": 2,
            "registration_channel": "mobile_app",
            "employment_status": "self_employed",
        },
        "journey": [
            {"action": "register", "channel": "mobile_app", "days_back": 90},
            {"action": "verify_eligibility", "days_back": 75},
        ],
        "demo_points": [
            "Digital registration pathway",
            "Verification workflow",
        ],
    },
    {
        "id": "carlos_elena_morales",
        "name": "Morales",
        "type": "household",
        "story_title": "Household Unit",
        "story_description": "Demonstrate household/group registration",
        "profile": {
            "head": {"name": "Carlos Morales", "gender": "male", "age": 45},
            "spouse": {"name": "Elena Morales", "gender": "female", "age": 42},
            "children": [
                {"name": "Marco Morales", "gender": "male", "age": 16},
                {"name": "Sofia Morales", "gender": "female", "age": 12},
                {"name": "Luis Morales", "gender": "male", "age": 8},
            ],
            "child_count": 3,  # CEL: Child benefit eligibility
            "district": "Southern District",
        },
        "journey": [
            {"action": "register_household", "days_back": 150},
            {"action": "add_household_members", "days_back": 145},
            {
                "action": "verify_eligibility",
                "program": "Universal Child Grant",
                "cel_check": "member_count",
                "days_back": 142,
            },
            {"action": "enroll_program", "program": "Universal Child Grant", "days_back": 140},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 100},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 10},
        ],
        "demo_points": [
            "Household with multiple members",
            "Head of household designation",
            "Child-focused program eligibility",
        ],
    },
    {
        "id": "amina_osman_household",
        "name": "Aquino",
        "type": "household",
        "story_title": "Single-Parent Household",
        "story_description": "Widowed mother with children - vulnerable household",
        "profile": {
            "ids": [{"type": "household_id", "value": "HH-400"}],
            "head": {"name": "Rosario Aquino", "gender": "female", "age": 38},
            "children": [
                {"name": "Daniel Aquino", "gender": "male", "age": 15},
                {"name": "Angela Aquino", "gender": "female", "age": 11},
                {
                    "name": "Rafael Aquino",
                    "gender": "male",
                    "age": 7,
                    "birthdate": "2019-01-15",
                    "ids": [{"type": "national_id", "value": "NID-1004"}],
                },
            ],
            "marital_status": "widowed",
            "vulnerability": ["single_parent", "low_income", "female_headed"],
            "vulnerability_score": 80,  # CEL: High vulnerability - single parent household
            "child_count": 3,  # CEL: Child benefit eligibility
            "district": "Western District",
        },
        "journey": [
            {"action": "register_household", "days_back": 180},
            {"action": "vulnerability_assessment", "score": "high", "days_back": 175},
            {
                "action": "verify_eligibility",
                "program": "Universal Child Grant",
                "cel_check": "member_count",
                "days_back": 162,
            },
            {"action": "enroll_program", "program": "Universal Child Grant", "days_back": 160},
            {"action": "enroll_program", "program": "Food Assistance", "days_back": 155},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 120},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 60},
        ],
        "demo_points": [
            "Female-headed household",
            "Single parent with dependents",
            "Multiple vulnerability indicators",
            "Multi-program enrollment",
        ],
    },
    {
        "id": "jose_reyes_multigenerational",
        "name": "Reyes",
        "type": "household",
        "story_title": "Multi-Generational Household",
        "story_description": "Three generations living together - grandparents, parents, children",
        "profile": {
            "head": {"name": "Jose Reyes Sr", "gender": "male", "age": 72},
            "spouse": {"name": "Carmen Reyes", "gender": "female", "age": 68},
            "adults": [
                {"name": "Miguel Reyes", "gender": "male", "age": 45, "relation": "son"},
                {"name": "Teresa Reyes", "gender": "female", "age": 42, "relation": "daughter-in-law"},
            ],
            "children": [
                {"name": "Jose Reyes Jr", "gender": "male", "age": 18},
                {"name": "Lucia Reyes", "gender": "female", "age": 14},
                {"name": "Antonio Reyes", "gender": "male", "age": 10},
                {"name": "Isabella Reyes", "gender": "female", "age": 6},
            ],
            "child_count": 3,  # CEL: Children under 18 (excluding 18-year-old)
            "district": "Northern District",
            "vulnerability": ["elderly_members"],
        },
        "journey": [
            {"action": "register_household", "days_back": 365},
            {"action": "add_household_members", "days_back": 360},
            {
                "action": "verify_eligibility",
                "program": "Elderly Social Pension",
                "cel_check": "age_retirement",
                "days_back": 352,
            },
            {"action": "enroll_program", "program": "Elderly Social Pension", "days_back": 350},
            {
                "action": "verify_eligibility",
                "program": "Universal Child Grant",
                "cel_check": "member_count",
                "days_back": 342,
            },
            {"action": "enroll_program", "program": "Universal Child Grant", "days_back": 340},
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "program": "Elderly Social Pension",
                "days_back": 300,
            },
            {
                "action": "create_payment",
                "amount": 400,
                "status": "paid",
                "program": "Universal Child Grant",
                "days_back": 290,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "program": "Elderly Social Pension",
                "days_back": 240,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "program": "Elderly Social Pension",
                "days_back": 180,
            },
        ],
        "demo_points": [
            "Multi-generational household (8 members)",
            "Mix of elderly and children",
            "Multiple program eligibility",
            "Complex household composition",
        ],
    },
    {
        "id": "chen_large_family",
        "name": "Bautista",
        "type": "household",
        "story_title": "Large Family",
        "story_description": "Large family with many children - demonstrates scale",
        "profile": {
            "ids": [{"type": "household_id", "value": "HH-500"}],
            "head": {"name": "Eduardo Bautista", "gender": "male", "age": 48},
            "spouse": {"name": "Carmen Bautista", "gender": "female", "age": 44},
            "children": [
                {"name": "Patricia Bautista", "gender": "female", "age": 22},
                {"name": "Fernando Bautista", "gender": "male", "age": 19},
                {"name": "Lucia Bautista", "gender": "female", "age": 16},
                {
                    "name": "Rosalie Bautista",
                    "gender": "female",
                    "age": 13,
                    "birthdate": "2013-01-15",
                    "ids": [{"type": "national_id", "value": "NID-1005"}],
                },
                {"name": "Antonio Bautista", "gender": "male", "age": 9},
            ],
            "child_count": 3,  # CEL: Children under 18 (Lucia, Rosalie, Antonio)
            "district": "Eastern District",
        },
        "journey": [
            {"action": "register_household", "days_back": 200},
            {"action": "add_household_members", "days_back": 195},
            {
                "action": "verify_eligibility",
                "program": "Universal Child Grant",
                "cel_check": "member_count",
                "days_back": 177,
            },
            {"action": "enroll_program", "program": "Universal Child Grant", "days_back": 175},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 140},
            {"action": "create_payment", "amount": 150, "status": "paid", "days_back": 80},
        ],
        "demo_points": [
            "Large family (7 members)",
            "Mixed age children (some eligible, some not)",
            "Cash benefits for children",
        ],
    },
    {
        "id": "manuel_gloria_elderly",
        "name": "Pangilinan",
        "type": "household",
        "story_title": "Elderly Couple",
        "story_description": "Elderly couple without dependents",
        "profile": {
            "head": {"name": "Manuel Pangilinan", "gender": "male", "age": 75},
            "spouse": {"name": "Gloria Pangilinan", "gender": "female", "age": 71},
            "vulnerability": ["elderly", "health_issues", "limited_mobility"],
            "vulnerability_score": 70,  # CEL: Elderly couple vulnerability
            "has_formal_pension": False,  # CEL: Elderly pension eligibility
            "district": "Central District",
        },
        "journey": [
            {"action": "register_household", "days_back": 250},
            {"action": "vulnerability_assessment", "score": "medium", "days_back": 245},
            {
                "action": "verify_eligibility",
                "program": "Elderly Social Pension",
                "cel_check": "age_retirement",
                "days_back": 232,
            },
            {"action": "enroll_program", "program": "Elderly Social Pension", "days_back": 230},
            {"action": "enroll_program", "program": "Food Assistance", "days_back": 220},
            {"action": "create_payment", "amount": 200, "status": "paid", "days_back": 200},
            {"action": "create_in_kind", "item": "Food Basket", "days_back": 195},
            {"action": "create_payment", "amount": 200, "status": "paid", "days_back": 140},
            {"action": "create_payment", "amount": 200, "status": "paid", "days_back": 80},
            {"action": "create_payment", "amount": 200, "status": "paid", "days_back": 20},
        ],
        "demo_points": [
            "Small elderly household",
            "Both spouses receiving benefits",
            "Health-related vulnerability",
            "Regular payment history",
        ],
    },
    {
        "id": "nguyen_extended_family",
        "name": "Navarro",
        "type": "household",
        "story_title": "Extended Family",
        "story_description": "Siblings and their families living together",
        "profile": {
            "head": {"name": "Ricardo Navarro", "gender": "male", "age": 52},
            "adults": [
                {"name": "Lourdes Navarro", "gender": "female", "age": 48, "relation": "spouse"},
                {
                    "name": "Eduardo Navarro",
                    "gender": "male",
                    "age": 46,
                    "relation": "brother",
                    "disability_status": "disabled",
                },
                {"name": "Cristina Navarro", "gender": "female", "age": 44, "relation": "sister-in-law"},
            ],
            "district": "Southern District",
            "vulnerability": ["disability"],
            "vulnerability_score": 65,  # CEL: Disability in household
            "disabled_count": 1,  # CEL: Member with disability
            "notes": "Brother Eduardo has disability requiring care",
        },
        "journey": [
            {"action": "register_household", "days_back": 300},
            {"action": "add_household_members", "days_back": 295},
            {"action": "vulnerability_assessment", "score": "medium", "days_back": 290},
            {"action": "enroll_program", "program": "Cash Transfer Program", "days_back": 280},
            {"action": "create_payment", "amount": 400, "status": "paid", "days_back": 250},
            {"action": "create_payment", "amount": 400, "status": "paid", "days_back": 190},
            {"action": "create_payment", "amount": 400, "status": "paid", "days_back": 130},
            {"action": "create_payment", "amount": 400, "status": "paid", "days_back": 70},
        ],
        "demo_points": [
            "Extended family structure",
            "Multiple adult members",
            "Disability accommodation",
            "Shared resources household",
        ],
    },
    {
        "id": "ibrahim_hassan",
        "name": "Gutierrez",
        "type": "household",
        "story_title": "Displaced Family",
        "story_description": "Demonstrate emergency/vulnerability response",
        "profile": {
            "head": {"name": "Ramon Gutierrez", "gender": "male", "age": 50},
            "spouse": {"name": "Elena Gutierrez", "gender": "female", "age": 45},
            "children": [
                {"name": "Marco Gutierrez", "gender": "male", "age": 18},
                {"name": "Isabella Gutierrez", "gender": "female", "age": 15},
                {"name": "Jose Gutierrez", "gender": "male", "age": 12},
                {"name": "Sofia Gutierrez", "gender": "female", "age": 9},
                {"name": "Miguel Gutierrez", "gender": "male", "age": 5},
            ],
            "marital_status": "married",
            "household_size": 7,
            "status": "internally_displaced",
            "vulnerability": ["displaced", "lost_assets"],
            "vulnerability_score": 85,  # CEL: Emergency relief - high vulnerability
            "displacement_status": "displaced",  # CEL: Emergency eligibility
        },
        "journey": [
            {"action": "register_household", "days_back": 60},
            {"action": "add_household_members", "days_back": 59},
            {"action": "vulnerability_assessment", "score": "very_high", "days_back": 58},
            {
                "action": "verify_eligibility",
                "program": "Emergency Relief Fund",
                "cel_check": "vulnerability_metric",
                "days_back": 56,
            },
            {"action": "enroll_program", "program": "Emergency Relief Fund", "days_back": 55},
            {"action": "create_payment", "amount": 400, "status": "paid", "days_back": 50},
            {"action": "create_payment", "amount": 400, "status": "paid", "days_back": 35},
            {
                "action": "create_grm_ticket",
                "title": "Request for resettlement support",
                "description": "Requesting information about resettlement assistance programs.",
                "ticket_type": "inquiry",
                "days_back": 20,
            },
        ],
        "demo_points": [
            "Emergency registration workflow",
            "High vulnerability scoring",
            "Rapid program enrollment",
            "Ongoing support request",
        ],
    },
    {
        "id": "fatima_al_rahman",
        "name": "Teresa Villanueva",
        "type": "individual",
        "story_title": "Information Seeker",
        "story_description": "Demonstrate GRM for inquiries (not complaints)",
        "profile": {
            "gender": "female",
            "age": 35,
            "education": "secondary",
            "marital_status": "married",
            "household_size": 4,
        },
        "journey": [
            {"action": "register", "days_back": 100},
            {
                "action": "create_grm_ticket",
                "title": "How do I qualify for programs?",
                "description": "I would like information about available programs and eligibility requirements.",
                "ticket_type": "inquiry",
                "days_back": 45,
            },
            {"action": "respond_ticket", "response": "Program information provided", "days_back": 43},
            {"action": "apply_program", "program": "Food Assistance", "days_back": 40},
            {"action": "enroll_program", "program": "Food Assistance", "days_back": 30},
        ],
        "demo_points": [
            "GRM used for information requests",
            "Inquiry leading to program enrollment",
        ],
    },
    {
        "id": "david_sofia_martinez",
        "name": "Martinez",
        "type": "household",
        "story_title": "Disability Support",
        "story_description": "Household with disabled child - demonstrates disability assistance",
        "profile": {
            "ids": [{"type": "household_id", "value": "HH-900"}],
            "head": {"name": "David Martinez", "gender": "male", "age": 48},
            "spouse": {"name": "Sofia Martinez", "gender": "female", "age": 45},
            "children": [
                {
                    "name": "Miguel Martinez",
                    "gender": "male",
                    "age": 12,
                    "birthdate": "2014-01-15",
                    "disability_status": "disabled",
                    "ids": [{"type": "national_id", "value": "NID-1006"}],
                },
            ],
            "disabled_count": 1,  # CEL: Disability Support Grant eligibility
            "child_count": 1,
            "district": "Western District",
        },
        "journey": [
            {"action": "register_household", "days_back": 120},
            {"action": "add_household_members", "days_back": 115},
            {"action": "disability_assessment", "member": "Miguel Martinez", "days_back": 110},
            {
                "action": "verify_eligibility",
                "program": "Disability Support Grant",
                "cel_check": "member_exists_disabled",
                "days_back": 102,
            },
            {"action": "enroll_program", "program": "Disability Support Grant", "days_back": 100},
            {"action": "create_payment", "amount": 175, "status": "paid", "days_back": 90},
            {"action": "create_payment", "amount": 175, "status": "paid", "days_back": 60},
            {"action": "create_payment", "amount": 175, "status": "paid", "days_back": 30},
        ],
        "demo_points": [
            "Household with disabled member",
            "Member existence check in CEL (members.exists)",
            "Disability-focused program eligibility",
            "Per-member benefit calculation",
        ],
    },
]

# Background stories (simpler, for context/volume)
BACKGROUND_STORIES = [
    {
        "id": "cara_okafor_control",
        "name": "Cara Okafor",
        "type": "individual",
        "story_title": "Civil Registry Control",
        "story_description": "Deceased-control record for Registry Notary evidence demos",
        "profile": {
            "gender": "female",
            "age": 69,
            "birthdate": "1957-02-14",
            "civil_status": "deceased_control",
            "ids": [{"type": "national_id", "value": "NID-1003"}],
        },
        "journey": [
            {"action": "register", "days_back": 300},
        ],
    },
    {
        "id": "luis_fernandez",
        "name": "Luis Fernandez",
        "type": "individual",
        "story_title": "Pending Application",
        "story_description": "Shows application pipeline",
        "profile": {"gender": "male", "age": 40},
        "journey": [
            {"action": "register", "days_back": 30},
        ],
    },
    {
        "id": "mary_johnson",
        "name": "Lorna Pascual",
        "type": "individual",
        "story_title": "Rejected Application",
        "story_description": "Shows eligibility rules",
        "profile": {"gender": "female", "age": 55},
        "journey": [
            {"action": "register", "days_back": 60},
            {
                "action": "apply_program",
                "program": "Elderly Social Pension",
                "status": "rejected",
                "reason": "Age requirement not met (55 < 65)",
                "days_back": 55,
            },
        ],
    },
    {
        "id": "ahmed_said",
        "name": "Castillo",
        "type": "household",
        "story_title": "Multiple GRM Tickets",
        "story_description": "Shows GRM history",
        "profile": {
            "head": {"name": "Roberto Castillo", "gender": "male", "age": 45},
            "spouse": {"name": "Linda Castillo", "gender": "female", "age": 40},
            "children": [
                {"name": "Paolo Castillo", "gender": "male", "age": 14},
            ],
            "household_size": 3,
        },
        "journey": [
            {"action": "register_household", "days_back": 200},
            {"action": "add_household_members", "days_back": 195},
            {"action": "enroll_program", "program": "Cash Transfer Program", "days_back": 180},
            {"action": "create_grm_ticket", "title": "Ticket 1", "days_back": 150},
            {"action": "create_grm_ticket", "title": "Ticket 2", "days_back": 100},
            {"action": "create_grm_ticket", "title": "Ticket 3", "days_back": 50},
        ],
    },
    {
        "id": "grace_okonkwo",
        "name": "Maricel Ramos",
        "type": "individual",
        "story_title": "Recently Registered",
        "story_description": "Shows new records",
        "profile": {"gender": "female", "age": 35},
        "journey": [
            {"action": "register", "days_back": 5},
        ],
    },
    {
        "id": "david_kim",
        "name": "Eduardo Tan",
        "type": "individual",
        "story_title": "Long-term Registrant",
        "story_description": "Shows long registration history",
        "profile": {"gender": "male", "age": 48},
        "journey": [
            {"action": "register", "days_back": 300},
        ],
    },
]

# Tutorial families for Get Started > first_program documentation
# These families demonstrate eligibility criteria:
# - Income < 10,000 PHP per month
# - Has at least one child under 5 years old
# Expected: Santos Family and Reyes Family are eligible (2 out of 5)
TUTORIAL_STORIES = [
    {
        "id": "tutorial_garcia_family",
        "name": "Garcia Family",
        "type": "household",
        "story_title": "Tutorial: Not Eligible (High Income)",
        "story_description": "Tutorial household with income above threshold - NOT ELIGIBLE",
        "profile": {
            "head": {"name": "Roberto Garcia", "gender": "male", "age": 42, "income": 15000},
            "spouse": {"name": "Maria Garcia", "gender": "female", "age": 38},
            "children": [
                {"name": "Carlos Garcia", "gender": "male", "age": 12},
            ],
            "child_count": 1,
            "district": "Central District",
        },
        "journey": [
            {"action": "register_household", "days_back": 60},
            {"action": "add_household_members", "days_back": 55},
        ],
        "demo_points": [
            "Tutorial: High income household",
            "Not eligible for Cash Transfer (income 15,000 > 10,000)",
            "No children under 5",
        ],
    },
    {
        "id": "tutorial_santos_family",
        "name": "Tolentino Family",
        "type": "household",
        "story_title": "Tutorial: Eligible (Low Income + Child Under 5)",
        "story_description": "Tutorial household meeting both criteria - ELIGIBLE",
        "profile": {
            "head": {"name": "Jose Tolentino", "gender": "male", "age": 35, "income": 8000},
            "spouse": {"name": "Ana Tolentino", "gender": "female", "age": 32},
            "children": [
                {"name": "Mia Tolentino", "gender": "female", "age": 4},  # Born ~2021, under 5
            ],
            "child_count": 1,
            "district": "Northern District",
        },
        "journey": [
            {"action": "register_household", "days_back": 60},
            {"action": "add_household_members", "days_back": 55},
        ],
        "demo_points": [
            "Tutorial: Low income + child under 5",
            "ELIGIBLE for Cash Transfer (income 8,000 < 10,000 AND has child born 2021)",
        ],
    },
    {
        "id": "tutorial_cruz_family",
        "name": "Salazar Family",
        "type": "household",
        "story_title": "Tutorial: Not Eligible (Income Above Threshold)",
        "story_description": "Tutorial household with income above threshold - NOT ELIGIBLE",
        "profile": {
            "head": {"name": "Pedro Salazar", "gender": "male", "age": 45, "income": 12000},
            "spouse": {"name": "Teresa Salazar", "gender": "female", "age": 42},
            "children": [
                {"name": "Juan Salazar", "gender": "male", "age": 15},
                {"name": "Maria Salazar", "gender": "female", "age": 10},
            ],
            "child_count": 2,
            "district": "Eastern District",
        },
        "journey": [
            {"action": "register_household", "days_back": 60},
            {"action": "add_household_members", "days_back": 55},
        ],
        "demo_points": [
            "Tutorial: Moderate income household",
            "Not eligible for Cash Transfer (income 12,000 > 10,000)",
            "No children under 5",
        ],
    },
    {
        "id": "tutorial_reyes_family",
        "name": "Mercado Family",
        "type": "household",
        "story_title": "Tutorial: Eligible (Low Income + Child Under 5)",
        "story_description": "Tutorial household meeting both criteria - ELIGIBLE",
        "profile": {
            "head": {"name": "Ramon Mercado", "gender": "male", "age": 30, "income": 6000},
            "spouse": {"name": "Elena Mercado", "gender": "female", "age": 28},
            "children": [
                {"name": "Lucia Mercado", "gender": "female", "age": 2},  # Born ~2023, under 5
            ],
            "child_count": 1,
            "district": "Southern District",
        },
        "journey": [
            {"action": "register_household", "days_back": 60},
            {"action": "add_household_members", "days_back": 55},
        ],
        "demo_points": [
            "Tutorial: Low income + youngest child",
            "ELIGIBLE for Cash Transfer (income 6,000 < 10,000 AND has child born 2023)",
        ],
    },
    {
        "id": "tutorial_ramos_family",
        "name": "Ramos Family",
        "type": "household",
        "story_title": "Tutorial: Not Eligible (High Income)",
        "story_description": "Tutorial household with highest income - NOT ELIGIBLE",
        "profile": {
            "head": {"name": "Antonio Ramos", "gender": "male", "age": 48, "income": 18000},
            "spouse": {"name": "Rosa Ramos", "gender": "female", "age": 45},
            "children": [
                {"name": "Diego Ramos", "gender": "male", "age": 18},
                {"name": "Carla Ramos", "gender": "female", "age": 14},
            ],
            "child_count": 2,
            "district": "Western District",
        },
        "journey": [
            {"action": "register_household", "days_back": 60},
            {"action": "add_household_members", "days_back": 55},
        ],
        "demo_points": [
            "Tutorial: High income household",
            "Not eligible for Cash Transfer (income 18,000 > 10,000)",
            "No children under 5",
        ],
    },
]


# ---------------------------------------------------------------------------
# Locale-specific name overrides
# ---------------------------------------------------------------------------
# Each locale maps story_id → {"name": ..., "profile_names": {...}}
# profile_names keys: "head", "spouse", "children" (list), "adults" (list)
# fil_PH is the default — names are already in the story dicts above.

LOCALE_NAMES = {
    "fil_PH": {},  # Default locale — no overrides needed
    # -----------------------------------------------------------------------
    # Sri Lanka — Sinhalese names
    # -----------------------------------------------------------------------
    "si_LK": {
        # DEMO_STORIES
        "maria_santos": {
            "name": "Perera",
            "profile_names": {
                "head": "Kumari Perera",
                "spouse": "Sunil Perera",
                "children": ["Nimali Perera", "Kasun Perera"],
                "adults": ["Padma Perera"],
            },
        },
        "juan_dela_cruz": {
            "name": "Bandara",
            "profile_names": {
                "head": "Nimal Bandara",
                "spouse": "Kamani Bandara",
                "children": ["Lahiru Bandara", "Sanduni Bandara"],
            },
        },
        "rosa_garcia": {"name": "Malini Silva"},
        "pedro_reyes": {"name": "Saman Jayawardena"},
        "ana_mendoza": {"name": "Sachini Dissanayake"},
        "cara_okafor_control": {"name": "Chandra Perera"},
        "carlos_elena_morales": {
            "name": "Fernando",
            "profile_names": {
                "head": "Kasun Fernando",
                "spouse": "Dilani Fernando",
                "children": ["Nuwan Fernando", "Nethmi Fernando", "Chamara Fernando"],
            },
        },
        "amina_osman_household": {
            "name": "Herath",
            "profile_names": {
                "head": "Anoma Herath",
                "children": ["Lahiru Herath", "Hiruni Herath", "Dinesh Herath"],
            },
        },
        "jose_reyes_multigenerational": {
            "name": "Rathnayake",
            "profile_names": {
                "head": "Kamal Rathnayake",
                "spouse": "Ramya Rathnayake",
                "adults": ["Ajith Rathnayake", "Sanduni Rathnayake"],
                "children": [
                    "Pradeep Rathnayake",
                    "Wasana Rathnayake",
                    "Ruwan Rathnayake",
                    "Nimali Rathnayake",
                ],
            },
        },
        "chen_large_family": {
            "name": "Gunasekara",
            "profile_names": {
                "head": "Thilak Gunasekara",
                "spouse": "Kusum Gunasekara",
                "children": [
                    "Gayani Gunasekara",
                    "Ashan Gunasekara",
                    "Chathurika Gunasekara",
                    "Ruwanthi Gunasekara",
                    "Mahesh Gunasekara",
                ],
            },
        },
        "manuel_gloria_elderly": {
            "name": "Wijesinghe",
            "profile_names": {
                "head": "Sunil Wijesinghe",
                "spouse": "Sirima Wijesinghe",
            },
        },
        "nguyen_extended_family": {
            "name": "Amarasinghe",
            "profile_names": {
                "head": "Ranjith Amarasinghe",
                "adults": [
                    "Champa Amarasinghe",
                    "Chandana Amarasinghe",
                    "Nadeesha Amarasinghe",
                ],
            },
        },
        "ibrahim_hassan": {
            "name": "Kumara",
            "profile_names": {
                "head": "Asanka Kumara",
                "spouse": "Chamari Kumara",
                "children": [
                    "Dinesh Kumara",
                    "Nishadi Kumara",
                    "Tharindu Kumara",
                    "Dilhani Kumara",
                    "Ravindu Kumara",
                ],
            },
        },
        "fatima_al_rahman": {"name": "Ishara Senanayake"},
        "david_sofia_martinez": {
            "name": "Wickramasinghe",
            "profile_names": {
                "head": "Sanjeewa Wickramasinghe",
                "spouse": "Nisansala Wickramasinghe",
                "children": ["Charitha Wickramasinghe"],
            },
        },
        # BACKGROUND_STORIES
        "luis_fernandez": {"name": "Dinesh Rajapaksa"},
        "mary_johnson": {"name": "Priyanka Mendis"},
        "ahmed_said": {
            "name": "Weerasinghe",
            "profile_names": {
                "head": "Ruwan Weerasinghe",
                "spouse": "Nilmini Weerasinghe",
                "children": ["Sampath Weerasinghe"],
            },
        },
        "grace_okonkwo": {"name": "Sanduni Karunaratne"},
        "david_kim": {"name": "Mahesh Gamage"},
        # TUTORIAL_STORIES
        "tutorial_garcia_family": {
            "name": "Pathirana Family",
            "profile_names": {
                "head": "Chaminda Pathirana",
                "spouse": "Mala Pathirana",
                "children": ["Kavinda Pathirana"],
            },
        },
        "tutorial_santos_family": {
            "name": "De Silva Family",
            "profile_names": {
                "head": "Rohan De Silva",
                "spouse": "Dilini De Silva",
                "children": ["Senuri De Silva"],
            },
        },
        "tutorial_cruz_family": {
            "name": "Cooray Family",
            "profile_names": {
                "head": "Upul Cooray",
                "spouse": "Manel Cooray",
                "children": ["Tharindu Cooray", "Rashmi Cooray"],
            },
        },
        "tutorial_reyes_family": {
            "name": "Gunawardena Family",
            "profile_names": {
                "head": "Sampath Gunawardena",
                "spouse": "Harshani Gunawardena",
                "children": ["Kaveesha Gunawardena"],
            },
        },
        "tutorial_ramos_family": {
            "name": "Senaratne Family",
            "profile_names": {
                "head": "Jagath Senaratne",
                "spouse": "Priyadarshani Senaratne",
                "children": ["Lakshan Senaratne", "Imalsha Senaratne"],
            },
        },
    },
    # -----------------------------------------------------------------------
    # Togo — Ewe / French names
    # -----------------------------------------------------------------------
    "fr_TG": {
        # DEMO_STORIES
        "maria_santos": {
            "name": "Koffi",
            "profile_names": {
                "head": "Ama Koffi",
                "spouse": "Kokou Koffi",
                "children": ["Esi Koffi", "Kweku Koffi"],
                "adults": ["Adjo Koffi"],
            },
        },
        "juan_dela_cruz": {
            "name": "Mensah",
            "profile_names": {
                "head": "Kofi Mensah",
                "spouse": "Akosua Mensah",
                "children": ["Yao Mensah", "Ama Mensah"],
            },
        },
        "rosa_garcia": {"name": "Adzo Amegah"},
        "pedro_reyes": {"name": "Yao Dossou"},
        "ana_mendoza": {"name": "Akua Ayivi"},
        "cara_okafor_control": {"name": "Ama Okafor"},
        "carlos_elena_morales": {
            "name": "Agbeko",
            "profile_names": {
                "head": "Kodjo Agbeko",
                "spouse": "Esi Agbeko",
                "children": ["Komla Agbeko", "Ablavi Agbeko", "Koku Agbeko"],
            },
        },
        "amina_osman_household": {
            "name": "Tetteh",
            "profile_names": {
                "head": "Adjoa Tetteh",
                "children": ["Messan Tetteh", "Akossiwa Tetteh", "Edem Tetteh"],
            },
        },
        "jose_reyes_multigenerational": {
            "name": "Lawson",
            "profile_names": {
                "head": "Kwame Lawson",
                "spouse": "Afia Lawson",
                "adults": ["Kossi Lawson", "Ayoko Lawson"],
                "children": [
                    "Dela Lawson",
                    "Dzidzor Lawson",
                    "Kokou Lawson",
                    "Ewoenam Lawson",
                ],
            },
        },
        "chen_large_family": {
            "name": "Akakpo",
            "profile_names": {
                "head": "Mawuli Akakpo",
                "spouse": "Kafui Akakpo",
                "children": [
                    "Dede Akakpo",
                    "Yaovi Akakpo",
                    "Yawa Akakpo",
                    "Abla Akakpo",
                    "Komi Akakpo",
                ],
            },
        },
        "manuel_gloria_elderly": {
            "name": "Amouzou",
            "profile_names": {
                "head": "Atsu Amouzou",
                "spouse": "Akpene Amouzou",
            },
        },
        "nguyen_extended_family": {
            "name": "Gbeho",
            "profile_names": {
                "head": "Selom Gbeho",
                "adults": ["Mawusi Gbeho", "Senyo Gbeho", "Ayele Gbeho"],
            },
        },
        "ibrahim_hassan": {
            "name": "Deku",
            "profile_names": {
                "head": "Kosi Deku",
                "spouse": "Akua Deku",
                "children": [
                    "Komla Deku",
                    "Ablavi Deku",
                    "Kofi Deku",
                    "Ama Deku",
                    "Edem Deku",
                ],
            },
        },
        "fatima_al_rahman": {"name": "Afia Sossou"},
        "david_sofia_martinez": {
            "name": "Koudawo",
            "profile_names": {
                "head": "Ata Koudawo",
                "spouse": "Ama Koudawo",
                "children": ["Kofi Koudawo"],
            },
        },
        # BACKGROUND_STORIES
        "luis_fernandez": {"name": "Messan Ameganvi"},
        "mary_johnson": {"name": "Ablavi Gbeassor"},
        "ahmed_said": {
            "name": "Agbodjan",
            "profile_names": {
                "head": "Komla Agbodjan",
                "spouse": "Adjoa Agbodjan",
                "children": ["Messan Agbodjan"],
            },
        },
        "grace_okonkwo": {"name": "Akossiwa Adjakly"},
        "david_kim": {"name": "Yaovi Assignon"},
        # TUTORIAL_STORIES
        "tutorial_garcia_family": {
            "name": "Famille Agbo",
            "profile_names": {
                "head": "Komi Agbo",
                "spouse": "Dede Agbo",
                "children": ["Edem Agbo"],
            },
        },
        "tutorial_santos_family": {
            "name": "Famille Sodji",
            "profile_names": {
                "head": "Kodjo Sodji",
                "spouse": "Esi Sodji",
                "children": ["Ewoenam Sodji"],
            },
        },
        "tutorial_cruz_family": {
            "name": "Famille Nyaku",
            "profile_names": {
                "head": "Kwame Nyaku",
                "spouse": "Adjoa Nyaku",
                "children": ["Yao Nyaku", "Dzidzor Nyaku"],
            },
        },
        "tutorial_reyes_family": {
            "name": "Famille Bamezon",
            "profile_names": {
                "head": "Kossi Bamezon",
                "spouse": "Ayoko Bamezon",
                "children": ["Kafui Bamezon"],
            },
        },
        "tutorial_ramos_family": {
            "name": "Famille Djossou",
            "profile_names": {
                "head": "Mawuli Djossou",
                "spouse": "Abla Djossou",
                "children": ["Dela Djossou", "Yawa Djossou"],
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Localization helpers
# ---------------------------------------------------------------------------


def _apply_locale_to_story(story, locale_entry):
    """Apply locale name overrides to a deep-copied story dict."""
    story["name"] = locale_entry["name"]
    profile = story.get("profile", {})
    pnames = locale_entry.get("profile_names", {})

    # Head of household
    if "head" in pnames and "head" in profile:
        profile["head"]["name"] = pnames["head"]

    # Spouse
    if "spouse" in pnames and "spouse" in profile:
        profile["spouse"]["name"] = pnames["spouse"]

    # Children (positional replacement)
    if "children" in pnames and "children" in profile:
        for idx, child_name in enumerate(pnames["children"]):
            if idx < len(profile["children"]):
                profile["children"][idx]["name"] = child_name

    # Adults (positional replacement)
    if "adults" in pnames and "adults" in profile:
        for idx, adult_name in enumerate(pnames["adults"]):
            if idx < len(profile["adults"]):
                profile["adults"][idx]["name"] = adult_name

    # Also update journey references that mention member names
    # (e.g., disability_assessment member field)
    if "children" in pnames:
        for step in story.get("journey", []):
            if "member" in step:
                # Find matching child by position
                orig_children = get_story_by_id(story["id"])
                if orig_children:
                    orig_profile = orig_children.get("profile", {})
                    for idx, child in enumerate(orig_profile.get("children", [])):
                        if child.get("name") == step["member"] and idx < len(pnames["children"]):
                            step["member"] = pnames["children"][idx]
                            break

    return story


def get_localized_stories(locale=None):
    """Return all stories with names replaced for the given locale.

    If locale is None or "fil_PH", returns the original stories unchanged.
    Otherwise, deep-copies all stories and applies LOCALE_NAMES overrides.
    Stories without locale overrides keep their original names.
    """
    all_stories = DEMO_STORIES + BACKGROUND_STORIES + TUTORIAL_STORIES
    if not locale or locale == "fil_PH" or locale not in LOCALE_NAMES:
        return all_stories

    locale_map = LOCALE_NAMES[locale]
    result = []
    for story in all_stories:
        if story["id"] in locale_map:
            localized = copy.deepcopy(story)
            _apply_locale_to_story(localized, locale_map[story["id"]])
            result.append(localized)
        else:
            result.append(story)
    return result


def get_localized_reserved_names(locale=None):
    """Return the RESERVED_NAMES list for the given locale.

    Collects all character names from localized stories.
    """
    if not locale or locale == "fil_PH" or locale not in LOCALE_NAMES:
        return RESERVED_NAMES

    stories = get_localized_stories(locale)
    names = []
    for story in stories:
        names.append(story["name"])
        profile = story.get("profile", {})
        if "head" in profile:
            names.append(profile["head"]["name"])
        if "spouse" in profile:
            names.append(profile["spouse"]["name"])
        for child in profile.get("children", []):
            names.append(child["name"])
        for adult in profile.get("adults", []):
            names.append(adult["name"])
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for n in names:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    return unique


def get_localized_name(story_id, locale=None):
    """Get the localized primary name for a single story."""
    if locale and locale != "fil_PH" and locale in LOCALE_NAMES:
        locale_map = LOCALE_NAMES[locale]
        if story_id in locale_map:
            return locale_map[story_id]["name"]
    # Fallback to original
    story = get_story_by_id(story_id)
    return story["name"] if story else None


def get_all_stories():
    """Return all demo stories (main + background + tutorial)."""
    return DEMO_STORIES + BACKGROUND_STORIES + TUTORIAL_STORIES


def get_main_stories():
    """Return only the main demo stories."""
    return DEMO_STORIES


def get_background_stories():
    """Return only the background stories."""
    return BACKGROUND_STORIES


def get_tutorial_stories():
    """Return only the tutorial stories for Get Started > first_program."""
    return TUTORIAL_STORIES


def get_story_by_id(story_id):
    """Get a specific story by ID."""
    for story in get_all_stories():
        if story["id"] == story_id:
            return story
    return None


def get_story_by_name(name):
    """Get a specific story by name."""
    for story in get_all_stories():
        if story["name"] == name:
            return story
    return None
