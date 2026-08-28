# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement
{
    "name": "OpenSPP CEL Load Testing",
    "summary": "Performance and validation testing for CEL expressions and studio logic",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "spp_cel_domain",
        "spp_programs",
    ],
    "external_dependencies": {
        "python": ["faker"],
    },
    "data": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
