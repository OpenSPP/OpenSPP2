# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Simulation run API endpoints."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.run import (
    DistributionData,
    FairnessData,
    GeographicData,
    MetricResult,
    RunListResponse,
    RunResponse,
    RunSummary,
    ScenarioSnapshot,
    TargetingEfficiencyData,
)

_logger = logging.getLogger(__name__)

run_router = APIRouter(tags=["Simulation"], prefix="/simulation")


def _optional_str(value):
    """Convert Odoo False to None for optional string fields."""
    return value if value else None


def _datetime_to_iso(value):
    """Convert datetime to ISO 8601 string, or None if empty."""
    if not value:
        return None
    # Handle datetime objects
    if hasattr(value, "isoformat"):
        return value.isoformat()
    # Already a string
    return str(value)


def _run_to_summary(run) -> RunSummary:
    """Convert Odoo run record to Pydantic summary."""
    return RunSummary(
        id=run.id,
        scenario_id=run.scenario_id.id,
        scenario_name=run.scenario_id.name,
        state=run.state,
        beneficiary_count=run.beneficiary_count,
        total_cost=run.total_cost,
        coverage_rate=run.coverage_rate,
        equity_score=run.equity_score,
        gini_coefficient=run.gini_coefficient,
        executed_at=_datetime_to_iso(run.executed_at),
        execution_duration_seconds=run.execution_duration_seconds if run.execution_duration_seconds else None,
    )


def _run_to_response(run, include_details: bool = False) -> RunResponse:
    """Convert Odoo run record to Pydantic response."""
    response = RunResponse(
        id=run.id,
        scenario_id=run.scenario_id.id,
        scenario_name=run.scenario_id.name,
        state=run.state,
        beneficiary_count=run.beneficiary_count,
        total_cost=run.total_cost,
        coverage_rate=run.coverage_rate,
        equity_score=run.equity_score,
        gini_coefficient=run.gini_coefficient,
        total_registry_count=run.total_registry_count,
        budget_utilization=run.budget_utilization,
        has_disparity=run.has_disparity,
        leakage_rate=run.leakage_rate,
        undercoverage_rate=run.undercoverage_rate,
        executed_at=_datetime_to_iso(run.executed_at),
        execution_duration_seconds=run.execution_duration_seconds if run.execution_duration_seconds else None,
        error_message=_optional_str(run.error_message),
    )

    if include_details and run.state == "completed":
        # Add scenario snapshot
        if run.scenario_snapshot_json:
            snapshot_data = run.scenario_snapshot_json
            response.scenario_snapshot = ScenarioSnapshot(
                name=snapshot_data.get("name", ""),
                target_type=snapshot_data.get("target_type", ""),
                targeting_expression=snapshot_data.get("targeting_expression", ""),
                budget_amount=snapshot_data.get("budget_amount", 0.0),
                budget_strategy=snapshot_data.get("budget_strategy", ""),
                ideal_population_expression=snapshot_data.get("ideal_population_expression") or None,
                entitlement_rules=snapshot_data.get("entitlement_rules", []),
            )

        # Add distribution data
        if run.distribution_json:
            dist_data = run.distribution_json
            response.distribution_data = DistributionData(
                count=dist_data.get("count", 0),
                total=dist_data.get("total", 0.0),
                minimum=dist_data.get("minimum", 0.0),
                maximum=dist_data.get("maximum", 0.0),
                mean=dist_data.get("mean", 0.0),
                median=dist_data.get("median", 0.0),
                standard_deviation=dist_data.get("standard_deviation", 0.0),
                gini_coefficient=dist_data.get("gini_coefficient", 0.0),
                percentiles=dist_data.get("percentiles", {}),
            )

        # Add fairness data
        if run.fairness_json:
            fairness_data = run.fairness_json
            response.fairness_data = FairnessData(
                equity_score=fairness_data.get("equity_score", 100.0),
                has_disparity=fairness_data.get("has_disparity", False),
                demographic_breakdown=fairness_data.get("demographic_breakdown", {}),
            )

        # Add targeting efficiency data
        if run.targeting_efficiency_json and "error" not in run.targeting_efficiency_json:
            eff_data = run.targeting_efficiency_json
            response.targeting_efficiency_data = TargetingEfficiencyData(
                true_positives=eff_data.get("true_positives", 0),
                false_positives=eff_data.get("false_positives", 0),
                false_negatives=eff_data.get("false_negatives", 0),
                total_simulated=eff_data.get("total_simulated", 0),
                total_ideal=eff_data.get("total_ideal", 0),
                leakage_rate=eff_data.get("leakage_rate", 0.0),
                undercoverage_rate=eff_data.get("undercoverage_rate", 0.0),
            )

        # Add geographic data
        if run.geographic_json:
            response.geographic_data = GeographicData(areas=run.geographic_json)

        # Add metric results
        if run.metric_results_json:
            metrics = {}
            for metric_name, metric_data in run.metric_results_json.items():
                metrics[metric_name] = MetricResult(
                    type=metric_data.get("type", "unknown"),
                    value=metric_data.get("value", 0),
                )
            response.metric_results = metrics

    return response


@run_router.get(
    "/runs",
    summary="List simulation runs",
    description="Returns all simulation runs with optional filters",
    response_model=RunListResponse,
)
async def list_runs(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    scenario_id: int | None = Query(default=None, description="Filter by scenario ID"),
    state: str | None = Query(default=None, description="Filter by state (running, completed, failed)"),
    limit: int = Query(default=100, le=500, description="Maximum number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
) -> RunListResponse:
    """List all runs with optional filters."""
    # Check simulation:read scope
    if not api_client.has_scope("simulation", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:read scope",
        )

    try:
        Run = env["spp.simulation.run"].sudo()

        # Build domain
        domain = []
        if scenario_id:
            domain.append(("scenario_id", "=", scenario_id))
        if state:
            domain.append(("state", "=", state))

        # Query runs
        total_count = Run.search_count(domain)
        runs = Run.search(domain, limit=limit, offset=offset, order="executed_at desc")

        # Convert to responses
        run_summaries = [_run_to_summary(run) for run in runs]

        return RunListResponse(
            runs=run_summaries,
            total_count=total_count,
        )

    except Exception:
        _logger.exception("Failed to list runs")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list runs",
        ) from None


@run_router.get(
    "/runs/{run_id}",
    summary="Get a simulation run",
    description="Returns detailed information about a specific run",
    response_model=RunResponse,
)
async def get_run(
    run_id: int,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    include_details: bool = Query(default=False, description="Include detailed distribution, fairness, etc."),
) -> RunResponse:
    """Get run details."""
    # Check simulation:read scope
    if not api_client.has_scope("simulation", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:read scope",
        )

    try:
        Run = env["spp.simulation.run"].sudo()
        run = Run.browse(run_id)

        if not run.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {run_id} not found",
            )

        return _run_to_response(run, include_details=include_details)

    except HTTPException:
        raise
    except Exception:
        _logger.exception("Failed to get run")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get run",
        ) from None
