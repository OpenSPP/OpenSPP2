# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Simulation comparison API endpoints."""

import logging
from typing import Annotated

from odoo import Command
from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, status

from ..schemas.comparison import (
    ComparisonCreateRequest,
    ComparisonResponse,
    ComparisonRunData,
    OverlapData,
)

_logger = logging.getLogger(__name__)

comparison_router = APIRouter(tags=["Simulation"], prefix="/simulation")


def _optional_str(value):
    """Convert Odoo False to None for optional string fields."""
    return value if value else None


def _comparison_to_response(comparison) -> ComparisonResponse:
    """Convert Odoo comparison record to Pydantic response."""
    # Extract run data from comparison_json
    runs_data = []
    if comparison.comparison_json:
        for run_data in comparison.comparison_json.get("runs", []):
            runs_data.append(
                ComparisonRunData(
                    run_id=run_data.get("run_id"),
                    scenario_name=run_data.get("scenario_name"),
                    beneficiary_count=run_data.get("beneficiary_count", 0),
                    total_cost=run_data.get("total_cost", 0.0),
                    coverage_rate=run_data.get("coverage_rate", 0.0),
                    equity_score=run_data.get("equity_score", 0.0),
                    gini_coefficient=run_data.get("gini_coefficient", 0.0),
                    has_disparity=run_data.get("has_disparity", False),
                    leakage_rate=run_data.get("leakage_rate", 0.0),
                    undercoverage_rate=run_data.get("undercoverage_rate", 0.0),
                    budget_utilization=run_data.get("budget_utilization", 0.0),
                    executed_at=run_data.get("executed_at") or None,
                )
            )

    # Extract overlap data from overlap_count_json
    overlap_list = []
    if comparison.overlap_count_json:
        for _key, overlap_data in comparison.overlap_count_json.items():
            overlap_list.append(
                OverlapData(
                    run_a_id=overlap_data.get("run_a_id"),
                    run_a_name=overlap_data.get("run_a_name"),
                    run_b_id=overlap_data.get("run_b_id"),
                    run_b_name=overlap_data.get("run_b_name"),
                    overlap_count=overlap_data.get("overlap_count", 0),
                    union_count=overlap_data.get("union_count", 0),
                    jaccard_index=overlap_data.get("jaccard_index", 0.0),
                )
            )

    return ComparisonResponse(
        id=comparison.id,
        name=comparison.name,
        runs=runs_data,
        overlap_data=overlap_list,
        staleness_warning=_optional_str(comparison.staleness_warning),
    )


@comparison_router.post(
    "/comparisons",
    summary="Create a comparison",
    description="Create a side-by-side comparison of multiple simulation runs",
    response_model=ComparisonResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comparison(
    request: ComparisonCreateRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> ComparisonResponse:
    """Create a comparison between runs."""
    # Check simulation:read scope (comparison is a read operation)
    if not api_client.has_scope("simulation", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:read scope",
        )

    try:
        # nosemgrep: odoo-sudo-without-context
        Comparison = env["spp.simulation.comparison"].sudo()
        # nosemgrep: odoo-sudo-without-context
        Run = env["spp.simulation.run"].sudo()

        # Validate runs exist
        runs = Run.browse(request.run_ids)
        if len(runs) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 2 runs are required for comparison",
            )

        # Check that all runs exist
        if not all(run.exists() for run in runs):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more runs not found",
            )

        # Create comparison
        comparison = Comparison.create(
            {
                "name": request.name,
                "run_ids": [Command.set(request.run_ids)],
            }
        )

        # Compute comparison data
        comparison.action_compute_comparison()

        return _comparison_to_response(comparison)

    except HTTPException:
        raise
    except Exception:
        _logger.exception("Failed to create comparison")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create comparison",
        ) from None


@comparison_router.get(
    "/comparisons/{comparison_id}",
    summary="Get a comparison",
    description="Returns detailed comparison data",
    response_model=ComparisonResponse,
)
async def get_comparison(
    comparison_id: int,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> ComparisonResponse:
    """Get comparison details."""
    # Check simulation:read scope
    if not api_client.has_scope("simulation", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:read scope",
        )

    try:
        # nosemgrep: odoo-sudo-without-context
        Comparison = env["spp.simulation.comparison"].sudo()
        comparison = Comparison.browse(comparison_id)

        if not comparison.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comparison {comparison_id} not found",
            )

        return _comparison_to_response(comparison)

    except HTTPException:
        raise
    except Exception:
        _logger.exception("Failed to get comparison")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get comparison",
        ) from None
