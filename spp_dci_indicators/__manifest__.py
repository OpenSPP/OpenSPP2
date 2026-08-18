# pylint: disable-next=pointless-statement
{
    "name": "OpenSPP DCI Indicators",
    "summary": "DCI data integration with CEL eligibility expressions",
    "version": "19.0.1.0.2",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "spp_dci_client",  # spp.dci.data.source (DCI Integration bridge)
        "spp_dci_client_dr",
        "spp_dci_client_crvs",
        "spp_dci_client_ibr",
        "spp_dci_client_sr",  # SRService for r.dci.sr.* fetch handlers
        "spp_cel_domain",  # Unified variable system
        "spp_studio",  # For variable label and UI fields
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/indicator_data.xml",
        "data/dci_sync.xml",
        "views/data_provider_dci_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
