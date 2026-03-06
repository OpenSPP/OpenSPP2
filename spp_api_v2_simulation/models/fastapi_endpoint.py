# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include simulation and aggregation routers."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppApiV2SimulationEndpoint(models.Model):
    """Extend FastAPI endpoint for Simulation and Aggregation API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add simulation and aggregation routers to API V2."""
        routers = super()._get_fastapi_routers()
        if self.app == "api_v2":
            from ..routers.aggregation import aggregation_router
            from ..routers.comparison import comparison_router
            from ..routers.run import run_router
            from ..routers.scenario import scenario_router
            from ..routers.simulation import simulation_router

            routers.extend(
                [
                    scenario_router,
                    run_router,
                    comparison_router,
                    simulation_router,
                    aggregation_router,
                ]
            )
        return routers
