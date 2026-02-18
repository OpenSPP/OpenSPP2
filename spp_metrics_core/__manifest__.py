# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Metrics Core",
    "summary": "Unified metric foundation for statistics and simulations",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/metric_categories.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "description": """
OpenSPP Metrics Core
====================

Unified foundation for all metrics (statistics, simulation metrics, etc.)

Architecture
------------
Provides a base abstract model that eliminates field duplication across
different metric types (statistics, simulation metrics, etc.).

::

    spp.metric.base (AbstractModel)
        │
        ├── spp.statistic (extends with publication flags)
        └── spp.simulation.metric (extends with scenario-specific fields)

Models
------
- ``spp.metric.base``: Abstract model with shared metric fields
- ``spp.metric.category``: Shared categorization for all metric types

Fields Provided
---------------
- **Identity**: name, label, description
- **Presentation**: unit, decimal_places
- **Categorization**: category_id
- **Metadata**: sequence, active

Migration
---------
Automatically migrates ``spp.statistic.category`` to ``spp.metric.category``
to maintain backward compatibility while providing a unified category model.
    """,
}
