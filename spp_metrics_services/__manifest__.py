# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Metrics Services",
    "summary": "Shared services for fairness, distribution, breakdown, and privacy",
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
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/demographic_dimensions.xml",
        "views/demographic_dimension_views.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "description": """
OpenSPP Metrics Services
========================

Provides shared services for metrics computation used across OpenSPP modules.

Services
--------

- ``spp.metrics.fairness``: Parity analysis across demographic groups
- ``spp.metrics.distribution``: Gini coefficient, Lorenz curve, percentiles
- ``spp.metrics.privacy``: K-anonymity enforcement with complementary suppression
- ``spp.metrics.breakdown``: Breakdown computation by demographic dimensions

These services are extracted from spp_aggregation to enable reuse across multiple modules.
    """,
}
