# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Simulation scenario API endpoints."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.run import RunSimulationResponse
from ..schemas.scenario import (
    ConvertToProgramRequest,
    ConvertToProgramResponse,
    ScenarioCreateRequest,
    ScenarioListResponse,
    ScenarioResponse,
    ScenarioUpdateRequest,
)

_logger = logging.getLogger(__name__)

scenario_router = APIRouter(tags=["Simulation"], prefix="/simulation")


def _optional_str(value):
    """Convert Odoo False to None for optional string fields."""
    return value if value else None


def _scenario_to_response(scenario) -> ScenarioResponse:
    """Convert Odoo scenario record to Pydantic response."""
    from ..schemas.scenario import EntitlementRuleResponse

    rules = []
    for rule in scenario.entitlement_rule_ids:
        rules.append(
            EntitlementRuleResponse(
                id=rule.id,
                amount_mode=rule.amount_mode,
                amount=rule.amount,
                multiplier_field=_optional_str(rule.multiplier_field),
                max_multiplier=rule.max_multiplier if rule.max_multiplier else None,
                amount_cel_expression=_optional_str(rule.amount_cel_expression),
                condition_cel_expression=_optional_str(rule.condition_cel_expression),
            )
        )

    return ScenarioResponse(
        id=scenario.id,
        name=scenario.name,
        description=_optional_str(scenario.description),
        category=_optional_str(scenario.category),
        target_type=scenario.target_type,
        targeting_expression=_optional_str(scenario.targeting_expression),
        targeting_expression_explanation=_optional_str(scenario.targeting_expression_explanation),
        budget_amount=scenario.budget_amount,
        budget_strategy=scenario.budget_strategy,
        ideal_population_expression=_optional_str(scenario.ideal_population_expression),
        state=scenario.state,
        targeting_preview_count=scenario.targeting_preview_count,
        targeting_preview_error=_optional_str(scenario.targeting_preview_error),
        run_count=scenario.run_count,
        latest_beneficiary_count=scenario.latest_beneficiary_count,
        latest_equity_score=scenario.latest_equity_score,
        entitlement_rules=rules,
        program_id=scenario.program_id.id if scenario.program_id else None,
    )


@scenario_router.get(
    "/scenarios",
    summary="List simulation scenarios",
    description="Returns all simulation scenarios with optional filters",
    response_model=ScenarioListResponse,
)
async def list_scenarios(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    state: str | None = Query(default=None, description="Filter by state (draft, ready, archived)"),
    category: str | None = Query(default=None, description="Filter by category"),
    limit: int = Query(default=100, le=500, description="Maximum number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
) -> ScenarioListResponse:
    """List all scenarios with optional filters."""
    # Check simulation:read scope
    if not api_client.has_scope("simulation", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:read scope",
        )

    try:
        Scenario = env["spp.simulation.scenario"].sudo()

        # Build domain
        domain = []
        if state:
            domain.append(("state", "=", state))
        if category:
            domain.append(("category", "=", category))

        # Query scenarios
        total_count = Scenario.search_count(domain)
        scenarios = Scenario.search(domain, limit=limit, offset=offset, order="write_date desc")

        # Convert to responses
        scenario_responses = [_scenario_to_response(scenario) for scenario in scenarios]

        return ScenarioListResponse(
            scenarios=scenario_responses,
            total_count=total_count,
        )

    except Exception as e:
        _logger.exception("Failed to list scenarios")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scenarios: {str(e)}",
        ) from None


