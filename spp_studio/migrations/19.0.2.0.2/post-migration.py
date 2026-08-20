# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Fix shipped logic-pack filter items whose CEL expressions cannot evaluate (#431).

24 ``spp.studio.pack.item`` records shipped with filter expressions referencing
registrant fields or studio variables that exist in no module, so installing
them produced logic that could never translate or run. The pack data files are
``noupdate="1"``, so existing databases keep the broken records after the XML
is corrected - this migration applies the same fix directly:

- items whose expression has no working near-equivalent are deleted;
- items where a meaningful sub-expression survives are rewritten to it
  (matching the corrected pack data files).
"""

import json
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

REMOVED_ITEMS = [
    "spp_studio.pack_disability_item_status_check",
    "spp_studio.pack_ovc_item_orphan_status",
    "spp_studio.pack_gmi_item_work_barriers",
    "spp_studio.pack_ovc_item_school_enrollment",
    "spp_studio.pack_social_pension_item_no_formal_pension",
    "spp_studio.pack_pw_item_physical",
    "spp_studio.pack_pw_item_seasonal",
    "spp_studio.pack_cct_item_health_compliance",
    "spp_studio.pack_geo_item_service_access",
    "spp_studio.pack_excl_item_govt_employee",
    "spp_studio.pack_excl_item_formal_sector",
    "spp_studio.pack_excl_item_vehicle",
    "spp_studio.pack_excl_item_business",
    "spp_studio.pack_excl_item_housing",
    "spp_studio.pack_excl_item_pension",
    "spp_studio.pack_excl_item_other_programs",
    "spp_studio.pack_excl_item_tax",
    "spp_studio.pack_excl_item_bank_balance",
    "spp_studio.pack_excl_item_livestock",
    "spp_studio.pack_excl_item_institutional",
]

# xmlid -> (new cel_expression, new description)
REWRITTEN_ITEMS = {
    "spp_studio.pack_ovc_item_child_age": (
        "age < child_age_limit",
        "Child must be under child_age_limit.",
    ),
    "spp_studio.pack_ovc_item_vulnerable_hh": (
        "is_elderly_headed || is_child_headed",
        "Household meets vulnerability criteria (elderly-headed or child-headed).",
    ),
    "spp_studio.pack_gmi_item_residency": (
        "residency_months >= 12",
        "Minimum residency duration requirement (12 months).",
    ),
    "spp_studio.pack_pw_item_poverty": (
        "per_capita_income <= poverty_threshold",
        "Household meets poverty criteria for public works targeting.",
    ),
}


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    removed = 0
    for xmlid in REMOVED_ITEMS:
        item = env.ref(xmlid, raise_if_not_found=False)
        if item:
            item.unlink()
            removed += 1

    rewritten = 0
    for xmlid, (expression, description) in REWRITTEN_ITEMS.items():
        item = env.ref(xmlid, raise_if_not_found=False)
        if not item:
            continue
        item.write(
            {
                "logic_data": json.dumps({"cel_expression": expression}),
                "description": description,
            }
        )
        rewritten += 1

    _logger.info(
        "spp_studio 19.0.2.0.2: removed %d and rewrote %d shipped pack items with non-evaluable CEL expressions (#431)",
        removed,
        rewritten,
    )
