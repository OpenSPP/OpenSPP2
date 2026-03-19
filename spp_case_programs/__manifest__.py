# pylint: disable=pointless-statement
{
    "name": "OpenSPP Case Programs Integration",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/Monitoring",
    "summary": "Links cases to OpenSPP programs and provides compliance tracking",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_security",
        "spp_case_base",
        "spp_programs",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Views
        "views/case_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": True,
}
