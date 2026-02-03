# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement
{
    "name": "OpenSPP Key Management",
    "summary": "Centralized cryptographic key management with pluggable providers",
    "category": "OpenSPP/Identity",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["openspp-dev"],
    "depends": [
        "base",
        "spp_security",
    ],
    "external_dependencies": {
        "python": [
            "cryptography",
        ],
    },
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "data/key_purposes.xml",
        "views/encryption_key_views.xml",
        "views/key_provider_views.xml",
        "views/asymmetric_key_views.xml",
        "views/menu.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
