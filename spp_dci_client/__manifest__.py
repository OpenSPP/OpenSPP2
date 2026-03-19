# pylint: disable=pointless-statement
{
    "name": "OpenSPP DCI Client",
    "summary": "Base DCI client infrastructure with OAuth2 and data source management",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "base",
        "spp_dci",
    ],
    "external_dependencies": {
        "python": [
            "httpx",
        ],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/data_source_views.xml",
    ],
    "installable": True,
    "application": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
