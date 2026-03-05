# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Case Management Demo Stories for OpenSPP

Fixed personas that demonstrate Case Management workflows for:
- Sales demos ("Search for the Santos Family case...")
- Training sessions
- Feature walkthroughs

Each story demonstrates a specific case management scenario.
"""

# Reserved names to avoid conflicts with random generation
RESERVED_CASE_NAMES = [
    "Santos Family Support",
    "Dela Cruz Emergency",
    "Garcia Elder Care",
    "Mendoza Child Protection",
    "Hassan Resettlement",
    "Morales Household Crisis",
    "Martinez Disability Support",
    "Al-Rahman Family Assessment",
    "Said Family Support",
]

CASE_DEMO_STORIES = [
    {
        "id": "santos_family_support",
        "case_name": "Santos Family Support",
        "story_title": "Full Case Lifecycle",
        "story_description": "Complete case from intake to successful closure",
        "case_profile": {
            "case_type": "General Support",
            "intensity_level": "2",
            "priority": "medium",
            "intake_source": "referral",
            "presenting_issue": "Family experiencing financial hardship following job loss. "
            "Needs assistance with basic needs and employment support.",
        },
        "client": {
            "name": "Maria Santos",
            "type": "individual",
        },
        "journey": [
            {"action": "intake", "days_back": 90, "notes": "Referred by community health worker"},
            {"action": "assessment", "days_back": 87, "notes": "Comprehensive needs assessment completed"},
            {"action": "create_plan", "days_back": 85, "plan_name": "Santos Family Support Plan"},
            {"action": "add_intervention", "days_back": 85, "intervention": "Emergency food assistance"},
            {"action": "add_intervention", "days_back": 85, "intervention": "Employment counseling referral"},
            {"action": "add_intervention", "days_back": 85, "intervention": "Skills training enrollment"},
            {"action": "home_visit", "days_back": 80, "purpose": "Initial home assessment"},
            {"action": "complete_intervention", "days_back": 70, "intervention": "Emergency food assistance"},
            {"action": "progress_note", "days_back": 60, "note": "Family receiving regular food support"},
            {"action": "home_visit", "days_back": 50, "purpose": "Progress check"},
            {"action": "complete_intervention", "days_back": 40, "intervention": "Employment counseling referral"},
            {"action": "progress_note", "days_back": 30, "note": "Client enrolled in vocational training"},
            {"action": "complete_intervention", "days_back": 20, "intervention": "Skills training enrollment"},
            {"action": "final_visit", "days_back": 10, "purpose": "Closure assessment"},
            {"action": "close_case", "days_back": 5, "outcome": "successful", "reason": "Goals achieved"},
        ],
        "demo_points": [
            "Complete case lifecycle from intake to closure",
            "Intervention plan with multiple activities",
            "Home visits with documentation",
            "Progress notes showing improvement",
            "Successful case closure",
        ],
    },
    {
        "id": "dela_cruz_emergency",
        "case_name": "Dela Cruz Emergency Response",
        "story_title": "High Intensity Emergency Case",
        "story_description": "Urgent case requiring immediate intervention",
        "case_profile": {
            "case_type": "Emergency Assistance",
            "intensity_level": "3",
            "priority": "urgent",
            "intake_source": "grm",
            "presenting_issue": "Family displaced due to house fire. "
            "Lost all belongings, need immediate shelter and basic supplies.",
        },
        "client": {
            "name": "Juan Dela Cruz",
            "type": "household",
        },
        "journey": [
            {"action": "intake", "days_back": 30, "notes": "Emergency intake - house fire displacement"},
            {"action": "emergency_assessment", "days_back": 30, "notes": "Same-day emergency assessment"},
            {"action": "create_plan", "days_back": 30, "plan_name": "Dela Cruz Emergency Response"},
            {"action": "add_intervention", "days_back": 30, "intervention": "Emergency shelter placement"},
            {"action": "add_intervention", "days_back": 30, "intervention": "Emergency cash assistance"},
            {"action": "add_intervention", "days_back": 30, "intervention": "Basic supplies provision"},
            {"action": "complete_intervention", "days_back": 29, "intervention": "Emergency shelter placement"},
            {"action": "complete_intervention", "days_back": 29, "intervention": "Basic supplies provision"},
            {"action": "progress_note", "days_back": 28, "note": "Family placed in temporary shelter"},
            {"action": "complete_intervention", "days_back": 27, "intervention": "Emergency cash assistance"},
            {"action": "add_intervention", "days_back": 25, "intervention": "Permanent housing search"},
            {"action": "home_visit", "days_back": 20, "purpose": "Shelter check-in"},
            {"action": "progress_note", "days_back": 15, "note": "Family stabilizing, housing search ongoing"},
        ],
        "demo_points": [
            "High intensity (Level 3) urgent case",
            "Same-day emergency response",
            "Multiple rapid interventions",
            "Case from GRM escalation",
            "Ongoing case management",
        ],
    },
    {
        "id": "garcia_elder_care",
        "case_name": "Garcia Elder Care Coordination",
        "story_title": "Long-term Care Case",
        "story_description": "Ongoing support for elderly client with multiple needs",
        "case_profile": {
            "case_type": "Health Support",
            "intensity_level": "2",
            "priority": "medium",
            "intake_source": "walk_in",
            "presenting_issue": "Elderly widow living alone, difficulty managing medications "
            "and daily activities. No family support in area.",
        },
        "client": {
            "name": "Rosa Garcia",
            "type": "individual",
        },
        "journey": [
            {"action": "intake", "days_back": 120, "notes": "Self-referred, needs daily living support"},
            {"action": "assessment", "days_back": 118, "notes": "Health and social needs assessment"},
            {"action": "create_plan", "days_back": 115, "plan_name": "Garcia Care Coordination Plan"},
            {"action": "add_intervention", "days_back": 115, "intervention": "Home health aide referral"},
            {"action": "add_intervention", "days_back": 115, "intervention": "Medication management support"},
            {"action": "add_intervention", "days_back": 115, "intervention": "Meals on wheels enrollment"},
            {
                "action": "add_referral",
                "days_back": 110,
                "service": "Home Health Services",
                "reason": "Daily care needs",
            },
            {"action": "home_visit", "days_back": 100, "purpose": "Care coordination check"},
            {"action": "complete_intervention", "days_back": 95, "intervention": "Meals on wheels enrollment"},
            {"action": "progress_note", "days_back": 90, "note": "Services in place, client adjusting well"},
            {"action": "home_visit", "days_back": 60, "purpose": "Quarterly review"},
            {"action": "progress_note", "days_back": 60, "note": "Client health stable, services effective"},
            {"action": "home_visit", "days_back": 30, "purpose": "Quarterly review"},
            {"action": "progress_note", "days_back": 30, "note": "Continuing monitoring, may reduce intensity"},
        ],
        "demo_points": [
            "Long-term ongoing case",
            "Service referrals to external providers",
            "Regular home visits",
            "Care coordination across services",
            "Monitoring phase case",
        ],
    },
    {
        "id": "mendoza_child_protection",
        "case_name": "Mendoza Child Welfare",
        "story_title": "Child Protection Case",
        "story_description": "Sensitive case requiring careful intervention",
        "case_profile": {
            "case_type": "Child Protection",
            "intensity_level": "3",
            "priority": "high",
            "intake_source": "referral",
            "presenting_issue": "School reported concerns about child welfare. "
            "Child showing signs of neglect, family needs support services.",
            "sensitivity": "high",
        },
        "client": {
            "name": "Ana Mendoza",
            "type": "household",
        },
        "journey": [
            {"action": "intake", "days_back": 45, "notes": "School social worker referral"},
            {"action": "safety_assessment", "days_back": 45, "notes": "Immediate safety assessment conducted"},
            {"action": "create_plan", "days_back": 43, "plan_name": "Mendoza Family Support Plan"},
            {"action": "add_intervention", "days_back": 43, "intervention": "Parenting support program"},
            {"action": "add_intervention", "days_back": 43, "intervention": "Family counseling"},
            {"action": "add_intervention", "days_back": 43, "intervention": "School liaison coordination"},
            {"action": "home_visit", "days_back": 40, "purpose": "Home safety check"},
            {"action": "progress_note", "days_back": 38, "note": "Home environment acceptable, services starting"},
            {"action": "home_visit", "days_back": 30, "purpose": "Weekly check-in"},
            {"action": "home_visit", "days_back": 23, "purpose": "Weekly check-in"},
            {"action": "progress_note", "days_back": 20, "note": "Family engaging with parenting program"},
            {"action": "home_visit", "days_back": 16, "purpose": "Weekly check-in"},
            {"action": "progress_note", "days_back": 10, "note": "Positive changes observed, reducing visit frequency"},
        ],
        "demo_points": [
            "Child protection case type",
            "High sensitivity flag",
            "Safety assessment workflow",
            "Frequent monitoring visits",
            "Multi-service coordination",
        ],
    },
    {
        "id": "hassan_resettlement",
        "case_name": "Hassan Resettlement Support",
        "story_title": "Displaced Person Case",
        "story_description": "Case escalated from GRM for comprehensive support",
        "case_profile": {
            "case_type": "General Support",
            "intensity_level": "2",
            "priority": "high",
            "intake_source": "grm",
            "presenting_issue": "Internally displaced farmer seeking resettlement assistance. "
            "Lost farm and livelihood, needs comprehensive reintegration support.",
        },
        "client": {
            "name": "Ibrahim Hassan",
            "type": "individual",
        },
        "journey": [
            {"action": "intake", "days_back": 60, "notes": "Escalated from GRM ticket"},
            {"action": "assessment", "days_back": 58, "notes": "Displacement and needs assessment"},
            {"action": "create_plan", "days_back": 55, "plan_name": "Hassan Reintegration Plan"},
            {"action": "add_intervention", "days_back": 55, "intervention": "Housing assistance application"},
            {"action": "add_intervention", "days_back": 55, "intervention": "Livelihood restoration support"},
            {"action": "add_intervention", "days_back": 55, "intervention": "Documentation assistance"},
            {"action": "add_referral", "days_back": 50, "service": "Housing Authority", "reason": "Permanent housing"},
            {"action": "progress_note", "days_back": 45, "note": "Housing application submitted"},
            {"action": "home_visit", "days_back": 40, "purpose": "Current situation review"},
            {"action": "complete_intervention", "days_back": 35, "intervention": "Documentation assistance"},
            {"action": "progress_note", "days_back": 30, "note": "Documents restored, awaiting housing decision"},
            {"action": "progress_note", "days_back": 15, "note": "Housing approved, preparing for relocation"},
        ],
        "demo_points": [
            "Case from GRM escalation",
            "Displacement/vulnerability scenario",
            "External referrals",
            "Document restoration workflow",
            "Housing assistance coordination",
        ],
    },
    {
        "id": "morales_household_crisis",
        "case_name": "Morales Household Crisis",
        "story_title": "Multi-Member Household Case",
        "story_description": "Complex household with multiple needs",
        "case_profile": {
            "case_type": "General Support",
            "intensity_level": "2",
            "priority": "medium",
            "intake_source": "outreach",
            "presenting_issue": "Household identified during community outreach. "
            "Multiple children, unemployed head of household, food insecurity.",
        },
        "client": {
            "name": "Carlos Morales",
            "type": "household",
        },
        "journey": [
            {"action": "intake", "days_back": 75, "notes": "Community outreach identification"},
            {"action": "assessment", "days_back": 72, "notes": "Household needs assessment"},
            {"action": "create_plan", "days_back": 70, "plan_name": "Morales Family Stabilization Plan"},
            {"action": "add_intervention", "days_back": 70, "intervention": "Food assistance enrollment"},
            {"action": "add_intervention", "days_back": 70, "intervention": "Child education support"},
            {"action": "add_intervention", "days_back": 70, "intervention": "Employment services referral"},
            {"action": "complete_intervention", "days_back": 65, "intervention": "Food assistance enrollment"},
            {"action": "home_visit", "days_back": 60, "purpose": "Service coordination"},
            {"action": "progress_note", "days_back": 55, "note": "Children enrolled in school support program"},
            {"action": "complete_intervention", "days_back": 50, "intervention": "Child education support"},
            {"action": "progress_note", "days_back": 40, "note": "Head of household started job training"},
            {"action": "home_visit", "days_back": 30, "purpose": "Progress review"},
            {"action": "progress_note", "days_back": 20, "note": "Family situation improving"},
        ],
        "demo_points": [
            "Household/group case type",
            "Community outreach intake",
            "Multiple intervention tracks",
            "Child-focused services",
            "Employment support coordination",
        ],
    },
    {
        "id": "martinez_disability_support",
        "case_name": "Martinez Disability Support",
        "story_title": "Disability Inclusion Case",
        "story_description": "Family with disabled child requiring specialized support services",
        "case_profile": {
            "case_type": "Health Support",
            "intensity_level": "2",
            "priority": "high",
            "intake_source": "referral",
            "presenting_issue": "Family caring for child with cerebral palsy. "
            "Need assistance accessing disability benefits, medical equipment, "
            "and inclusive education services.",
        },
        "client": {
            "name": "David Martinez",
            "type": "household",
        },
        "journey": [
            {"action": "intake", "days_back": 100, "notes": "Referred by disability rights organization"},
            {"action": "assessment", "days_back": 97, "notes": "Comprehensive disability needs assessment"},
            {"action": "create_plan", "days_back": 95, "plan_name": "Martinez Disability Support Plan"},
            {"action": "add_intervention", "days_back": 95, "intervention": "Disability grant application"},
            {"action": "add_intervention", "days_back": 95, "intervention": "Medical equipment assistance"},
            {"action": "add_intervention", "days_back": 95, "intervention": "Inclusive education enrollment"},
            {
                "action": "add_referral",
                "days_back": 90,
                "service": "Disability Services Center",
                "reason": "Wheelchair and mobility aids",
            },
            {"action": "complete_intervention", "days_back": 85, "intervention": "Disability grant application"},
            {"action": "progress_note", "days_back": 80, "note": "Disability Support Grant approved - $175/month"},
            {"action": "home_visit", "days_back": 70, "purpose": "Equipment delivery coordination"},
            {"action": "complete_intervention", "days_back": 65, "intervention": "Medical equipment assistance"},
            {"action": "progress_note", "days_back": 60, "note": "Wheelchair delivered, family training completed"},
            {"action": "home_visit", "days_back": 45, "purpose": "School enrollment support"},
            {"action": "complete_intervention", "days_back": 40, "intervention": "Inclusive education enrollment"},
            {"action": "progress_note", "days_back": 30, "note": "Miguel enrolled in inclusive school program"},
            {"action": "home_visit", "days_back": 15, "purpose": "Quarterly review"},
        ],
        "demo_points": [
            "Disability-focused case management",
            "Integration with Disability Support Grant program",
            "Medical equipment coordination",
            "Inclusive education advocacy",
            "Multi-service referral workflow",
        ],
    },
    {
        "id": "al_rahman_family_assessment",
        "case_name": "Al-Rahman Family Assessment",
        "story_title": "GRM-Initiated Assessment Case",
        "story_description": "Case opened after GRM inquiry about program eligibility",
        "case_profile": {
            "case_type": "General Support",
            "intensity_level": "1",
            "priority": "medium",
            "intake_source": "grm",
            "presenting_issue": "Family inquired about program eligibility through GRM. "
            "Assessment revealed need for child support services. "
            "Mother seeking assistance for 2 children while husband works abroad.",
        },
        "client": {
            "name": "Fatima Al-Rahman",
            "type": "individual",
        },
        "journey": [
            {"action": "intake", "days_back": 40, "notes": "Escalated from GRM eligibility inquiry"},
            {"action": "assessment", "days_back": 38, "notes": "Family needs assessment - eligible for child grant"},
            {"action": "create_plan", "days_back": 35, "plan_name": "Al-Rahman Support Plan"},
            {"action": "add_intervention", "days_back": 35, "intervention": "Universal Child Grant enrollment"},
            {"action": "add_intervention", "days_back": 35, "intervention": "School supplies assistance"},
            {"action": "progress_note", "days_back": 30, "note": "Child Grant application submitted"},
            {"action": "complete_intervention", "days_back": 25, "intervention": "Universal Child Grant enrollment"},
            {"action": "progress_note", "days_back": 20, "note": "Grant approved - $100/month for 2 children"},
            {"action": "home_visit", "days_back": 15, "purpose": "Enrollment verification"},
            {"action": "complete_intervention", "days_back": 10, "intervention": "School supplies assistance"},
            {"action": "progress_note", "days_back": 5, "note": "Family stable, monitoring for graduation"},
        ],
        "demo_points": [
            "GRM to case management escalation",
            "Program enrollment assistance",
            "Universal Child Grant integration",
            "Quick resolution pathway",
            "Proactive outreach from inquiry",
        ],
    },
    {
        "id": "said_family_support",
        "case_name": "Said Family Support",
        "story_title": "Repeat GRM Beneficiary Case",
        "story_description": "Case for beneficiary with multiple GRM tickets requiring holistic support",
        "case_profile": {
            "case_type": "General Support",
            "intensity_level": "1",
            "priority": "medium",
            "intake_source": "grm",
            "presenting_issue": "Beneficiary filed multiple GRM tickets over 3 months "
            "regarding payment issues and account updates. Pattern suggests need "
            "for comprehensive case management rather than ticket-by-ticket resolution.",
        },
        "client": {
            "name": "Ahmed Said",
            "type": "individual",
        },
        "journey": [
            {"action": "intake", "days_back": 25, "notes": "Pattern of repeat GRM tickets identified"},
            {"action": "assessment", "days_back": 23, "notes": "Root cause analysis - banking access issues"},
            {"action": "create_plan", "days_back": 20, "plan_name": "Said Support Plan"},
            {"action": "add_intervention", "days_back": 20, "intervention": "Bank account regularization"},
            {"action": "add_intervention", "days_back": 20, "intervention": "Financial literacy training"},
            {"action": "progress_note", "days_back": 15, "note": "Bank account issues resolved"},
            {"action": "complete_intervention", "days_back": 12, "intervention": "Bank account regularization"},
            {"action": "progress_note", "days_back": 10, "note": "Enrolled in community financial literacy program"},
            {"action": "home_visit", "days_back": 5, "purpose": "Follow-up on payment receipt"},
        ],
        "demo_points": [
            "Pattern detection from GRM history",
            "Root cause analysis approach",
            "Financial inclusion support",
            "Preventive case management",
            "Reduced future GRM tickets",
        ],
    },
]

# Background cases for volume
BACKGROUND_CASES = [
    {
        "id": "pending_intake",
        "case_name": "Fernandez Intake Pending",
        "story_title": "New Intake",
        "case_profile": {
            "case_type": "General Support",
            "intensity_level": "1",
            "priority": "low",
            "intake_source": "phone",
        },
        "journey": [
            {"action": "intake", "days_back": 3, "notes": "Phone intake, awaiting assessment"},
        ],
    },
    {
        "id": "assessment_phase",
        "case_name": "Johnson Assessment",
        "story_title": "In Assessment",
        "case_profile": {
            "case_type": "Health Support",
            "intensity_level": "1",
            "priority": "medium",
            "intake_source": "walk_in",
        },
        "journey": [
            {"action": "intake", "days_back": 10, "notes": "Walk-in client"},
            {"action": "assessment", "days_back": 7, "notes": "Assessment in progress"},
        ],
    },
    {
        "id": "closed_unsuccessful",
        "case_name": "Kim Case Closed",
        "story_title": "Closed - Lost Contact",
        "case_profile": {
            "case_type": "General Support",
            "intensity_level": "1",
            "priority": "low",
            "intake_source": "referral",
        },
        "journey": [
            {"action": "intake", "days_back": 90, "notes": "Referred by partner agency"},
            {"action": "assessment", "days_back": 85, "notes": "Initial assessment"},
            {"action": "create_plan", "days_back": 80, "plan_name": "Support Plan"},
            {"action": "progress_note", "days_back": 60, "note": "Unable to contact client"},
            {"action": "progress_note", "days_back": 45, "note": "Multiple contact attempts failed"},
            {"action": "close_case", "days_back": 30, "outcome": "unsuccessful", "reason": "Lost to follow-up"},
        ],
    },
]


def get_all_case_stories():
    """Return all case demo stories (main + background)."""
    return CASE_DEMO_STORIES + BACKGROUND_CASES


def get_main_case_stories():
    """Return only the main case demo stories."""
    return CASE_DEMO_STORIES


def get_background_case_stories():
    """Return only the background case stories."""
    return BACKGROUND_CASES


def get_case_story_by_id(story_id):
    """Get a specific case story by ID."""
    for story in get_all_case_stories():
        if story["id"] == story_id:
            return story
    return None
