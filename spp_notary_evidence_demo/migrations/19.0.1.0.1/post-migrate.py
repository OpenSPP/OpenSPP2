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


def migrate(cr, version):
    """Rewrite installed demo program expressions from flat Notary variables."""
    for table in ("spp_program_membership_manager_default", "spp_cel_expression"):
        for old_expression, new_expression in EXPRESSION_REPLACEMENTS.items():
            cr.execute(
                f"""
                UPDATE {table}
                SET cel_expression = %s
                WHERE cel_expression = %s
                """,
                (new_expression, old_expression),
            )
            if cr.rowcount:
                _logger.info(
                    "Updated %s %s row(s) from %s to explicit Notary evidence syntax",
                    cr.rowcount,
                    table,
                    old_expression,
                )
