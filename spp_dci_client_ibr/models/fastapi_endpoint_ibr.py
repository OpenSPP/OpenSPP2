# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include IBR callback router."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppDCIClientIBREndpoint(models.Model):
    """Extend FastAPI endpoint for DCI IBR Client callback API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add IBR callback router to DCI API."""
        routers = super()._get_fastapi_routers()
        if self.app == "dci_api":
            from ..routers.callback import ibr_callback_router

            routers.append(ibr_callback_router)
        return routers
