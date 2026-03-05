# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for simulation runs."""

from pydantic import BaseModel, Field


class DistributionData(BaseModel):
    """Distribution analysis data for entitlements."""

    count: int = Field(..., description="Number of beneficiaries")
    total: float = Field(..., description="Total amount distributed")
    minimum: float = Field(..., description="Minimum entitlement amount")
    maximum: float = Field(..., description="Maximum entitlement amount")
    mean: float = Field(..., description="Mean entitlement amount")
    median: float = Field(..., description="Median entitlement amount")
    standard_deviation: float = Field(..., description="Standard deviation")
    gini_coefficient: float = Field(..., description="Gini coefficient")
    percentiles: dict = Field(..., description="Percentile values (p25, p50, p75, etc.)")


class FairnessData(BaseModel):
    """Fairness metrics by demographic groups."""

    equity_score: float = Field(..., description="Overall equity score")
    has_disparity: bool = Field(..., description="Whether significant disparity was detected")
    demographic_breakdown: dict = Field(..., description="Breakdown by demographic groups")


class GeographicData(BaseModel):
    """Geographic distribution data."""

    areas: dict = Field(..., description="Area-level statistics keyed by area name")


class MetricResult(BaseModel):
    """Result of a custom metric calculation."""

    type: str = Field(..., description="Metric type (count, sum, average, etc.)")
    value: float | int = Field(..., description="Metric value")


class TargetingEfficiencyData(BaseModel):
    """Targeting efficiency metrics (requires ideal population)."""

    true_positives: int = Field(..., description="Beneficiaries in ideal population")
    false_positives: int = Field(..., description="Beneficiaries outside ideal population")
    false_negatives: int = Field(..., description="Ideal population not covered")
    total_simulated: int = Field(..., description="Total simulated beneficiaries")
    total_ideal: int = Field(..., description="Total ideal population")
    leakage_rate: float = Field(..., description="Leakage rate (false positives / total simulated)")
    undercoverage_rate: float = Field(..., description="Undercoverage rate (false negatives / total ideal)")


class ScenarioSnapshot(BaseModel):
    """Snapshot of scenario configuration at time of run."""

    name: str = Field(..., description="Scenario name")
    target_type: str = Field(..., description="Target type (group/individual)")
    targeting_expression: str = Field(..., description="Targeting CEL expression")
    budget_amount: float = Field(..., description="Budget amount")
    budget_strategy: str = Field(..., description="Budget strategy")
    ideal_population_expression: str | None = Field(default=None, description="Ideal population CEL expression")
    entitlement_rules: list[dict] = Field(..., description="Entitlement rules")


class RunSummary(BaseModel):
    """Summary data for a simulation run (list view)."""

    id: int = Field(..., description="Run ID")
    scenario_id: int = Field(..., description="Scenario ID")
    scenario_name: str = Field(..., description="Scenario name")
    state: str = Field(..., description="Run state")
    beneficiary_count: int = Field(..., description="Number of beneficiaries")
    total_cost: float = Field(..., description="Total cost")
    coverage_rate: float = Field(..., description="Coverage rate")
    equity_score: float = Field(..., description="Equity score")
    gini_coefficient: float = Field(..., description="Gini coefficient")
    executed_at: str | None = Field(default=None, description="Execution timestamp")
    execution_duration_seconds: float | None = Field(default=None, description="Execution duration in seconds")


class RunResponse(BaseModel):
    """Simulation run details."""

    id: int = Field(..., description="Run ID")
    scenario_id: int = Field(..., description="Scenario ID")
    scenario_name: str = Field(..., description="Scenario name")
    state: str = Field(..., description="Run state: 'pending', 'running', 'completed', 'failed'")
    executed_at: str | None = Field(default=None, description="Execution timestamp (ISO 8601)")
    execution_duration_seconds: float | None = Field(default=None, description="Execution duration in seconds")
    # Headline metrics
    beneficiary_count: int = Field(..., description="Number of beneficiaries selected")
    total_registry_count: int = Field(..., description="Total number of registrants in registry")
    coverage_rate: float = Field(..., description="Coverage rate (beneficiaries / total registry)")
    total_cost: float = Field(..., description="Total cost of entitlements")
    budget_utilization: float = Field(..., description="Budget utilization rate (total cost / budget)")
    gini_coefficient: float = Field(..., description="Gini coefficient measuring inequality")
    equity_score: float = Field(..., description="Equity score (1 - Gini coefficient)")
    has_disparity: bool = Field(..., description="Whether significant disparity was detected")
    leakage_rate: float = Field(..., description="Leakage rate (beneficiaries outside ideal population)")
    undercoverage_rate: float = Field(..., description="Undercoverage rate (ideal population not covered)")
    error_message: str | None = Field(default=None, description="Error message if run failed")
    # Optional detailed data
    distribution_data: DistributionData | None = Field(default=None, description="Distribution analysis data")
    fairness_data: FairnessData | None = Field(default=None, description="Fairness metrics by demographic group")
    geographic_data: GeographicData | None = Field(default=None, description="Geographic distribution data")
    targeting_efficiency_data: TargetingEfficiencyData | None = Field(
        default=None, description="Targeting efficiency metrics"
    )
    metric_results: dict[str, MetricResult] | None = Field(
        default=None, description="Detailed metric calculation results"
    )
    scenario_snapshot: ScenarioSnapshot | None = Field(
        default=None, description="Snapshot of scenario configuration at time of run"
    )


class RunListResponse(BaseModel):
    """List of simulation runs."""

    runs: list[RunSummary] = Field(..., description="List of runs")
    total_count: int = Field(..., description="Total number of runs")


class RunSimulationRequest(BaseModel):
    """Request to run a simulation (no body needed, just POST to endpoint)."""

    pass


class RunSimulationResponse(BaseModel):
    """Response after starting a simulation run."""

    run_id: int = Field(..., description="ID of the created run")
    scenario_id: int = Field(..., description="Scenario ID")
    state: str = Field(..., description="Run state: 'running', 'completed', 'failed'")
    message: str = Field(..., description="Human-readable status message")
