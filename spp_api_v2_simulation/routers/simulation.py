# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Simulation template API endpoints."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, status

from ..schemas.simulation import TemplateListResponse
from ..services.simulation_api_service import SimulationApiService

_logger = logging.getLogger(__name__)

simulation_router = APIRouter(tags=["Simulation"], prefix="/simulation")


@simulation_router.get(
    "/templates",
    response_model=TemplateListResponse,
    summary="List scenario templates",
    description="Returns active pre-built scenario templates.",
)
async def list_templates(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """List active scenario templates.

    Requires:
        simulation:read scope
    """
    if not api_client.has_scope("simulation", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:read scope",
        )

    try:
        service = SimulationApiService(env)
        templates = service.list_templates()
        return {"templates": templates}

    except Exception as e:
        _logger.error("Failed to list templates: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list templates",
        ) from e
