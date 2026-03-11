# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from . import models, services


def post_init_hook(env):
    """Initialize vocabulary functions and concept groups.

    This hook is called after module installation to:
    1. Ensure standard concept groups exist (search-or-create pattern)
    2. Register vocabulary functions with CEL function registry
    """
    # Ensure standard concept groups exist (safe for re-runs)
    _ensure_concept_groups(env)

    # Register vocabulary functions
    env["spp.cel.vocabulary.functions"].register_vocabulary_functions()


def _ensure_concept_groups(env):
    """Ensure standard concept groups exist using search-or-create pattern.

    This is idempotent and safe for upgrades where records may already exist
    from tests or previous installations.
    """
    ConceptGroup = env["spp.vocabulary.concept.group"]

    # Standard concept groups - search first, create only if missing
    standard_groups = [
        {
            "name": "feminine_gender",
            "label": "Feminine Gender",
            "cel_function": "is_female",
            "target_field": "gender_id",
            "description": (
                "Codes representing feminine gender identity. "
                "Add codes from your gender vocabulary that represent "
                "female/feminine gender."
            ),
        },
        {
            "name": "masculine_gender",
            "label": "Masculine Gender",
            "cel_function": "is_male",
            "target_field": "gender_id",
            "description": (
                "Codes representing masculine gender identity. "
                "Add codes from your gender vocabulary that represent "
                "male/masculine gender."
            ),
        },
        {
            "name": "head_of_household",
            "label": "Head of Household",
            "cel_function": "is_head",
            "description": (
                "Relationship types indicating head of household role. "
                "Add codes from your relationship vocabulary that represent "
                "household heads."
            ),
        },
        {
            "name": "pregnant_eligible",
            "label": "Pregnant/Eligible",
            "cel_function": "is_pregnant",
            "target_field": "pregnancy_status_id",
            "description": (
                "Pregnancy statuses eligible for maternal benefits. "
                "Add codes from your pregnancy status vocabulary that represent "
                "pregnant/expecting mothers."
            ),
        },
        {
            "name": "climate_hazards",
            "label": "Climate-related Hazards",
            "cel_function": None,
            "description": (
                "Hazard types related to climate and weather events "
                "(typhoons, floods, droughts, etc.). "
                "Add codes from your hazard vocabulary."
            ),
        },
        {
            "name": "geophysical_hazards",
            "label": "Geophysical Hazards",
            "cel_function": None,
            "description": (
                "Hazard types related to earth processes "
                "(earthquakes, volcanic eruptions, landslides, etc.). "
                "Add codes from your hazard vocabulary."
            ),
        },
        {
            "name": "children",
            "label": "Children",
            "cel_function": None,
            "description": (
                "Age group codes representing children (typically under 18 years). "
                "Add codes from your age group vocabulary if applicable."
            ),
        },
        {
            "name": "adults",
            "label": "Adults",
            "cel_function": None,
            "description": (
                "Age group codes representing adults. Add codes from your age group vocabulary if applicable."
            ),
        },
        {
            "name": "elderly",
            "label": "Elderly/Senior Citizens",
            "cel_function": None,
            "description": (
                "Age group codes representing elderly or senior citizens. "
                "Add codes from your age group vocabulary if applicable."
            ),
        },
        {
            "name": "persons_with_disability",
            "label": "Persons with Disability",
            "cel_function": None,
            "description": (
                "Disability type codes. "
                "Add all codes from your disability vocabulary that indicate "
                "presence of a disability."
            ),
        },
    ]

    for group_data in standard_groups:
        existing = ConceptGroup.search([("name", "=", group_data["name"])], limit=1)
        if not existing:
            # Build create values, excluding None values
            create_vals = {k: v for k, v in group_data.items() if v is not None}
            ConceptGroup.create(create_vals)
