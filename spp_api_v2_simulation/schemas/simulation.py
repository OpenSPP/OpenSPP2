# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for Simulation API."""

from pydantic import BaseModel, Field

# --- Entitlement Rule Schemas ---


class EntitlementRuleRequest(BaseModel):
    """Entitlement rule definition for scenario creation/update."""

    name: str | None = Field(default=None, description="Rule name")
    sequence: int = Field(default=10, description="Rule evaluation order")
    amount_mode: str = Field(
        default="fixed",
        description="Amount mode: 'fixed', 'multiplier', or 'cel'",
    )
    amount: float = Field(default=0.0, description="Fixed amount per beneficiary")
    multiplier_field: str | None = Field(
        default=None,
        description="Field name to multiply (for multiplier mode)",
    )
    max_multiplier: float = Field(
        default=0.0,
        description="Maximum multiplier cap (0 = no limit)",
    )
    amount_cel_expression: str | None = Field(
        default=None,
        description="CEL expression returning amount (for cel mode)",
    )
    condition_cel_expression: str | None = Field(
        default=None,
        description="Optional CEL sub-filter within targeted population",
    )


class EntitlementRuleResponse(BaseModel):
    """Entitlement rule in API responses."""

    id: int = Field(..., description="Rule ID")
    name: str | None = Field(default=None, description="Rule name")
    sequence: int = Field(..., description="Rule evaluation order")
    amount_mode: str = Field(..., description="Amount mode")
    amount: float = Field(..., description="Fixed amount")
    multiplier_field: str | None = Field(default=None, description="Multiplier field")
    max_multiplier: float = Field(..., description="Max multiplier cap")
    amount_cel_expression: str | None = Field(default=None, description="CEL amount expression")
    condition_cel_expression: str | None = Field(default=None, description="CEL condition expression")


# --- Template Schemas ---


class TemplateResponse(BaseModel):
    """Simulation scenario template."""

    id: int = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    description: str | None = Field(default=None, description="Template description")
    category: str = Field(..., description="Template category")
    target_type: str = Field(..., description="Target type: 'group' or 'individual'")
    targeting_expression: str = Field(..., description="CEL targeting expression")
    default_amount: float = Field(..., description="Default entitlement amount")
    default_amount_mode: str = Field(..., description="Default amount mode")
    icon: str = Field(..., description="FontAwesome icon class")


class TemplateListResponse(BaseModel):
    """Response from GET /simulation/templates."""

    templates: list[TemplateResponse] = Field(..., description="Active scenario templates")


# --- Scenario Schemas ---


class CreateScenarioRequest(BaseModel):
    """Request body for POST /simulation/scenarios."""

    name: str = Field(..., description="Scenario name")
    description: str | None = Field(default=None, description="Scenario description")
    category: str | None = Field(default=None, description="Scenario category")
    template_id: int | None = Field(
        default=None,
        description="Template ID to create from (overrides manual fields)",
    )
    target_type: str = Field(default="group", description="Target type: 'group' or 'individual'")
    targeting_expression: str | None = Field(
        default=None,
        description="CEL targeting expression (required if no template_id)",
    )
    budget_amount: float = Field(default=0.0, description="Total budget amount")
    budget_strategy: str = Field(
        default="none",
        description="Budget strategy: 'none', 'cap_total', or 'proportional_reduction'",
    )
    ideal_population_expression: str | None = Field(
        default=None,
        description="CEL expression for ideal population (leakage/undercoverage measurement)",
    )
    entitlement_rules: list[EntitlementRuleRequest] | None = Field(
        default=None,
        description="Entitlement rules (ignored if template_id is provided)",
    )


class UpdateScenarioRequest(BaseModel):
    """Request body for PATCH /simulation/scenarios/{id}."""

    name: str | None = Field(default=None, description="Updated scenario name")
    description: str | None = Field(default=None, description="Updated description")
    category: str | None = Field(default=None, description="Updated category")
    targeting_expression: str | None = Field(default=None, description="Updated CEL expression")
    budget_amount: float | None = Field(default=None, description="Updated budget amount")
    budget_strategy: str | None = Field(default=None, description="Updated budget strategy")
    ideal_population_expression: str | None = Field(
        default=None,
        description="Updated ideal population expression",
    )
    entitlement_rules: list[EntitlementRuleRequest] | None = Field(
        default=None,
        description="Replacement entitlement rules (replaces all existing rules)",
    )


class ScenarioResponse(BaseModel):
    """Simulation scenario in API responses."""

    id: int = Field(..., description="Scenario ID")
    name: str = Field(..., description="Scenario name")
    description: str | None = Field(default=None, description="Scenario description")
    category: str | None = Field(default=None, description="Scenario category")
    template_id: int | None = Field(default=None, description="Source template ID")
    target_type: str = Field(..., description="Target type")
    targeting_expression: str | None = Field(default=None, description="CEL targeting expression")
    budget_amount: float = Field(..., description="Budget amount")
    budget_strategy: str = Field(..., description="Budget strategy")
    ideal_population_expression: str | None = Field(default=None, description="Ideal population expression")
    state: str = Field(..., description="Scenario state: 'draft', 'ready', or 'archived'")
    targeting_preview_count: int = Field(..., description="Live count of matching registrants")
    entitlement_rules: list[EntitlementRuleResponse] = Field(
        default_factory=list,
        description="Entitlement rules",
    )
    run_count: int = Field(default=0, description="Number of simulation runs")


