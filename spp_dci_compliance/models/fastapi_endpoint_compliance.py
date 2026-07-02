# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint for DCI compliance testing.

SECURITY NOTE: The compliance testing endpoints are only enabled when:
1. Odoo is running in test mode (--test-enable), OR
2. System parameter 'dci.enable_compliance_endpoints' is set to 'true'

This prevents accidental exposure of test endpoints in production.
"""

import logging

from odoo import models, tools

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class FastAPIEndpointCompliance(models.Model):
    """Extend DCI API with compliance testing endpoints.

    The compliance testing endpoints (/test/*) provide functionality for
    verifying DCI callbacks during compliance testing. These endpoints are
    protected and only available in test environments or when explicitly enabled.
    """

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add compliance verification router when app is dci_api.

        The compliance router is only added when:
        - Running in test mode (tools.config.get('test_enable')), OR
        - System parameter 'dci.enable_compliance_endpoints' is 'true'

        This provides security by default while allowing compliance testing
        when needed.
        """
        routers = super()._get_fastapi_routers()

        if self.app == "dci_api":
            # Check if compliance endpoints should be enabled
            is_test_mode = tools.config.get("test_enable", False)
            config = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
            enable_param = config.get_param("dci.enable_compliance_endpoints", "false").lower() == "true"

            if is_test_mode or enable_param:
                from ..routers.verification import verification_router

                routers.append(verification_router)
                _logger.debug(
                    "DCI compliance endpoints enabled (test_mode=%s, param=%s)",
                    is_test_mode,
                    enable_param,
                )
            else:
                _logger.debug(
                    "DCI compliance endpoints disabled in production. "
                    "Set 'dci.enable_compliance_endpoints' to 'true' to enable."
                )

        return routers
