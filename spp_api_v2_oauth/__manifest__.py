# pylint: disable=pointless-statement
{
    "name": "OpenSPP API V2: OAuth RS256 Bridge",
    "summary": "Bridges spp_api_v2 and spp_oauth to enable RS256 JWT authentication for the API.",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "author": "OpenSPP.org",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "external_dependencies": {"python": ["pyjwt>=2.4.0", "cryptography"]},
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "depends": [
        "spp_api_v2",
        "spp_oauth",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/oauth_issuer_views.xml",
        "views/api_client_views.xml",
    ],
    "application": False,
    "auto_install": ["spp_api_v2", "spp_oauth"],
    "installable": True,
}
