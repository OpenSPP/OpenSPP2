# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""FastAPI routers for simulation and aggregation API."""

from . import aggregation
from . import simulation
from .comparison import comparison_router
from .run import run_router
from .scenario import scenario_router

__all__ = [
    "aggregation",
    "simulation",
    "scenario_router",
    "run_router",
    "comparison_router",
]