@scenario_router.post(
    "/scenarios",
    summary="Create a simulation scenario",
    description="Create a new simulation scenario with entitlement rules",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    request: ScenarioCreateRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> ScenarioResponse:
    """Create a new scenario."""
    # Check simulation:write scope
    if not api_client.has_scope("simulation", "write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:write scope",
        )

    try:
        Scenario = env["spp.simulation.scenario"].sudo()

        # Build scenario values
        vals = {
            "name": request.name,
            "description": request.description,
            "category": request.category,
            "target_type": request.target_type,
            "targeting_expression": request.targeting_expression,
            "targeting_expression_explanation": request.targeting_expression_explanation,
            "budget_amount": request.budget_amount,
            "budget_strategy": request.budget_strategy,
            "ideal_population_expression": request.ideal_population_expression,
        }

        if request.program_id:
            vals["program_id"] = request.program_id

        # Create scenario
        scenario = Scenario.create(vals)

        # Create entitlement rules
        EntitlementRule = env["spp.simulation.entitlement.rule"].sudo()
        for rule_data in request.entitlement_rules:
            EntitlementRule.create(
                {
                    "scenario_id": scenario.id,
                    "amount_mode": rule_data.amount_mode,
                    "amount": rule_data.amount,
                    "multiplier_field": rule_data.multiplier_field,
                    "max_multiplier": rule_data.max_multiplier,
                    "amount_cel_expression": rule_data.amount_cel_expression,
                    "condition_cel_expression": rule_data.condition_cel_expression,
                }
            )

        # Refresh to get computed fields
        scenario.invalidate_recordset()

        return _scenario_to_response(scenario)

    except Exception as e:
        _logger.exception("Failed to create scenario")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create scenario: {str(e)}",
        ) from None


@scenario_router.get(
    "/scenarios/{scenario_id}",
    summary="Get a simulation scenario",
    description="Returns detailed information about a specific scenario",
    response_model=ScenarioResponse,
)
async def get_scenario(
    scenario_id: int,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> ScenarioResponse:
    """Get scenario details."""
    # Check simulation:read scope
    if not api_client.has_scope("simulation", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:read scope",
        )

    try:
        Scenario = env["spp.simulation.scenario"].sudo()
        scenario = Scenario.browse(scenario_id)

        if not scenario.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        return _scenario_to_response(scenario)

    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Failed to get scenario")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scenario: {str(e)}",
        ) from None


@scenario_router.put(
    "/scenarios/{scenario_id}",
    summary="Update a simulation scenario",
    description="Update an existing scenario (only allowed in draft state)",
    response_model=ScenarioResponse,
)
async def update_scenario(
    scenario_id: int,
    request: ScenarioUpdateRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> ScenarioResponse:
    """Update a scenario."""
    # Check simulation:write scope
    if not api_client.has_scope("simulation", "write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:write scope",
        )

    try:
        Scenario = env["spp.simulation.scenario"].sudo()
        scenario = Scenario.browse(scenario_id)

        if not scenario.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        if scenario.state != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft scenarios can be updated",
            )

        # Build update values
        vals = {}
        if request.name is not None:
            vals["name"] = request.name
        if request.description is not None:
            vals["description"] = request.description
        if request.category is not None:
            vals["category"] = request.category
        if request.targeting_expression is not None:
            vals["targeting_expression"] = request.targeting_expression
        if request.targeting_expression_explanation is not None:
            vals["targeting_expression_explanation"] = request.targeting_expression_explanation
        if request.budget_amount is not None:
            vals["budget_amount"] = request.budget_amount
        if request.budget_strategy is not None:
            vals["budget_strategy"] = request.budget_strategy
        if request.ideal_population_expression is not None:
            vals["ideal_population_expression"] = request.ideal_population_expression

        # Update scenario
        if vals:
            scenario.write(vals)

        # Refresh to get computed fields
        scenario.invalidate_recordset()

        return _scenario_to_response(scenario)

    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Failed to update scenario")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update scenario: {str(e)}",
        ) from None


@scenario_router.delete(
    "/scenarios/{scenario_id}",
    summary="Archive a simulation scenario",
    description="Archive a scenario (soft delete)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_scenario(
    scenario_id: int,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> None:
    """Archive a scenario."""
    # Check simulation:write scope
    if not api_client.has_scope("simulation", "write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:write scope",
        )

    try:
        Scenario = env["spp.simulation.scenario"].sudo()
        scenario = Scenario.browse(scenario_id)

        if not scenario.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        scenario.action_archive()

    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Failed to archive scenario")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive scenario: {str(e)}",
        ) from None


@scenario_router.post(
    "/scenarios/{scenario_id}/ready",
    summary="Mark scenario as ready",
    description="Transition scenario from draft to ready state",
    response_model=ScenarioResponse,
)
async def mark_scenario_ready(
    scenario_id: int,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> ScenarioResponse:
    """Mark scenario as ready."""
    # Check simulation:write scope
    if not api_client.has_scope("simulation", "write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:write scope",
        )

    try:
        Scenario = env["spp.simulation.scenario"].sudo()
        scenario = Scenario.browse(scenario_id)

        if not scenario.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        try:
            scenario.action_set_ready()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from None

        # Refresh to get updated state
        scenario.invalidate_recordset()

        return _scenario_to_response(scenario)

    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Failed to mark scenario as ready")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark scenario as ready: {str(e)}",
        ) from None


