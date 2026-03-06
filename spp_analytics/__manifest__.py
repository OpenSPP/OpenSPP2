# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Analytics",
    "summary": "Query engine for indicators, simulations, and GIS analytics",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi"],
    "depends": [
        "base",
        "spp_cel_domain",
        "spp_area",
        "spp_registry",
        "spp_security",
        "spp_metric_service",
    ],
    "data": [
        # Security
        "security/aggregation_security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/cron_cache_cleanup.xml",
        # Views
        "views/analytics_scope_views.xml",
        "views/analytics_access_views.xml",
        "views/menu.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
