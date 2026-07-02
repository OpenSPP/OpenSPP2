# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Statistics discovery API endpoint."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, status

from ..schemas.statistics import (
    IndicatorCategoryInfo,
    IndicatorInfo,
    IndicatorsListResponse,
)

_logger = logging.getLogger(__name__)

statistics_router = APIRouter(tags=["GIS"], prefix="/gis")


@statistics_router.get(
    "/statistics",
    summary="List published GIS statistics",
    description="Returns all statistics published for GIS context, grouped by category.",
    response_model=IndicatorsListResponse,
)
async def list_statistics(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> IndicatorsListResponse:
    """List all GIS-published statistics grouped by category.

    Used by the QGIS plugin to discover what statistics are available
    for spatial queries and map visualization.
    """
    # Check read scope
    if not (api_client.has_scope("gis", "read") or api_client.has_scope("statistics", "read")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read or statistics:read scope",
        )

    try:
        # nosemgrep: odoo-sudo-without-context
        Statistic = env["spp.indicator"].sudo()
        stats_by_category = Statistic.get_published_by_category("gis")

        categories = []
        total_count = 0

        for category_code, stat_records in stats_by_category.items():
            # Get category metadata
            category_record = stat_records[0].category_id if stat_records else None

            stat_items = []
            for stat in stat_records:
                config = stat.get_context_config("gis")
                stat_items.append(
                    IndicatorInfo(
                        name=stat.name,
                        label=config.get("label", stat.label),
                        description=stat.description,
                        format=config.get("format", stat.format),
                        unit=stat.unit,
                    )
                )

            categories.append(
                IndicatorCategoryInfo(
                    code=category_code,
                    name=category_record.name if category_record else category_code.replace("_", " ").title(),
                    icon=getattr(category_record, "icon", None) if category_record else None,
                    statistics=stat_items,
                )
            )
            total_count += len(stat_items)

        return IndicatorsListResponse(
            categories=categories,
            total_count=total_count,
        )

    except Exception:
        _logger.exception("Failed to list statistics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list statistics",
        ) from None
