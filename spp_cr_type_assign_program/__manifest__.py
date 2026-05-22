{
    "name": "OpenSPP CR Type - Assign to Program",
    "version": "19.0.1.0.1",
    "sequence": 53,
    "category": "OpenSPP",
    "summary": "Change request type for assigning a registrant to a program",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "depends": [
        "spp_change_request_v2",
        "spp_programs",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/detail_assign_program_views.xml",
        "data/cr_types.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
