# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Demo data providers for MIS demo.

This module activates standard registry variables (from spp_studio) and
demo-specific variables (from demo_constants.xml) for the MIS demo.

Standard Variables Activated (from spp_studio):
- Demographics: age
- Household composition: hh_size, child_count, elderly_count, working_age_count
- Household characteristics: is_female_headed, is_elderly_headed,
  has_pregnant_member, dependency_ratio
- Economic: per_capita_income, hh_total_income, hh_avg_income
- Constants: poverty_line, retirement_age, child_age_limit, per_child_benefit,
  base_benefit

Demo-Specific Variables Activated (from demo_constants.xml):
- vulnerability_threshold, base_child_grant, emergency_tier_1/2/3,
  elderly_pension_amount, cash_transfer_amount

These variables support the demo programs:
- Universal Child Grant: child_count, child_age_limit, per_child_benefit
- Elderly Social Pension: age, retirement_age, elderly_pension_amount
- Emergency Relief Fund: vulnerability_threshold, emergency_tier_*
- Cash Transfer Program: hh_size, poverty_line, hh_total_income
"""

from __future__ import annotations

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Standard variables from spp_studio to activate (module.xml_id format)
STANDARD_VARIABLES = [
    # Demographics (computed)
    "spp_studio.var_age",
    # Household composition (aggregate)
    "spp_studio.var_hh_size",
    "spp_studio.var_child_count",
    "spp_studio.var_children_under_5",
    "spp_studio.var_elderly_count",
    "spp_studio.var_working_age_count",
    # Household characteristics (computed)
    "spp_studio.var_is_female_headed",
    "spp_studio.var_is_elderly_headed",
    "spp_studio.var_has_pregnant_member",
    "spp_studio.var_dependency_ratio",
    # Economic (computed/aggregate)
    "spp_studio.var_per_capita_income",
    "spp_studio.var_hh_total_income",
    "spp_studio.var_hh_avg_income",
    # Constants
    "spp_studio.var_poverty_line",
    "spp_studio.var_retirement_age",
    "spp_studio.var_child_age_limit",
    "spp_studio.var_per_child_benefit",
    "spp_studio.var_base_benefit",
]

# Demo-specific variables to activate (from demo_constants.xml)
DEMO_VARIABLES = [
    "spp_mis_demo_v2.var_vulnerability_threshold",
    "spp_mis_demo_v2.var_base_child_grant",
    "spp_mis_demo_v2.var_emergency_tier_1",
    "spp_mis_demo_v2.var_emergency_tier_2",
    "spp_mis_demo_v2.var_emergency_tier_3",
    "spp_mis_demo_v2.var_elderly_pension_amount",
    "spp_mis_demo_v2.var_cash_transfer_amount",
]


def _activate_variables(env, xml_ids, source_name):
    """Activate variables by their XML IDs.

    Args:
        env: Odoo environment
        xml_ids: List of XML IDs (module.name format)
        source_name: Description for logging (e.g., "standard", "demo")
    """
    activated = 0
    skipped = 0
    errors = []

    for xml_id in xml_ids:
        try:
            variable = env.ref(xml_id, raise_if_not_found=False)
            if not variable:
                _logger.warning(
                    "[spp.mis.demo] Variable not found: %s (may not be installed)",
                    xml_id,
                )
                continue

            if variable.state == "active":
                skipped += 1
                continue

            if variable.state == "draft":
                variable.action_activate()
                activated += 1
                _logger.debug("[spp.mis.demo] Activated variable ID %s", variable.id)
            else:
                _logger.debug(
                    "[spp.mis.demo] Variable %s in state %s, skipping",
                    variable.name,
                    variable.state,
                )
                skipped += 1
        except Exception as e:
            errors.append(f"{xml_id}: {e}")
            _logger.error("[spp.mis.demo] Failed to activate %s: %s", xml_id, e)

    _logger.info(
        "[spp.mis.demo] %s variables: %d activated, %d already active, %d errors",
        source_name,
        activated,
        skipped,
        len(errors),
    )
    return activated, skipped, errors


def post_init_hook(env_or_cr, registry=None):
    """Post-initialization hook for demo module.

    Activates standard registry variables from spp_studio and demo-specific
    variables for use in the MIS demo programs.

    Args:
        env_or_cr: Either an Environment (Odoo 19+) or cursor (older versions)
        registry: Module registry (optional, for older Odoo versions)
    """
    # Handle both Odoo 19+ (env) and older (cr) signatures
    if hasattr(env_or_cr, "cr"):
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})

    _logger.info("[spp.mis.demo] Activating registry variables for MIS demo...")

    # Activate standard variables from spp_studio
    std_activated, std_skipped, std_errors = _activate_variables(env, STANDARD_VARIABLES, "Standard")

    # Activate demo-specific variables
    demo_activated, demo_skipped, demo_errors = _activate_variables(env, DEMO_VARIABLES, "Demo")

    total_activated = std_activated + demo_activated
    total_skipped = std_skipped + demo_skipped
    total_errors = len(std_errors) + len(demo_errors)

    _logger.info(
        "[spp.mis.demo] Registry variables ready: %d activated, %d skipped, %d errors",
        total_activated,
        total_skipped,
        total_errors,
    )
