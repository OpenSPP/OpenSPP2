# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Post-installation hook to configure enrollment program.

    Finds the first available program and sets it as the default
    enrollment program for the DCI demo.
    """
    _logger.info("Running spp_dci_demo post_init_hook")

    # Check if spp.program model exists
    if "spp.program" not in env:
        _logger.info("spp.program model not available, skipping enrollment program setup")
        return

    # Find the first program
    program = env["spp.program"].search([], limit=1)
    if not program:
        _logger.info("No programs found, enrollment_program_id not configured")
        return

    # Set the system parameter
    env["ir.config_parameter"].sudo().set_param(
        "spp_dci_demo.enrollment_program_id",
        str(program.id),
    )
    _logger.info(
        "Set spp_dci_demo.enrollment_program_id to %s (%s)",
        program.id,
        program.name,
    )
