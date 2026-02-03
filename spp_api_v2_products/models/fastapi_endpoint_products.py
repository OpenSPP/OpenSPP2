# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include Products routers."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppApiV2ProductsEndpoint(models.Model):
    """Extend FastAPI endpoint for Products API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add Products routers to API V2."""
        routers = super()._get_fastapi_routers()
        if self.app == "api_v2":
            from ..routers.product import product_router
            from ..routers.product_category import product_category_router
            from ..routers.uom import uom_router

            routers.extend(
                [
                    product_router,
                    product_category_router,
                    uom_router,
                ]
            )
        return routers
