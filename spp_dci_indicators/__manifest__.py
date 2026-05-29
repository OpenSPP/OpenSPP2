# pylint: disable-next=pointless-statement
{
    "name": "OpenSPP DCI Indicators",
    "summary": "DCI data integration with CEL eligibility expressions",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "spp_dci_client_dr",
        "spp_dci_client_crvs",
        "spp_dci_client_ibr",
        "spp_cel_domain",  # Unified variable system
        "spp_studio",  # For variable label and UI fields
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/indicator_data.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
