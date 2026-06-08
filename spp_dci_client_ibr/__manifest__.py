# pylint: disable-next=pointless-statement
{
    "name": "OpenSPP DCI Client - IBR",
    "summary": "Connect to IBR for duplication checks via DCI API",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": ["spp_dci_client", "spp_dci_server", "spp_registry"],
    "data": [
        "security/ir.model.access.csv",
        "views/duplication_check_views.xml",
        "views/ibr_sender_views.xml",
    ],
    "installable": True,
    "application": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
