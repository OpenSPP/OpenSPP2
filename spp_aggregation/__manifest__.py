# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Aggregation Engine",
    "summary": "Unified aggregation service for statistics, simulations, and GIS queries",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi"],
    "depends": [
        "base",
        "spp_cel_domain",
        "spp_area",
        "spp_registry",
        "spp_security",
        "spp_metrics_services",
    ],
    "data": [
        # Security
        "security/aggregation_security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/cron_cache_cleanup.xml",
        # Views
        "views/aggregation_scope_views.xml",
        "views/aggregation_access_views.xml",
        "views/menu.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "description": """
OpenSPP Aggregation Engine
==========================

Provides a centralized aggregation service that unifies statistics computation
across simulation, GIS API, and dashboards.

Features
--------

- **Unified Scopes**: Define targeting with CEL expressions, spatial polygons,
  administrative areas, or explicit IDs
- **Multi-dimensional Breakdown**: Group by configurable demographic dimensions
  (gender, disability, area, age group)
- **Privacy Protection**: K-anonymity with complementary suppression prevents
  differencing attacks
- **Access Control**: Aggregate-only access for researchers (no individual records)
- **Distribution Statistics**: Gini coefficient, Lorenz curve, percentiles
- **Fairness Analysis**: Parity analysis across demographic groups

Architecture
------------

::

    ┌─────────────────────────────────────────────────────────┐
    │                      CONSUMERS                           │
    ├─────────────┬─────────────┬─────────────┬───────────────┤
    │ Simulation  │   GIS API   │ QGIS Plugin │  Dashboards   │
    └──────┬──────┴──────┬──────┴──────┬──────┴───────┬───────┘
           │             │             │              │
           ▼             ▼             ▼              ▼
    ┌─────────────────────────────────────────────────────────┐
    │          spp.aggregation.service (AbstractModel)         │
    │                                                          │
    │  compute_aggregation(scope, statistics, group_by)        │
    └─────────────────────────────────────────────────────────┘

Models
------

- ``spp.aggregation.scope``: Unified targeting scope (CEL, spatial, area)
- ``spp.aggregation.access.rule``: Access control for aggregate-only users
- ``spp.demographic.dimension``: Configurable breakdown dimensions

Services
--------

- ``spp.aggregation.service``: Main computation entry point
- ``spp.aggregation.scope.resolver``: Resolve scope to registrant IDs
- ``spp.aggregation.cache``: TTL-based result caching
- ``spp.metrics.distribution``: Gini, Lorenz, percentiles
- ``spp.metrics.fairness``: Parity analysis
- ``spp.metrics.privacy``: K-anonymity enforcement
    """,
}
