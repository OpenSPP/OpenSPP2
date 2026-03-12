# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Targeting Simulation",
    "summary": "Simulate targeting scenarios, analyze fairness and distribution, "
    "and compare different targeting strategies before committing to criteria.",
    "category": "OpenSPP/Targeting",
    "version": "19.0.2.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi"],
    "depends": [
        "base",
        "mail",
        "spp_programs",
        "spp_cel_domain",
        "spp_cel_widget",
        "spp_security",
        "spp_analytics",
        "spp_metric",
    ],
    "data": [
        # Security
        "security/simulation_security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/scenario_templates.xml",
        # Views
        "views/simulation_scenario_template_views.xml",
        "views/simulation_scenario_views.xml",
        "views/simulation_run_views.xml",
        "views/simulation_comparison_views.xml",
        "views/simulation_metric_views.xml",
        "views/menu.xml",
        # Wizard
        "wizard/compare_wizard_views.xml",
        # Report
        "report/simulation_report_views.xml",
        "report/simulation_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_simulation/static/src/results_summary/*",
            "spp_simulation/static/src/fairness_table/*",
            "spp_simulation/static/src/comparison_table/*",
            "spp_simulation/static/src/overlap_table/*",
        ],
    },
    "demo": [],
    "images": [],
    "application": True,
    "installable": True,
    "auto_install": False,
}
