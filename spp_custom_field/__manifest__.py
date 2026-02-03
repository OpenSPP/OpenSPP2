# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Custom Fields",
    "summary": "The module enables administrators to define and add custom data fields directly to registrant profiles, tailoring data collection for specific social protection programs. It supports field differentiation by registrant type, integrates new data points into records, and provides dedicated sections for read-only program indicators.",
    "category": "OpenSPP/Configuration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": ["base", "spp_registry", "spp_security"],
    "data": [
        "security/ir.model.access.csv",
        "views/field_group_views.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
