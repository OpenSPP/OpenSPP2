# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Statistics discovery API endpoint.

Delegates to the ProcessRegistry for statistics metadata,
keeping this endpoint as a convenience alias.
"""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, status

from ..schemas.statistics import (
    StatisticCategoryInfo,
    StatisticInfo,
    StatisticsListResponse,
)
from ..services.process_registry import ProcessRegistry

_logger = logging.getLogger(__name__)

statistics_router = APIRouter(tags=["GIS"], prefix="/gis")


@statistics_router.get(
    "/statistics",
    summary="List published GIS statistics",
    description="Returns all statistics published for GIS context, grouped by category.",
    response_model=StatisticsListResponse,
)
async def list_statistics(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> StatisticsListResponse:
    """List all GIS-published statistics grouped by category.

    Used by the QGIS plugin to discover what statistics are available
    for spatial queries and map visualization. Delegates to the
    ProcessRegistry for consistent metadata.
    """
    # Check read scope
    if not (api_client.has_scope("gis", "read") or api_client.has_scope("statistics", "read")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read or statistics:read scope",
        )

    try:
        registry = ProcessRegistry(env)
        _variable_names, categories_data = registry.get_statistics_metadata()

        categories = []
        total_count = 0

        for cat in categories_data:
            stat_items = [
                StatisticInfo(
                    name=s["name"],
                    label=s["label"],
                    description=s.get("description"),
                    format=s["format"],
                    unit=s.get("unit"),
                )
                for s in cat["statistics"]
            ]

            categories.append(
                StatisticCategoryInfo(
                    code=cat["code"],
                    name=cat["name"],
                    icon=cat.get("icon"),
                    statistics=stat_items,
                )
            )
            total_count += len(stat_items)

        return StatisticsListResponse(
            categories=categories,
            total_count=total_count,
        )

    except Exception:
        _logger.exception("Failed to list statistics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list statistics",
        ) from None
