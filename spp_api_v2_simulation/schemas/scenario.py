# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for simulation scenarios."""

from pydantic import BaseModel, Field


class EntitlementRuleSchema(BaseModel):
    """Entitlement rule for simulation scenario (create/update)."""

    amount_mode: str = Field(..., description="Mode: 'fixed', 'multiplier', or 'cel'")
    amount: float = Field(..., description="Base amount")
    multiplier_field: str | None = Field(default=None, description="Field for multiplier mode")
    max_multiplier: int | None = Field(default=None, description="Maximum multiplier value")
    amount_cel_expression: str | None = Field(default=None, description="CEL expression for amount calculation")
    condition_cel_expression: str | None = Field(default=None, description="CEL condition for rule application")


class EntitlementRuleResponse(BaseModel):
    """Entitlement rule in response."""

    id: int = Field(..., description="Rule ID")
    amount_mode: str = Field(..., description="Mode: 'fixed', 'multiplier', or 'cel'")
    amount: float = Field(..., description="Base amount")
    multiplier_field: str | None = Field(default=None, description="Field for multiplier mode")
    max_multiplier: int | None = Field(default=None, description="Maximum multiplier value")
    amount_cel_expression: str | None = Field(default=None, description="CEL expression for amount calculation")
    condition_cel_expression: str | None = Field(default=None, description="CEL condition for rule application")


class ScenarioCreateRequest(BaseModel):
    """Request to create a simulation scenario."""

    name: str = Field(..., description="Scenario name")
    description: str | None = Field(default=None, description="Scenario description")
    category: str | None = Field(default=None, description="Scenario category")
    target_type: str = Field(default="group", description="Target type: 'group' or 'individual'")
    targeting_expression: str | None = Field(default=None, description="CEL expression for targeting beneficiaries")
    targeting_expression_explanation: str | None = Field(
        default=None, description="Human-readable explanation of targeting expression"
    )
    ideal_population_expression: str | None = Field(
        default=None, description="CEL expression for ideal population calculation"
    )
    budget_amount: float = Field(default=0.0, description="Total budget amount")
    budget_strategy: str = Field(
        default="none",
        description="Budget strategy: 'none', 'cap_total', or 'proportional_reduction'",
    )
    entitlement_rules: list[EntitlementRuleSchema] = Field(
        default_factory=list, description="List of entitlement rules"
    )
    program_id: int | None = Field(default=None, description="Reference program ID")


class ScenarioUpdateRequest(BaseModel):
    """Request to update a simulation scenario."""

    name: str | None = Field(default=None, description="Scenario name")
    description: str | None = Field(default=None, description="Scenario description")
    category: str | None = Field(default=None, description="Scenario category")
    target_type: str | None = Field(default=None, description="Target type: 'group' or 'individual'")
    targeting_expression: str | None = Field(default=None, description="CEL expression for targeting beneficiaries")
    ideal_population_expression: str | None = Field(
        default=None, description="CEL expression for ideal population calculation"
    )
    budget_amount: float | None = Field(default=None, description="Total budget amount")
    budget_strategy: str | None = Field(
        default=None,
        description="Budget strategy: 'none', 'cap_total', or 'proportional_reduction'",
    )
    entitlement_rules: list[EntitlementRuleSchema] | None = Field(default=None, description="List of entitlement rules")


class ScenarioResponse(BaseModel):
    """Simulation scenario details."""

    id: int = Field(..., description="Scenario ID")
    name: str = Field(..., description="Scenario name")
    description: str | None = Field(default=None, description="Scenario description")
    category: str | None = Field(default=None, description="Scenario category")
    target_type: str = Field(..., description="Target type: 'group' or 'individual'")
    state: str = Field(..., description="Scenario state: 'draft', 'ready', 'archived'")
    targeting_expression: str | None = Field(default=None, description="CEL expression for targeting beneficiaries")
    targeting_expression_explanation: str | None = Field(
        default=None, description="Human-readable explanation of targeting expression"
    )
    ideal_population_expression: str | None = Field(
        default=None, description="CEL expression for ideal population calculation"
    )
    budget_amount: float = Field(..., description="Total budget amount")
    budget_strategy: str = Field(
        ...,
        description="Budget strategy: 'none', 'cap_total', or 'proportional_reduction'",
    )
    targeting_preview_count: int = Field(..., description="Number of beneficiaries in targeting preview")
    targeting_preview_error: str | None = Field(
        default=None, description="Error message from targeting preview, if any"
    )
    run_count: int = Field(..., description="Total number of runs for this scenario")
    latest_beneficiary_count: int = Field(..., description="Beneficiary count from latest run")
    latest_equity_score: float = Field(..., description="Equity score from latest run")
    entitlement_rules: list[EntitlementRuleResponse] = Field(..., description="List of entitlement rules")
    program_id: int | None = Field(default=None, description="Reference program ID")


class ScenarioListResponse(BaseModel):
    """List of simulation scenarios."""

    scenarios: list[ScenarioResponse] = Field(..., description="List of scenarios")
    total_count: int = Field(..., description="Total number of scenarios")


class ConvertToProgramRequest(BaseModel):
    """Request to convert a simulation scenario to a program."""

    name: str | None = Field(default=None, description="Override program name (defaults to scenario name)")
    currency_code: str | None = Field(default=None, description="ISO currency code (e.g., 'USD', 'PHP')")
    is_one_time_distribution: bool = Field(default=False, description="One-time program (auto-creates first cycle)")
    import_beneficiaries: bool = Field(default=False, description="Auto-enroll matching registrants")
    rrule_type: str | None = Field(default=None, description="Recurrence: daily/weekly/monthly/yearly")
    cycle_duration: int | None = Field(default=None, description="Number of recurrence units per cycle")
    day: int | None = Field(default=None, description="Day of month (for monthly by date)")
    month_by: str | None = Field(default=None, description="Monthly mode: 'date' or 'day'")
    weekday: str | None = Field(default=None, description="Day of week (MON-SUN, for monthly by day)")
    byday: str | None = Field(default=None, description="Which week (1-4, -1=last, for monthly by day)")
    mon: bool = Field(default=False, description="Monday (for weekly recurrence)")
    tue: bool = Field(default=False, description="Tuesday (for weekly recurrence)")
    wed: bool = Field(default=False, description="Wednesday (for weekly recurrence)")
    thu: bool = Field(default=False, description="Thursday (for weekly recurrence)")
    fri: bool = Field(default=False, description="Friday (for weekly recurrence)")
    sat: bool = Field(default=False, description="Saturday (for weekly recurrence)")
    sun: bool = Field(default=False, description="Sunday (for weekly recurrence)")


class ConvertToProgramResponse(BaseModel):
    """Response from converting a scenario to a program."""

    program_id: int = Field(..., description="Created program ID")
    program_name: str = Field(..., description="Created program name")
    scenario_id: int = Field(..., description="Source scenario ID")
    warnings: list[str] = Field(default_factory=list, description="Lossy conversion warnings")