@scenario_router.post(
    "/scenarios/{scenario_id}/run",
    summary="Run a simulation",
    description="Execute the simulation for this scenario",
    response_model=RunSimulationResponse,
)
async def run_simulation(
    scenario_id: int,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> RunSimulationResponse:
    """Run a simulation."""
    # Check simulation:execute scope (special scope for running)
    if not api_client.has_scope("simulation", "execute"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:execute scope",
        )

    try:
        Scenario = env["spp.simulation.scenario"].sudo()
        scenario = Scenario.browse(scenario_id)

        if not scenario.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        if scenario.state != "ready":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only scenarios in 'ready' state can be run",
            )

        # Execute simulation via service
        service = env["spp.simulation.service"]
        run = service.execute_simulation(scenario)

        return RunSimulationResponse(
            run_id=run.id,
            scenario_id=scenario.id,
            state=run.state,
            message=f"Simulation completed with {run.beneficiary_count} beneficiaries"
            if run.state == "completed"
            else run.error_message or "Simulation failed",
        )

    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Failed to run simulation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run simulation: {str(e)}",
        ) from None


@scenario_router.post(
    "/scenarios/{scenario_id}/convert-to-program",
    summary="Convert scenario to program",
    description="Convert a ready simulation scenario into a real program with "
    "CEL eligibility and cash entitlement managers.",
    response_model=ConvertToProgramResponse,
    status_code=status.HTTP_201_CREATED,
)
async def convert_to_program(
    scenario_id: int,
    request: ConvertToProgramRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> ConvertToProgramResponse:
    """Convert a simulation scenario to a program."""
    # Check simulation:write scope
    if not api_client.has_scope("simulation", "write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:write scope",
        )

    # Check simulation:convert scope
    if not api_client.has_scope("simulation", "convert"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have simulation:convert scope",
        )

    try:
        Scenario = env["spp.simulation.scenario"].sudo()
        scenario = Scenario.browse(scenario_id)

        if not scenario.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        if scenario.state != "ready":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only scenarios in 'ready' state can be converted",
            )

        if scenario.converted_program_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Scenario already converted to program '{scenario.converted_program_id.name}'",
            )

        if not scenario.entitlement_rule_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scenario must have at least one entitlement rule",
            )

        # Build options from request
        options = _build_convert_options(request)

        # Validate currency code if provided
        if request.currency_code:
            currency = env["res.currency"].sudo().search([("name", "=", request.currency_code)], limit=1)
            if not currency:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Currency code '{request.currency_code}' not found",
                )

        # Check for duplicate program name
        program_name = request.name or scenario.name
        existing = env["spp.program"].sudo().search([("name", "=", program_name)], limit=1)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A program with this name already exists",
            )

        # Execute conversion via service
        service = env["spp.simulation.service"].sudo()
        result = service.convert_to_program(scenario, options)
        program = result["program"]
        warnings = [str(w) for w in result.get("warnings", [])]

        return ConvertToProgramResponse(
            program_id=program.id,
            program_name=program.name,
            scenario_id=scenario.id,
            warnings=warnings,
        )

    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Failed to convert scenario to program")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert scenario to program: {str(e)}",
        ) from None


def _build_convert_options(request: ConvertToProgramRequest) -> dict:
    """Build service options dict from request schema."""
    options = {}
    if request.name:
        options["name"] = request.name
    if request.currency_code:
        options["currency_code"] = request.currency_code
    if request.is_one_time_distribution:
        options["is_one_time_distribution"] = True
    if request.import_beneficiaries:
        options["import_beneficiaries"] = True
    if request.rrule_type:
        options["rrule_type"] = request.rrule_type
    if request.cycle_duration is not None:
        options["cycle_duration"] = request.cycle_duration
    if request.day is not None:
        options["day"] = request.day
    if request.month_by:
        options["month_by"] = request.month_by
    if request.weekday:
        options["weekday"] = request.weekday
    if request.byday:
        options["byday"] = request.byday

    # Weekly day flags
    for day_field in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        if getattr(request, day_field, False):
            options[day_field] = True

    return options