class ScenarioListResponse(BaseModel):
    """Response from GET /simulation/scenarios."""

    scenarios: list[ScenarioResponse] = Field(..., description="Matching scenarios")


# --- Run Schemas ---


class RunHeadlineResponse(BaseModel):
    """Headline metrics from a simulation run (returned after execution)."""

    id: int = Field(..., description="Run ID")
    scenario_id: int = Field(..., description="Parent scenario ID")
    scenario_name: str = Field(..., description="Scenario name at time of run")
    state: str = Field(..., description="Run state: 'running', 'completed', or 'failed'")
    beneficiary_count: int = Field(..., description="Number of beneficiaries targeted")
    total_registry_count: int = Field(..., description="Total registry population")
    coverage_rate: float = Field(..., description="Coverage rate as percentage")
    total_cost: float = Field(..., description="Total entitlement cost")
    budget_utilization: float = Field(..., description="Budget utilization percentage")
    gini_coefficient: float = Field(..., description="Gini coefficient (0=equal, 1=max inequality)")
    equity_score: float = Field(..., description="Equity score 0-100")
    has_disparity: bool = Field(..., description="Whether significant disparity was detected")
    executed_at: str | None = Field(default=None, description="Execution timestamp (ISO 8601)")
    execution_duration_seconds: float = Field(default=0.0, description="Execution duration in seconds")
    error_message: str | None = Field(default=None, description="Error message if failed")


class RunDetailResponse(RunHeadlineResponse):
    """Full detail of a simulation run including JSON breakdowns."""

    leakage_rate: float = Field(default=0.0, description="Leakage rate percentage")
    undercoverage_rate: float = Field(default=0.0, description="Undercoverage rate percentage")
    distribution_json: dict | None = Field(
        default=None,
        description="Distribution statistics (min, max, mean, median, percentiles)",
    )
    fairness_json: dict | None = Field(
        default=None,
        description="Fairness analysis data",
    )
    targeting_efficiency_json: dict | None = Field(
        default=None,
        description="Targeting efficiency (true/false positives/negatives)",
    )
    geographic_json: dict | None = Field(
        default=None,
        description="Geographic breakdown by area",
    )
    metric_results_json: dict | None = Field(
        default=None,
        description="Custom metric results",
    )
    scenario_snapshot_json: dict | None = Field(
        default=None,
        description="Scenario parameters at time of execution",
    )


# --- Comparison Schemas ---


class CompareRunsRequest(BaseModel):
    """Request body for POST /simulation/runs/compare."""

    run_ids: list[int] = Field(
        ...,
        min_length=2,
        description="List of run IDs to compare (minimum 2)",
    )
    name: str | None = Field(
        default=None,
        description="Comparison name (auto-generated if not provided)",
    )


class ComparisonRunMetrics(BaseModel):
    """Metrics for a single run within a comparison."""

    run_id: int = Field(..., description="Run ID")
    scenario_name: str = Field(..., description="Scenario name")
    beneficiary_count: int = Field(..., description="Number of beneficiaries")
    total_cost: float = Field(..., description="Total cost")
    coverage_rate: float = Field(..., description="Coverage rate percentage")
    equity_score: float = Field(..., description="Equity score 0-100")
    gini_coefficient: float = Field(..., description="Gini coefficient")
    has_disparity: bool = Field(..., description="Disparity detected")
    leakage_rate: float = Field(default=0.0, description="Leakage rate")
    undercoverage_rate: float = Field(default=0.0, description="Undercoverage rate")
    budget_utilization: float = Field(default=0.0, description="Budget utilization")
    executed_at: str | None = Field(default=None, description="Execution timestamp")


class ComparisonOverlap(BaseModel):
    """Overlap analysis between two runs."""

    run_a_id: int = Field(..., description="First run ID")
    run_a_name: str = Field(..., description="First run scenario name")
    run_b_id: int = Field(..., description="Second run ID")
    run_b_name: str = Field(..., description="Second run scenario name")
    overlap_count: int = Field(..., description="Number of shared beneficiaries")
    union_count: int = Field(..., description="Total unique beneficiaries across both")
    jaccard_index: float = Field(..., description="Jaccard similarity index (0-1)")


class ComparisonResponse(BaseModel):
    """Response from POST /simulation/runs/compare."""

    id: int = Field(..., description="Comparison ID")
    name: str = Field(..., description="Comparison name")
    runs: list[ComparisonRunMetrics] = Field(..., description="Per-run metrics")
    overlap: list[ComparisonOverlap] = Field(
        default_factory=list,
        description="Pairwise overlap analysis",
    )
    staleness_warning: str | None = Field(
        default=None,
        description="Warning if runs were executed far apart",
    )
