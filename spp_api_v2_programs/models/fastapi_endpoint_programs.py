# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Register the Program and ProgramMembership routers on the API V2 app."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppApiV2ProgramsEndpoint(models.Model):
    """Extend the API V2 FastAPI endpoint with program routers."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add Program / ProgramMembership routers to API V2."""
        routers = super()._get_fastapi_routers()
        if self.app == "api_v2":
            from ..routers.program import program_router
            from ..routers.program_filters import (
                program_filter_router,
                program_membership_filter_router,
            )
            from ..routers.program_membership import program_membership_router

            routers.extend(
                [
                    program_router,
                    program_filter_router,
                    program_membership_router,
                    program_membership_filter_router,
                ]
            )
        return routers
