# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include DR callback router."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppDCIClientDREndpoint(models.Model):
    """Extend FastAPI endpoint for DCI DR Client callback API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add DR callback router to DCI API."""
        routers = super()._get_fastapi_routers()
        if self.app == "dci_api":
            from ..routers.callback import dr_callback_router

            routers.append(dr_callback_router)
        return routers
