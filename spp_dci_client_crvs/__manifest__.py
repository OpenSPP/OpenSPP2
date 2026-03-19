{  # pylint: disable=pointless-statement
    "name": "OpenSPP DCI Client - CRVS",
    "summary": "Connect to CRVS registries via DCI API",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": ["spp_dci_client", "spp_registry"],
    "data": [
        "security/ir.model.access.csv",
        "views/crvs_event_views.xml",
        "views/crvs_sender_views.xml",
    ],
    "installable": True,
    "application": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
