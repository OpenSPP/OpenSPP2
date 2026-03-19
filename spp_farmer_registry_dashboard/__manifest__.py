# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Farmer Registry Dashboard",
    "summary": "Farmer registry dashboard with CEL-based metrics and trends",
    "category": "OpenSPP",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_farmer_registry",
        "spp_dashboard_base",
        "spp_studio",
        "spreadsheet_dashboard",
        "spp_security",
    ],
    "data": [
        "data/dashboard_metrics.xml",
        "data/dashboards.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "description": """
OpenSPP Farmer Registry Dashboard
==================================

Provides a comprehensive dashboard for farmer registry metrics using
CEL variables and Odoo spreadsheet dashboards.

Key Metrics
-----------
- Total farms by type (crop, livestock, aquaculture, mixed)
- Smallholder vs commercial farm distribution
- Farm size distribution
- Female farmer percentage
- Activity counts by season
- Land tenure breakdown
    """,
}
