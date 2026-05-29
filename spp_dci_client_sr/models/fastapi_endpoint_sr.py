# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include SR callback router."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppDCIClientSREndpoint(models.Model):
    """Extend FastAPI endpoint for DCI SR Client callback API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add SR callback router to DCI API."""
        routers = super()._get_fastapi_routers()
        if self.app == "dci_api":
            from ..routers.callback import sr_callback_router

            routers.append(sr_callback_router)
        return routers
