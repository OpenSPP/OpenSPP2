# pylint: disable=pointless-statement
{
    "name": "OpenSPP DCI Server - Social Registry",
    "summary": "Expose Social Registry beneficiaries via DCI API",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": ["spp_dci_server", "spp_registry", "spp_cel_domain", "spp_programs"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
}
