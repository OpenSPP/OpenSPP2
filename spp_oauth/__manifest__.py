# pylint: disable=pointless-statement
{
    "name": "OpenSPP API: Oauth",
    "summary": "The module establishes an OAuth 2.0 authentication framework, securing OpenSPP API communication for integrated systems and applications.",
    "category": "OpenSPP/Integration",
    "version": "19.0.1.3.1",
    "author": "OpenSPP.org",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "external_dependencies": {"python": ["pyjwt>=2.4.0", "cryptography"]},
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "depends": [
        "spp_security",
        "base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter_data.xml",
        "views/res_config_view.xml",
    ],
    "application": False,
    "auto_install": False,
    "installable": True,
}
