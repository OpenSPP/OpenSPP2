# pylint: disable-next=pointless-statement
{
    "name": "OpenSPP DCI Client - IBR",
    "summary": "Connect to IBR for duplication checks via DCI API",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
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
}
