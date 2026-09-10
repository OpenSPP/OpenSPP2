# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Fix shipped logic-pack filter items whose CEL expressions cannot evaluate (#431).

24 ``spp.studio.pack.item`` records shipped with filter expressions referencing
registrant fields that exist in no module (in some cases through catalogued
``spp.cel.variable`` records whose ``source_field`` is dangling - see #446),
so installing them produced logic that could never translate or run. The pack
data files are ``noupdate="1"``, so existing databases keep the broken records
after the XML is corrected - this migration applies the same fix directly:

- items whose expression has no working near-equivalent are deleted;
- items where a meaningful stricter sub-expression survives are rewritten to
  it (matching the corrected pack data files).

Every write is guarded on the item still carrying the known-broken shipped
expression: ``noupdate`` exists so local changes survive upgrades, and a
deployment may have repaired an item itself (e.g. by defining the missing
variables), so locally-modified items are left untouched and logged.

Two flagged items need special handling:

- Institutional Residence Exclusion keeps its shipped expression - it only
  lacked a variable definition, and the new ``in_institutional_care`` standard
  variable (over the existing ``spp_registry`` field) is created by the
  regular data load, which is not ``noupdate`` for ``standard_variables.xml``.
  The variable applies to individuals, so the item's shipped
  ``context_type="both"`` is narrowed to ``individual`` here.
- Logic already installed FROM a removed item (``installed_logic_id`` ->
  ``spp.cel.expression``) is deliberately NOT deleted: once installed it is
  the deployment's own data, possibly referenced by programs. Those
  expressions were never evaluable, and cleaning them up is left to the
  deployment.
"""

import json
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# xmlid -> known-broken shipped cel_expression (deleted only if still intact)
REMOVED_ITEMS = {
    "spp_studio.pack_disability_item_status_check": "has_disability && disability_certified",
    "spp_studio.pack_ovc_item_orphan_status": "is_orphan || (!has_mother && !has_father)",
    "spp_studio.pack_ovc_item_school_enrollment": ("age < 6 || is_enrolled_in_school || has_enrollment_exemption"),
    "spp_studio.pack_social_pension_item_no_formal_pension": ("!has_formal_pension || formal_pension_amount == 0"),
    "spp_studio.pack_gmi_item_work_barriers": (
        "has_disabled_member || has_caregiver_responsibilities || is_single_parent || no_working_age_members"
    ),
    "spp_studio.pack_gmi_item_residency": "is_legal_resident && residency_months >= 12",
    "spp_studio.pack_pw_item_physical": "can_perform_manual_labor || eligible_for_light_duty",
    "spp_studio.pack_pw_item_seasonal": "is_lean_season || !has_active_farm_work",
    "spp_studio.pack_cct_item_health_compliance": (
        "children_0_5 == 0 || (health_checkups_completed && vaccinations_current)"
    ),
    "spp_studio.pack_geo_item_service_access": ("distance_to_health_facility > 10 || distance_to_school > 5"),
    "spp_studio.pack_excl_item_govt_employee": "!has_government_employee",
    "spp_studio.pack_excl_item_formal_sector": "!has_formal_employment || formal_income < 5000",
    "spp_studio.pack_excl_item_vehicle": "!owns_car && motorcycle_count <= 1",
    "spp_studio.pack_excl_item_business": "!owns_registered_business || business_revenue < 50000",
    "spp_studio.pack_excl_item_housing": "housing_quality_score <= 3 || !has_permanent_structure",
    "spp_studio.pack_excl_item_pension": "!receives_contributory_pension || pension_amount < 1000",
    "spp_studio.pack_excl_item_other_programs": "!enrolled_in_similar_program",
    "spp_studio.pack_excl_item_tax": "!pays_income_tax",
    "spp_studio.pack_excl_item_bank_balance": "total_bank_balance <= 50000",
    "spp_studio.pack_excl_item_livestock": "livestock_tlu <= 5",
}

# xmlid -> (known-broken shipped expression, new expression, new description)
REWRITTEN_ITEMS = {
    "spp_studio.pack_ovc_item_child_age": (
        "age < child_age_limit || (age < 25 && is_in_education)",
        "age < child_age_limit",
        "Child must be under child_age_limit.",
    ),
    "spp_studio.pack_ovc_item_vulnerable_hh": (
        "is_elderly_headed || is_child_headed || is_skipped_generation || has_chronically_ill_head",
        "is_elderly_headed || is_child_headed",
        "Household meets vulnerability criteria (elderly-headed or child-headed).",
    ),
    "spp_studio.pack_pw_item_poverty": (
        "per_capita_income <= poverty_threshold || is_food_insecure",
        "per_capita_income <= poverty_threshold",
        "Household meets poverty criteria for public works targeting.",
    ),
}


def _current_expression(item):
    try:
        return json.loads(item.logic_data or "{}").get("cel_expression")
    except (ValueError, TypeError):
        return None


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    removed = 0
    for xmlid, shipped_expr in REMOVED_ITEMS.items():
        item = env.ref(xmlid, raise_if_not_found=False)
        if not item:
            continue
        if _current_expression(item) != shipped_expr:
            _logger.warning(
                "spp_studio 19.0.2.0.2: pack item %s was modified locally; "
                "leaving it in place instead of removing it (#431)",
                xmlid,
            )
            continue
        item.unlink()
        removed += 1

    rewritten = 0
    for xmlid, (shipped_expr, new_expr, new_desc) in REWRITTEN_ITEMS.items():
        item = env.ref(xmlid, raise_if_not_found=False)
        if not item:
            continue
        if _current_expression(item) != shipped_expr:
            _logger.warning(
                "spp_studio 19.0.2.0.2: pack item %s was modified locally; "
                "leaving it in place instead of rewriting it (#431)",
                xmlid,
            )
            continue
        try:
            logic_data = json.loads(item.logic_data or "{}")
        except (ValueError, TypeError):
            logic_data = {}
        logic_data["cel_expression"] = new_expr
        item.write(
            {
                "logic_data": json.dumps(logic_data),
                "description": new_desc,
            }
        )
        rewritten += 1

    # Institutional Residence Exclusion: the new in_institutional_care
    # variable applies to individuals, so narrow the item's shipped
    # context_type accordingly (guarded like the writes above).
    institutional = env.ref("spp_studio.pack_excl_item_institutional", raise_if_not_found=False)
    if (
        institutional
        and institutional.context_type == "both"
        and _current_expression(institutional) == "!in_institutional_care"
    ):
        institutional.write({"context_type": "individual"})

    _logger.info(
        "spp_studio 19.0.2.0.2: removed %d and rewrote %d shipped pack items with non-evaluable CEL expressions (#431)",
        removed,
        rewritten,
    )
