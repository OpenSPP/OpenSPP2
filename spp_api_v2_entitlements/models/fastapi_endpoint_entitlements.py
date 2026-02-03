# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include Entitlements router."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppApiV2EntitlementsEndpoint(models.Model):
    """Extend FastAPI endpoint for Entitlements API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add Entitlements router to API V2."""
        routers = super()._get_fastapi_routers()
        if self.app == "api_v2":
            from ..routers.entitlement import entitlement_router

            routers.append(entitlement_router)
        return routers
