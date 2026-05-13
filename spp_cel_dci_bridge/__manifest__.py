# pylint: disable=pointless-statement
{
    "name": "OpenSPP CEL <-> DCI Bridge",
    "summary": "Fetch CEL variable values from external DCI registries",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_cel_domain",
        "spp_dci_client",
        "spp_studio",
    ],
    "external_dependencies": {"python": []},
    "data": [
        "security/ir.model.access.csv",
        "views/data_provider_views.xml",
        "views/cel_variable_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
