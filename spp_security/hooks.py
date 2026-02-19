# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Post-installation hooks for spp_security module."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def post_init_hook(env_or_cr, registry=None):
    """
    Post-installation hook to set up group inheritance.

    This hook ensures that base.group_system (Odoo's System Admin)
    automatically implies spp_security.group_spp_admin (OpenSPP Admin).

    Using a hook is more reliable than XML data files for updating
    external records' Many2many fields.

    Supports both Odoo hook signatures:
    - post_init_hook(env) - Modern Odoo style
    - post_init_hook(cr, registry) - Legacy style
    """
    # Handle both Odoo hook signatures
    if registry is not None:
        # Legacy signature: (cr, registry)
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    else:
        # Modern signature: (env)
        env = env_or_cr

    _setup_admin_group_inheritance(env)


def _setup_admin_group_inheritance(env):
    """
    Configure Odoo system admin to inherit OpenSPP admin group.

    This creates the relationship: base.group_system -> spp_security.group_spp_admin

    When a user is assigned to base.group_system (Settings/Administration: Administration),
    they automatically get spp_security.group_spp_admin and all its implied groups.
    """
    try:
        system_admin = env.ref("base.group_system", raise_if_not_found=False)
        spp_admin = env.ref("spp_security.group_spp_admin", raise_if_not_found=False)

        if not system_admin or not spp_admin:
            _logger.warning(
                "Could not set up admin group inheritance: base.group_system or spp_security.group_spp_admin not found"
            )
            return

        # Check if relationship already exists
        if spp_admin in system_admin.implied_ids:
            _logger.debug("Admin group inheritance already configured")
            return

        # Add spp_admin to system_admin's implied_ids
        system_admin.write({"implied_ids": [(4, spp_admin.id)]})
        _logger.info("Configured admin group inheritance: base.group_system -> spp_security.group_spp_admin")

    except Exception as e:
        _logger.warning("Failed to set up admin group inheritance: %s", str(e))
