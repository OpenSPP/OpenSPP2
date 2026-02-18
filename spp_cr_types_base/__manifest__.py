{
    "name": "OpenSPP CR Types - Base",
    "version": "19.0.2.0.0",
    "sequence": 51,
    "category": "OpenSPP",
    "summary": "Basic change request types with field mapping strategy",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "depends": [
        "spp_change_request_v2",
    ],
    "data": [
        "security/ir.model.access.csv",
        # CR type data definitions with editability flags
        # Note: Detail models, views, and strategies are provided by spp_change_request_v2
        "data/cr_types.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
