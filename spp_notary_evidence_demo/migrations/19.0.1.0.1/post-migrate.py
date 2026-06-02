# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Migrate Notary demo CEL expressions to explicit evidence syntax."""

import logging

_logger = logging.getLogger(__name__)

EXPRESSION_REPLACEMENTS = {
    "notary_registry_lab_civil_notary_person_is_alive == true": (
        "r.evidence.registry_lab_civil_notary.person_is_alive == true"
    ),
    "notary_registry_lab_shared_eligibility_notary_eligible_for_combined_support == true": (
        "r.evidence.registry_lab_shared_eligibility_notary.eligible_for_combined_support == true"
    ),
    "notary_registry_lab_shared_eligibility_notary_health_service_available == true": (
        "r.evidence.registry_lab_shared_eligibility_notary.health_service_available == true"
    ),
}

CEL_EXPRESSION_TABLES = {
    "spp_program_membership_manager_default": """
        UPDATE spp_program_membership_manager_default
        SET cel_expression = %s
        WHERE cel_expression = %s
    """,
    "spp_cel_expression": """
        UPDATE spp_cel_expression
        SET cel_expression = %s
        WHERE cel_expression = %s
    """,
}


def migrate(cr, version):
    """Rewrite installed demo program expressions from flat Notary variables."""
    for table, query in CEL_EXPRESSION_TABLES.items():
        for old_expression, new_expression in EXPRESSION_REPLACEMENTS.items():
            cr.execute(query, (new_expression, old_expression))
            if cr.rowcount:
                _logger.info(
                    "Updated %s %s row(s) from %s to explicit Notary evidence syntax",
                    cr.rowcount,
                    table,
                    old_expression,
                )
