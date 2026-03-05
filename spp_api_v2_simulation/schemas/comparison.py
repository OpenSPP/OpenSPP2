# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for simulation run comparisons."""

from pydantic import BaseModel, Field


class ComparisonCreateRequest(BaseModel):
    """Request to create a comparison between runs."""

    name: str = Field(default="Comparison", description="Name for this comparison")
    run_ids: list[int] = Field(..., min_length=2, description="IDs of runs to compare (minimum 2)")


class ComparisonRunData(BaseModel):
    """Data for a single run in a comparison."""

    run_id: int = Field(..., description="Run ID")
    scenario_name: str = Field(..., description="Scenario name")
    beneficiary_count: int = Field(..., description="Number of beneficiaries selected")
    total_cost: float = Field(..., description="Total cost of entitlements")
    coverage_rate: float = Field(..., description="Coverage rate (beneficiaries / total registry)")
    equity_score: float = Field(..., description="Equity score (1 - Gini coefficient)")
    gini_coefficient: float = Field(..., description="Gini coefficient measuring inequality")
    has_disparity: bool = Field(..., description="Whether significant disparity was detected")
    leakage_rate: float = Field(..., description="Leakage rate (beneficiaries outside ideal population)")
    undercoverage_rate: float = Field(..., description="Undercoverage rate (ideal population not covered)")
    budget_utilization: float = Field(..., description="Budget utilization rate")
    executed_at: str | None = Field(default=None, description="Execution timestamp (ISO 8601)")


class OverlapData(BaseModel):
    """Overlap data between two runs."""

    run_a_id: int = Field(..., description="First run ID")
    run_a_name: str = Field(..., description="First run scenario name")
    run_b_id: int = Field(..., description="Second run ID")
    run_b_name: str = Field(..., description="Second run scenario name")
    overlap_count: int = Field(..., description="Number of beneficiaries in both runs")
    union_count: int = Field(..., description="Total unique beneficiaries across both runs")
    jaccard_index: float = Field(..., description="Jaccard similarity index (overlap / union)")


class ComparisonResponse(BaseModel):
    """Comparison between simulation runs."""

    id: int = Field(..., description="Comparison ID")
    name: str = Field(..., description="Comparison name")
    runs: list[ComparisonRunData] = Field(..., description="Run data being compared")
    overlap_data: list[OverlapData] = Field(default_factory=list, description="Overlap analysis between runs")
    staleness_warning: str | None = Field(default=None, description="Warning if scenarios were modified after runs")
