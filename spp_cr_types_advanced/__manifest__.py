{
    "name": "OpenSPP CR Types - Advanced",
    "version": "19.0.2.0.0",
    "sequence": 52,
    "category": "OpenSPP",
    "summary": "Advanced change request types with custom Python strategies",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
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
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
