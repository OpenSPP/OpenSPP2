# pylint: disable=pointless-statement
{
    "name": "OpenSPP Primero Referral",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Integration",
    "summary": "Record a child protection concern and refer the child to Primero through an OpenFn webhook",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["gonzalesedwin1123"],
    "depends": [
        "spp_registry",
        "spp_api_v2",
    ],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "data/vocabulary_protection.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
