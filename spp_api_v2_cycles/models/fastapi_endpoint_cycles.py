# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include Cycles router."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppApiV2CyclesEndpoint(models.Model):
    """Extend FastAPI endpoint for Cycles API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add Cycles router to API V2."""
        routers = super()._get_fastapi_routers()
        if self.app == "api_v2":
            from ..routers.cycle import cycle_router

            routers.append(cycle_router)
        return routers
