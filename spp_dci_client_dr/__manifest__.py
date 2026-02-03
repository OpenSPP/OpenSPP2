# pylint: disable-all
{
    "name": "OpenSPP DCI Client - Disability Registry",
    "summary": "Connect to Disability Registry via DCI API",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": ["spp_dci_client", "spp_dci_server", "spp_registry"],
    "data": [
        "security/ir.model.access.csv",
        "views/disability_status_views.xml",
        "views/dr_sender_views.xml",
    ],
    "installable": True,
    "application": False,
}
