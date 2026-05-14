{  # pylint: disable=pointless-statement
    "name": "OpenSPP DCI Server — Disability Registry",
    "summary": (
        "Server-side DCI Disability Registry handler — replaces the 501 stub "
        "in spp_dci_server with a real /disability/registry/sync/search endpoint."
    ),
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_dci_server",
        "spp_registry",
        "spp_vocabulary",
    ],
    "external_dependencies": {"python": []},
    "data": [
        "security/ir.model.access.csv",
        "data/dr_id_types.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
