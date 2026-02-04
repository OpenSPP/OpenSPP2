# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Fixed Demo Stories for OpenSPP Demo Generator V2

These stories provide predictable, documented personas for:
- Sales demos ("Search for Maria Santos...")
- Partner onboarding/training
- CI/Testing verification

Each story demonstrates a specific workflow or feature set.
"""

# Reserved names that should not be used for random volume generation
RESERVED_NAMES = [
    "Maria Santos",
    "Juan Dela Cruz",
    "Rosa Garcia",
    "Pedro Reyes",
    "Ana Mendoza",
    "Carlos Morales",
    "Elena Morales",
    "Ibrahim Hassan",
    "Fatima Al-Rahman",
    "Luis Fernandez",
    "Mary Johnson",
    "Ahmed Said",
    "Grace Okonkwo",
    "David Kim",
    # Additional household members
    "Marco Morales",
    "Sofia Morales",
    "Luis Morales",
    # New household stories
    "Amina Osman",
    "Yusuf Osman",
    "Layla Osman",
    "Hassan Osman",
    "Jose Reyes Sr",
    "Carmen Reyes",
    "Miguel Reyes",
    "Teresa Reyes",
    "Jose Reyes Jr",
    "Lucia Reyes",
    "Antonio Reyes",
    "Isabella Reyes",
    "Chen Wei",
    "Chen Mei",
    "Chen Ling",
    "Chen Jun",
    "Chen Xiao",
    "Chen Yan",
    "Chen Bo",
    "Manuel Santos",
    "Gloria Santos",
    "James Nguyen",
    "Linda Nguyen",
    "Michael Nguyen",
    "Sarah Nguyen",
    # Story 9 - Martinez household
    "David Martinez",
    "Sofia Martinez",
    "Miguel Martinez",
    # Tutorial families (Get Started > first_program)
    "Garcia Family",
    "Roberto Garcia",
    "Maria Garcia",
    "Carlos Garcia",
    "Santos Family",
    "Jose Santos",
    "Ana Santos",
    "Mia Santos",
    "Cruz Family",
    "Pedro Cruz",
    "Teresa Cruz",
    "Juan Cruz",
    "Maria Cruz",
    "Reyes Family",
    "Ramon Reyes",
    "Elena Reyes",
    "Lucia Reyes",
    "Ramos Family",
    "Antonio Ramos",
    "Rosa Ramos",
    "Diego Ramos",
    "Carla Ramos",
]

DEMO_STORIES = [
    {
        "id": "maria_santos",
        "name": "Maria Santos",
        "type": "farmer",
        "story_title": "The Success Story",
        "story_description": "Happy path from registration to graduation",
        "profile": {
            "gender": "female",
            "age": 42,
            "education": "primary",
            "farm_size": 2.5,
            "farm_size_hectares": 2.5,  # CEL: Input Subsidy eligibility
            "farm_type": "crop",
            "main_crop": "rice",
            "district": "Northern District",
            "marital_status": "married",
            "household_size": 5,
        },
        "journey": [
            {"action": "register", "days_back": 180},
            {"action": "add_farm_details", "days_back": 175},
            {
                "action": "verify_eligibility",
                "program": "Input Subsidy Program",
                "cel_check": "farm_size",
                "days_back": 152,
            },
            {
                "action": "enroll_program",
                "program": "Input Subsidy Program",
                "days_back": 150,
            },
            {"action": "create_event", "event_type": "training", "days_back": 145},
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "days_back": 120,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "days_back": 90,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "days_back": 60,
            },
            {"action": "graduate_program", "days_back": 30},
        ],
        "demo_points": [
            "Complete farmer profile with all details filled",
            "Program enrollment with full cycle",
            "Payment history showing successful disbursements",
            "Graduation status",
        ],
    },
    {
        "id": "juan_dela_cruz",
        "name": "Juan Dela Cruz",
        "type": "farmer",
        "story_title": "GRM Resolution",
        "story_description": "Demonstrate grievance handling workflow",
        "profile": {
            "gender": "male",
            "age": 38,
            "education": "secondary",
            "farm_size": 1.0,
            "farm_size_hectares": 1.0,  # CEL: Farm size for eligibility
            "farm_type": "mixed",
            "main_crop": "vegetables",
            "marital_status": "married",
            "household_size": 4,
        },
        "journey": [
            {"action": "register", "days_back": 120},
            {
                "action": "enroll_program",
                "program": "Cash Transfer Program",
                "days_back": 100,
            },
            {
                "action": "create_payment",
                "amount": 150,
                "status": "paid",
                "days_back": 70,
            },
            {
                "action": "create_payment",
                "amount": 150,
                "status": "failed",
                "days_back": 40,
            },
            {
                "action": "create_grm_ticket",
                "title": "Payment not received",
                "description": "My second payment was not received. Bank shows no deposit.",
                "days_back": 38,
            },
            {"action": "assign_ticket", "days_back": 35},
            {
                "action": "add_ticket_note",
                "note": "Investigation: Bank details were incorrect",
                "days_back": 32,
            },
            {
                "action": "resolve_ticket",
                "resolution": "Bank details corrected",
                "days_back": 30,
            },
            {
                "action": "create_payment",
                "amount": 150,
                "status": "paid",
                "days_back": 25,
            },
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
            "age": 67,
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
                "program": "Elderly Pension",
                "cel_check": "age_retirement",
                "days_back": 182,
            },
            {
                "action": "enroll_program",
                "program": "Elderly Pension",
                "days_back": 180,
            },
            {
                "action": "enroll_program",
                "program": "Food Assistance",
                "days_back": 175,
            },
            {
                "action": "create_payment",
                "amount": 100,
                "status": "paid",
                "program": "Elderly Pension",
                "days_back": 150,
            },
            {"action": "create_in_kind", "item": "Food Basket", "days_back": 150},
            {
                "action": "create_payment",
                "amount": 100,
                "status": "paid",
                "program": "Elderly Pension",
                "days_back": 120,
            },
            {
                "action": "create_payment",
                "amount": 100,
                "status": "paid",
                "program": "Elderly Pension",
                "days_back": 90,
            },
            {
                "action": "create_payment",
                "amount": 100,
                "status": "paid",
                "program": "Elderly Pension",
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
        "type": "farmer",
        "story_title": "Cooperative Leader",
        "story_description": "Demonstrate farmer registry depth and group features",
        "profile": {
            "gender": "male",
            "age": 55,
            "education": "tertiary",
            "farm_size": 8.0,
            "farm_size_hectares": 8.0,  # CEL: Large livestock farm
            "farm_type": "livestock",
            "main_livestock": "dairy",
            "district": "Central District",
            "marital_status": "married",
            "household_size": 6,
            "role": "cooperative_chairman",
        },
        "journey": [
            {"action": "register", "days_back": 365},
            {"action": "add_farm_details", "comprehensive": True, "days_back": 360},
            {"action": "register_cooperative_leader", "days_back": 350},
            {
                "action": "enroll_program",
                "program": "Livestock Improvement Program",
                "days_back": 300,
            },
            {
                "action": "create_event",
                "event_type": "extension_visit",
                "days_back": 250,
            },
            {
                "action": "create_event",
                "event_type": "extension_visit",
                "days_back": 200,
            },
            {
                "action": "create_in_kind",
                "item": "Improved Breed Cattle",
                "quantity": 2,
                "days_back": 150,
            },
        ],
        "demo_points": [
            "Detailed farm profile (livestock, assets, land records)",
            "Group/cooperative membership",
            "Extension service history",
            "In-kind entitlement",
        ],
    },
    {
        "id": "ana_mendoza",
        "name": "Ana Mendoza",
        "type": "farmer",
        "story_title": "Young Modern Farmer",
        "story_description": "Demonstrate tech-savvy farmer profile",
        "profile": {
            "gender": "female",
            "age": 28,
            "education": "university",
            "farm_size": 3.0,
            "farm_size_hectares": 3.0,  # CEL: Youth farmer eligibility
            "farm_type": "crop",
            "main_crop": "mixed_vegetables",
            "district": "Eastern District",
            "marital_status": "single",
            "household_size": 2,
            "registration_channel": "mobile_app",
            "employment_status": "self_employed",  # CEL: Youth employment status
        },
        "journey": [
            {"action": "register", "channel": "mobile_app", "days_back": 90},
            {"action": "add_farm_details", "with_gps": True, "days_back": 85},
            {
                "action": "apply_program",
                "program": "Input Subsidy Program",
                "days_back": 80,
            },
            {"action": "verify_eligibility", "days_back": 75},
            {
                "action": "enroll_program",
                "program": "Input Subsidy Program",
                "days_back": 70,
            },
            {"action": "create_in_kind", "item": "Inputs Package", "days_back": 45},
        ],
        "demo_points": [
            "Modern farmer profile",
            "GPS coordinates on farm",
            "Digital registration pathway",
        ],
    },
    {
        "id": "carlos_elena_morales",
        "name": "Carlos Morales",
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
            "farm_size": 2.0,
            "farm_size_hectares": 2.0,  # CEL: Household farm size
            "child_count": 3,  # CEL: Child benefit eligibility
            "district": "Southern District",
        },
        "journey": [
            {"action": "register_household", "days_back": 150},
            {"action": "add_household_members", "days_back": 145},
            {
                "action": "verify_eligibility",
                "program": "Child Support Grant",
                "cel_check": "member_count",
                "days_back": 142,
            },
            {
                "action": "enroll_program",
                "program": "Child Support Grant",
                "days_back": 140,
            },
            {
                "action": "create_payment",
                "amount": 300,
                "status": "paid",
                "days_back": 100,
            },
            {
                "action": "create_payment",
                "amount": 300,
                "status": "paid",
                "days_back": 10,
            },
        ],
        "demo_points": [
            "Household with multiple members",
            "Head of household designation",
            "Child-focused program eligibility",
        ],
    },
    {
        "id": "amina_osman_household",
        "name": "Amina Osman",
        "type": "household",
        "story_title": "Single-Parent Household",
        "story_description": "Widowed mother with children - vulnerable household",
        "profile": {
            "head": {"name": "Amina Osman", "gender": "female", "age": 38},
            "children": [
                {"name": "Yusuf Osman", "gender": "male", "age": 15},
                {"name": "Layla Osman", "gender": "female", "age": 11},
                {"name": "Hassan Osman", "gender": "male", "age": 7},
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
                "program": "Child Support Grant",
                "cel_check": "member_count",
                "days_back": 162,
            },
            {
                "action": "enroll_program",
                "program": "Child Support Grant",
                "days_back": 160,
            },
            {
                "action": "enroll_program",
                "program": "Food Assistance",
                "days_back": 155,
            },
            {
                "action": "create_payment",
                "amount": 350,
                "status": "paid",
                "days_back": 120,
            },
            {
                "action": "create_payment",
                "amount": 350,
                "status": "paid",
                "days_back": 60,
            },
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
        "name": "Jose Reyes Sr",
        "type": "household",
        "story_title": "Multi-Generational Household",
        "story_description": "Three generations living together - grandparents, parents, children",
        "profile": {
            "head": {"name": "Jose Reyes Sr", "gender": "male", "age": 72},
            "spouse": {"name": "Carmen Reyes", "gender": "female", "age": 68},
            "adults": [
                {
                    "name": "Miguel Reyes",
                    "gender": "male",
                    "age": 45,
                    "relation": "son",
                },
                {
                    "name": "Teresa Reyes",
                    "gender": "female",
                    "age": 42,
                    "relation": "daughter-in-law",
                },
            ],
            "children": [
                {"name": "Jose Reyes Jr", "gender": "male", "age": 18},
                {"name": "Lucia Reyes", "gender": "female", "age": 14},
                {"name": "Antonio Reyes", "gender": "male", "age": 10},
                {"name": "Isabella Reyes", "gender": "female", "age": 6},
            ],
            "farm_size": 5.0,
            "farm_size_hectares": 5.0,  # CEL: Multi-generational household farm
            "child_count": 3,  # CEL: Children under 18 (excluding 18-year-old)
            "district": "Northern District",
            "vulnerability": ["elderly_members"],
        },
        "journey": [
            {"action": "register_household", "days_back": 365},
            {"action": "add_household_members", "days_back": 360},
            {
                "action": "verify_eligibility",
                "program": "Elderly Pension",
                "cel_check": "age_retirement",
                "days_back": 352,
            },
            {
                "action": "enroll_program",
                "program": "Elderly Pension",
                "days_back": 350,
            },
            {
                "action": "verify_eligibility",
                "program": "Child Support Grant",
                "cel_check": "member_count",
                "days_back": 342,
            },
            {
                "action": "enroll_program",
                "program": "Child Support Grant",
                "days_back": 340,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "program": "Elderly Pension",
                "days_back": 300,
            },
            {
                "action": "create_payment",
                "amount": 400,
                "status": "paid",
                "program": "Child Support Grant",
                "days_back": 290,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "program": "Elderly Pension",
                "days_back": 240,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "program": "Elderly Pension",
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
        "name": "Chen Wei",
        "type": "household",
        "story_title": "Large Family",
        "story_description": "Large family with many children - demonstrates scale",
        "profile": {
            "head": {"name": "Chen Wei", "gender": "male", "age": 48},
            "spouse": {"name": "Chen Mei", "gender": "female", "age": 44},
            "children": [
                {"name": "Chen Ling", "gender": "female", "age": 22},
                {"name": "Chen Jun", "gender": "male", "age": 19},
                {"name": "Chen Xiao", "gender": "female", "age": 16},
                {"name": "Chen Yan", "gender": "female", "age": 13},
                {"name": "Chen Bo", "gender": "male", "age": 9},
            ],
            "farm_size": 4.5,
            "farm_size_hectares": 4.5,  # CEL: Large family farm
            "child_count": 3,  # CEL: Children under 18 (Xiao, Yan, Bo)
            "farm_type": "crop",
            "main_crop": "rice",
            "district": "Eastern District",
        },
        "journey": [
            {"action": "register_household", "days_back": 200},
            {"action": "add_household_members", "days_back": 195},
            {"action": "add_farm_details", "days_back": 190},
            {
                "action": "verify_eligibility",
                "program": "Input Subsidy Program",
                "cel_check": "farm_size",
                "days_back": 182,
            },
            {
                "action": "enroll_program",
                "program": "Input Subsidy Program",
                "days_back": 180,
            },
            {
                "action": "verify_eligibility",
                "program": "Child Support Grant",
                "cel_check": "member_count",
                "days_back": 177,
            },
            {
                "action": "enroll_program",
                "program": "Child Support Grant",
                "days_back": 175,
            },
            {"action": "create_in_kind", "item": "Inputs Package", "days_back": 150},
            {
                "action": "create_payment",
                "amount": 450,
                "status": "paid",
                "days_back": 140,
            },
            {
                "action": "create_payment",
                "amount": 450,
                "status": "paid",
                "days_back": 80,
            },
        ],
        "demo_points": [
            "Large family (7 members)",
            "Mixed age children (some eligible, some not)",
            "Farming household",
            "Both in-kind and cash benefits",
        ],
    },
    {
        "id": "manuel_gloria_elderly",
        "name": "Manuel Santos",
        "type": "household",
        "story_title": "Elderly Couple",
        "story_description": "Elderly couple without dependents",
        "profile": {
            "head": {"name": "Manuel Santos", "gender": "male", "age": 75},
            "spouse": {"name": "Gloria Santos", "gender": "female", "age": 71},
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
                "program": "Elderly Pension",
                "cel_check": "age_retirement",
                "days_back": 232,
            },
            {
                "action": "enroll_program",
                "program": "Elderly Pension",
                "days_back": 230,
            },
            {
                "action": "enroll_program",
                "program": "Food Assistance",
                "days_back": 220,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "days_back": 200,
            },
            {"action": "create_in_kind", "item": "Food Basket", "days_back": 195},
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "days_back": 140,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "days_back": 80,
            },
            {
                "action": "create_payment",
                "amount": 200,
                "status": "paid",
                "days_back": 20,
            },
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
        "name": "James Nguyen",
        "type": "household",
        "story_title": "Extended Family",
        "story_description": "Siblings and their families living together",
        "profile": {
            "head": {"name": "James Nguyen", "gender": "male", "age": 52},
            "adults": [
                {
                    "name": "Linda Nguyen",
                    "gender": "female",
                    "age": 48,
                    "relation": "spouse",
                },
                {
                    "name": "Michael Nguyen",
                    "gender": "male",
                    "age": 46,
                    "relation": "brother",
                    "disability_status": "disabled",
                },
                {
                    "name": "Sarah Nguyen",
                    "gender": "female",
                    "age": 44,
                    "relation": "sister-in-law",
                },
            ],
            "farm_size": 6.0,
            "farm_size_hectares": 6.0,  # CEL: Extended family farm
            "farm_type": "mixed",
            "district": "Southern District",
            "vulnerability": ["disability"],
            "vulnerability_score": 65,  # CEL: Disability in household
            "disabled_count": 1,  # CEL: Member with disability
            "notes": "Brother Michael has disability requiring care",
        },
        "journey": [
            {"action": "register_household", "days_back": 300},
            {"action": "add_household_members", "days_back": 295},
            {"action": "vulnerability_assessment", "score": "medium", "days_back": 290},
            {
                "action": "enroll_program",
                "program": "Cash Transfer Program",
                "days_back": 280,
            },
            {
                "action": "create_payment",
                "amount": 400,
                "status": "paid",
                "days_back": 250,
            },
            {
                "action": "create_payment",
                "amount": 400,
                "status": "paid",
                "days_back": 190,
            },
            {
                "action": "create_payment",
                "amount": 400,
                "status": "paid",
                "days_back": 130,
            },
            {
                "action": "create_payment",
                "amount": 400,
                "status": "paid",
                "days_back": 70,
            },
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
        "name": "Ibrahim Hassan",
        "type": "individual",
        "story_title": "Displaced Farmer",
        "story_description": "Demonstrate emergency/vulnerability response",
        "profile": {
            "gender": "male",
            "age": 50,
            "education": "primary",
            "marital_status": "married",
            "household_size": 7,
            "status": "internally_displaced",
            "previous_farm_size": 5.0,
            "vulnerability": ["displaced", "lost_assets"],
            "vulnerability_score": 85,  # CEL: Emergency relief - high vulnerability
            "displacement_status": "displaced",  # CEL: Emergency eligibility
        },
        "journey": [
            {"action": "emergency_register", "days_back": 60},
            {
                "action": "vulnerability_assessment",
                "score": "very_high",
                "days_back": 58,
            },
            {
                "action": "verify_eligibility",
                "program": "Emergency Cash Transfer",
                "cel_check": "vulnerability_metric",
                "days_back": 56,
            },
            {
                "action": "enroll_program",
                "program": "Emergency Cash Transfer",
                "days_back": 55,
            },
            {
                "action": "create_payment",
                "amount": 500,
                "status": "paid",
                "days_back": 50,
            },
            {
                "action": "create_payment",
                "amount": 500,
                "status": "paid",
                "days_back": 35,
            },
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
        "name": "Fatima Al-Rahman",
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
            {
                "action": "respond_ticket",
                "response": "Program information provided",
                "days_back": 43,
            },
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
        "name": "David Martinez",
        "type": "household",
        "story_title": "Disability Support",
        "story_description": "Household with disabled child - demonstrates disability assistance",
        "profile": {
            "head": {"name": "David Martinez", "gender": "male", "age": 48},
            "spouse": {"name": "Sofia Martinez", "gender": "female", "age": 45},
            "children": [
                {
                    "name": "Miguel Martinez",
                    "gender": "male",
                    "age": 12,
                    "disability_status": "disabled",
                },
            ],
            "farm_size": 1.5,
            "farm_size_hectares": 1.5,  # CEL: Small farm household
            "disabled_count": 1,  # CEL: Disability Support Grant eligibility
            "child_count": 1,
            "district": "Western District",
        },
        "journey": [
            {"action": "register_household", "days_back": 120},
            {"action": "add_household_members", "days_back": 115},
            {
                "action": "disability_assessment",
                "member": "Miguel Martinez",
                "days_back": 110,
            },
            {
                "action": "verify_eligibility",
                "program": "Disability Support Grant",
                "cel_check": "member_exists_disabled",
                "days_back": 102,
            },
            {
                "action": "enroll_program",
                "program": "Disability Support Grant",
                "days_back": 100,
            },
            {
                "action": "create_payment",
                "amount": 175,
                "status": "paid",
                "days_back": 90,
            },
            {
                "action": "create_payment",
                "amount": 175,
                "status": "paid",
                "days_back": 60,
            },
            {
                "action": "create_payment",
                "amount": 175,
                "status": "paid",
                "days_back": 30,
            },
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
        "id": "luis_fernandez",
        "name": "Luis Fernandez",
        "type": "farmer",
        "story_title": "Pending Application",
        "story_description": "Shows application pipeline",
        "profile": {"gender": "male", "age": 40, "farm_size": 1.5},
        "journey": [
            {"action": "register", "days_back": 30},
            {
                "action": "apply_program",
                "program": "Input Subsidy Program",
                "status": "pending",
                "days_back": 25,
            },
        ],
    },
    {
        "id": "mary_johnson",
        "name": "Mary Johnson",
        "type": "individual",
        "story_title": "Rejected Application",
        "story_description": "Shows eligibility rules",
        "profile": {"gender": "female", "age": 32},
        "journey": [
            {"action": "register", "days_back": 60},
            {
                "action": "apply_program",
                "program": "Elderly Pension",
                "status": "rejected",
                "reason": "Age requirement not met",
                "days_back": 55,
            },
        ],
    },
    {
        "id": "ahmed_said",
        "name": "Ahmed Said",
        "type": "farmer",
        "story_title": "Multiple GRM Tickets",
        "story_description": "Shows GRM history",
        "profile": {"gender": "male", "age": 45, "farm_size": 2.0},
        "journey": [
            {"action": "register", "days_back": 200},
            {
                "action": "enroll_program",
                "program": "Cash Transfer Program",
                "days_back": 180,
            },
            {"action": "create_grm_ticket", "title": "Ticket 1", "days_back": 150},
            {"action": "create_grm_ticket", "title": "Ticket 2", "days_back": 100},
            {"action": "create_grm_ticket", "title": "Ticket 3", "days_back": 50},
        ],
    },
    {
        "id": "grace_okonkwo",
        "name": "Grace Okonkwo",
        "type": "farmer",
        "story_title": "Recently Registered",
        "story_description": "Shows new records",
        "profile": {"gender": "female", "age": 35, "farm_size": 1.0},
        "journey": [
            {"action": "register", "days_back": 5},
        ],
    },
    {
        "id": "david_kim",
        "name": "David Kim",
        "type": "farmer",
        "story_title": "Contract Farmer",
        "story_description": "Shows guaranteed market arrangement",
        "profile": {
            "gender": "male",
            "age": 48,
            "farm_size": 4.0,
            "contract_farming": True,
        },
        "journey": [
            {"action": "register", "days_back": 300},
            {"action": "add_farm_details", "days_back": 295},
            {"action": "register_contract", "buyer": "AgriCorp Ltd", "days_back": 250},
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
            "head": {
                "name": "Roberto Garcia",
                "gender": "male",
                "age": 42,
                "income": 15000,
            },
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
        "name": "Santos Family",
        "type": "household",
        "story_title": "Tutorial: Eligible (Low Income + Child Under 5)",
        "story_description": "Tutorial household meeting both criteria - ELIGIBLE",
        "profile": {
            "head": {
                "name": "Jose Santos",
                "gender": "male",
                "age": 35,
                "income": 8000,
            },
            "spouse": {"name": "Ana Santos", "gender": "female", "age": 32},
            "children": [
                {
                    "name": "Mia Santos",
                    "gender": "female",
                    "age": 4,
                },  # Born ~2021, under 5
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
        "name": "Cruz Family",
        "type": "household",
        "story_title": "Tutorial: Not Eligible (Income Above Threshold)",
        "story_description": "Tutorial household with income above threshold - NOT ELIGIBLE",
        "profile": {
            "head": {
                "name": "Pedro Cruz",
                "gender": "male",
                "age": 45,
                "income": 12000,
            },
            "spouse": {"name": "Teresa Cruz", "gender": "female", "age": 42},
            "children": [
                {"name": "Juan Cruz", "gender": "male", "age": 15},
                {"name": "Maria Cruz", "gender": "female", "age": 10},
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
        "name": "Reyes Family",
        "type": "household",
        "story_title": "Tutorial: Eligible (Low Income + Child Under 5)",
        "story_description": "Tutorial household meeting both criteria - ELIGIBLE",
        "profile": {
            "head": {
                "name": "Ramon Reyes",
                "gender": "male",
                "age": 30,
                "income": 6000,
            },
            "spouse": {"name": "Elena Reyes", "gender": "female", "age": 28},
            "children": [
                {
                    "name": "Lucia Reyes",
                    "gender": "female",
                    "age": 2,
                },  # Born ~2023, under 5
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
            "head": {
                "name": "Antonio Ramos",
                "gender": "male",
                "age": 48,
                "income": 18000,
            },
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
