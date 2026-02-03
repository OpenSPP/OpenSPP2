# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Studio API v2 Integration",
    "version": "19.0.2.0.0",
    "category": "OpenSPP",
    "summary": "Bridge Studio custom fields and variables with API v2",
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "depends": [
        "spp_api_v2",
        "spp_studio",
        "spp_cel_domain",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/api_extension_data.xml",
    ],
    "installable": True,
    # Bridge module: auto-install when both spp_api_v2 and spp_studio are present
    "auto_install": ["spp_api_v2", "spp_studio"],
}
