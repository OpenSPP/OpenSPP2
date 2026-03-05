# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Simulation API",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": [
        "spp_api_v2",
        "spp_simulation",
        "spp_aggregation",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": """
        REST API for simulation scenario management.
    """,
    "description": """
OpenSPP Simulation API
======================

Extends OpenSPP API V2 with simulation-specific endpoints for managing targeting scenarios,
runs, and comparisons, plus aggregation endpoints for population analytics.

Endpoints
---------
- ``CRUD /simulation/scenarios`` - Manage simulation scenarios
- ``CRUD /simulation/runs`` - Execute and retrieve simulation runs
- ``CRUD /simulation/comparisons`` - Compare different scenarios
- ``GET /simulation/scenarios/{id}/execute`` - Execute a scenario
- ``GET /simulation/runs/{id}/results`` - Get run results with metrics
- ``POST /aggregation/compute`` - Population counts with demographic breakdowns
- ``GET /aggregation/dimensions`` - Available group-by dimensions

Design Principles
-----------------
- RESTful design for scenario lifecycle management
- Batch execution support for large-scale simulations
- Metric aggregation for analysis and comparison
- Requires authentication via OAuth 2.0
- Privacy protection via unified aggregation service (k-anonymity)
    """,
}
