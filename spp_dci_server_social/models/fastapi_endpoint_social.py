# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include Social Registry DCI router."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppDCIServerSocialEndpoint(models.Model):
    """Extend FastAPI endpoint for DCI Social Registry API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add Social Registry routers to DCI API."""
        routers = super()._get_fastapi_routers()
        # Social Registry routers are now mounted via spp_dci_server's
        # fastapi_endpoint_dci.py under /social/registry/* prefix
        return routers
