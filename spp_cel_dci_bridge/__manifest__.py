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
    ],
    "external_dependencies": {"python": []},
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
