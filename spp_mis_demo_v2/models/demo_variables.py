# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Demo Variables for MIS Demo V2

Provides constant values and helper functions for managing demo CEL variables.
These variables are used by demo programs for eligibility and benefit calculations.

Usage:
    from odoo.addons.spp_mis_demo_v2.models.demo_variables import (
        get_demo_constant,
        DEMO_CONSTANTS,
    )

    # Get a constant value
    retirement_age = get_demo_constant(env, 'retirement_age', default=65)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from odoo.api import Environment

_logger = logging.getLogger(__name__)


# Default constant values (used when XML data not loaded or as fallback)
DEMO_CONSTANTS = {
    # Eligibility thresholds
    "poverty_line": 5000,  # Monthly income threshold
    "retirement_age": 65,  # Minimum age for elderly pension
    "child_age_limit": 18,  # Maximum age to be considered a child
    "max_farm_size_subsidy": 10,  # Max hectares for input subsidy
    "vulnerability_threshold": 70,  # Min score for emergency eligibility
    # Benefit amounts - Child support
    "base_child_grant": 50,  # Per-child amount
    # Benefit amounts - Disability
    "disability_grant_base": 100,  # Base amount
    "disability_grant_per_member": 75,  # Per disabled member
    # Benefit amounts - Emergency (tiered)
    "emergency_tier_1": 500,  # Score >= 90
    "emergency_tier_2": 400,  # Score >= 80
    "emergency_tier_3": 300,  # Score >= 70
    # Fixed program amounts
    "elderly_pension_amount": 100,
    "cash_transfer_amount": 150,
}


def get_demo_constant(env: Environment, name: str, default: Any = None) -> int | float | str:
    """Get a demo constant value from CEL variables or fallback to default.

    Args:
        env: Odoo environment
        name: Variable name (e.g., 'poverty_line', 'retirement_age')
        default: Fallback value if not found

    Returns:
        The constant value (number or string)
    """
    # Try to get from spp.cel.variable
    Variable = env["spp.cel.variable"].sudo()  # nosemgrep: odoo-sudo-without-context
    variable = Variable.search([("name", "=", name)], limit=1)

    if variable and variable.default_value:
        try:
            # Try to parse as number
            return float(variable.default_value)
        except (ValueError, TypeError):
            return variable.default_value

    # Fallback to DEMO_CONSTANTS
    if name in DEMO_CONSTANTS:
        return DEMO_CONSTANTS[name]

    # Return provided default
    if default is not None:
        return default

    _logger.warning(f"[spp.mis.demo] Constant not found: {name}")
    return 0


def get_all_demo_constants(env: Environment) -> dict[str, Any]:
    """Get all demo constants as a dictionary.

    Args:
        env: Odoo environment

    Returns:
        Dictionary of all constant names and values
    """
    result = {}
    for name in DEMO_CONSTANTS:
        result[name] = get_demo_constant(env, name)
    return result


def ensure_demo_constants(env: Environment) -> None:
    """Ensure all demo constants exist as CEL variables.

    Creates any missing variables from DEMO_CONSTANTS.

    Args:
        env: Odoo environment
    """
    Variable = env["spp.cel.variable"].sudo()  # nosemgrep: odoo-sudo-without-context
    Category = env["spp.cel.variable.category"].sudo()  # nosemgrep: odoo-sudo-without-context

    # Get or create demo category
    demo_category = Category.search([("code", "=", "demo")], limit=1)
    if not demo_category:
        demo_category = Category.create(
            {
                "name": "Demo Constants",
                "code": "demo",
                "description": "Constants for MIS Demo V2",
            }
        )

    for name, value in DEMO_CONSTANTS.items():
        existing = Variable.search([("name", "=", name)], limit=1)
        if not existing:
            Variable.create(
                {
                    "name": name,
                    "display_name": name.replace("_", " ").title(),
                    "source_type": "constant",
                    "value_type": "number",
                    "default_value": str(value),
                    "category_id": demo_category.id,
                }
            )
            _logger.debug(f"[spp.mis.demo] Created constant: {name} = {value}")


# Logic Pack codes used by demo programs
DEMO_LOGIC_PACKS = [
    "social_pension",  # Elderly Pension program
    "disability_assistance",  # Disability Support Grant
    "child_benefit",  # Universal Child Grant
    "cash_transfer_basic",  # Cash Transfer Program
    "vulnerability_assessment",  # Emergency Relief Fund
]


def get_demo_pack_codes() -> list[str]:
    """Get list of Logic Pack codes used by demo programs.

    Returns:
        List of pack codes (e.g., ['social_pension', 'child_benefit', ...])
    """
    return DEMO_LOGIC_PACKS.copy()


def install_demo_packs(env: Environment) -> list:
    """Install Logic Packs used by demo programs.

    Args:
        env: Odoo environment

    Returns:
        List of installed pack records
    """
    Pack = env["spp.studio.pack"].sudo()  # nosemgrep: odoo-sudo-without-context
    installed = []

    for code in DEMO_LOGIC_PACKS:
        pack = Pack.search([("code", "=", code)], limit=1)
        if pack and pack.state == "available":
            try:
                pack.action_install()
                installed.append(pack)
                _logger.info(f"[spp.mis.demo] Installed Logic Pack: {code}")
            except Exception as e:
                _logger.warning(f"[spp.mis.demo] Failed to install pack {code}: {e}")

    return installed
