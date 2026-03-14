# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend FastAPI endpoint to include GIS routers."""

import logging

from odoo import models

from fastapi import APIRouter

_logger = logging.getLogger(__name__)


class SppApiV2GisEndpoint(models.Model):
    """Extend FastAPI endpoint for GIS API."""

    _inherit = "fastapi.endpoint"

    def _get_fastapi_routers(self) -> list[APIRouter]:
        """Add GIS routers to API V2."""
        routers = super()._get_fastapi_routers()
        if self.app == "api_v2":
            from ..routers.export import export_router
            from ..routers.geofence import geofence_router
            from ..routers.jobs import jobs_router
            from ..routers.ogc_features import ogc_features_router
            from ..routers.processes import processes_router
            from ..routers.proximity import proximity_router
            from ..routers.spatial_query import spatial_query_router
            from ..routers.statistics import statistics_router

            routers.extend(
                [
                    ogc_features_router,
                    processes_router,
                    jobs_router,
                    export_router,
                    geofence_router,
                    proximity_router,
                    spatial_query_router,
                    statistics_router,
                ]
            )
        return routers
