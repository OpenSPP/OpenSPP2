{  # pylint: disable=pointless-statement
    "name": "OpenSPP DCI Core",
    "summary": "Core DCI (Digital Convergence Initiative) API components",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "base",
        "spp_registry",
    ],
    "external_dependencies": {
        "python": [
            "pydantic",
            "cryptography",
        ],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/identifier_type_data.xml",
    ],
    "installable": True,
    "application": False,
}
