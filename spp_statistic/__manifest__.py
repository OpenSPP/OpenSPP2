# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Statistics",
    "summary": "Publishable statistics based on CEL variables for dashboards, GIS, and APIs",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_cel_domain",
        "spp_metrics_core",
        "spp_security",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/statistic_categories.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "description": """
OpenSPP Statistics
==================

Provides a configuration layer for publishable statistics that can be
consumed by multiple contexts (GIS, dashboards, APIs, reports).

Architecture
------------
Statistics separate "what to compute" (CEL variables) from "where to publish"
(contexts) and "how to present" (labels, formats, grouping).

::

    spp.cel.variable (defines computation)
        │
        └── Referenced by ──► spp.statistic (defines publication)
                                  ├── is_published_gis
                                  ├── is_published_dashboard
                                  ├── is_published_api
                                  │
                                  └── spp.statistic.context
                                        ├── context (gis/dashboard/api)
                                        ├── label, format, group
                                        └── context-specific config

Models
------
- ``spp.statistic``: Publishable statistic referencing a CEL variable
- ``spp.statistic.category``: Organization categories for statistics
- ``spp.statistic.context``: Context-specific presentation configuration

Usage
-----
Define statistics via XML or UI::

    <record id="stat_children_under_5" model="spp.statistic">
        <field name="name">children_under_5</field>
        <field name="variable_id" ref="cel_var_children_under_5"/>
        <field name="label">Children Under 5</field>
        <field name="is_published_gis" eval="True"/>
        <field name="is_published_dashboard" eval="True"/>
    </record>

Query statistics for a context::

    stats = env["spp.statistic"].get_published_for_context("gis")
    """,
}
