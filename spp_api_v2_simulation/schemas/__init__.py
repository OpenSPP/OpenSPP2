# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for simulation and aggregation API."""

from . import analytics
from . import simulation
from .comparison import (
    ComparisonCreateRequest,
    ComparisonResponse,
    ComparisonRunData,
    OverlapData,
)
from .run import (
    DistributionData,
    FairnessData,
    GeographicData,
    MetricResult,
    RunListResponse,
    RunResponse,
    RunSimulationRequest,
    RunSimulationResponse,
    RunSummary,
    ScenarioSnapshot,
    TargetingEfficiencyData,
)
from .scenario import (
    EntitlementRuleResponse,
    EntitlementRuleSchema,
    ScenarioCreateRequest,
    ScenarioListResponse,
    ScenarioResponse,
    ScenarioUpdateRequest,
)

__all__ = [
    "analytics",
    "simulation",
    # Scenario schemas
    "EntitlementRuleSchema",
    "EntitlementRuleResponse",
    "ScenarioCreateRequest",
    "ScenarioUpdateRequest",
    "ScenarioResponse",
    "ScenarioListResponse",
    # Run schemas
    "RunResponse",
    "RunListResponse",
    "RunSimulationRequest",
    "RunSimulationResponse",
    "RunSummary",
    "DistributionData",
    "FairnessData",
    "GeographicData",
    "MetricResult",
    "TargetingEfficiencyData",
    "ScenarioSnapshot",
    # Comparison schemas
    "ComparisonCreateRequest",
    "ComparisonRunData",
    "OverlapData",
    "ComparisonResponse",
]
