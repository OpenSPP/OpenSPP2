# pylint: disable=pointless-statement
# Copyright 2022 ACSONE SA/NV
# License LGPL-3.0 or later (http://www.gnu.org/licenses/LGPL).

{
    "name": "Odoo FastAPI",
    "category": "Hidden",
    "summary": """
        Odoo FastAPI endpoint""",
    "version": "19.0.2.0.0",
    "license": "LGPL-3",
    "author": "ACSONE SA/NV,Odoo Community Association (OCA)",
    "maintainers": ["lmignon"],
    "website": "https://github.com/OpenSPP/openspp-modules",
    "depends": ["endpoint_route_handler", "spp_security"],
    "data": [
        "security/privileges.xml",
        "security/res_groups.xml",
        "security/fastapi_endpoint.xml",
        "security/ir_rule+acl.xml",
        "views/fastapi_menu.xml",
        "views/fastapi_endpoint.xml",
        "views/fastapi_endpoint_demo.xml",
    ],
    "demo": ["demo/fastapi_endpoint_demo.xml"],
    "external_dependencies": {
        "python": [
            "fastapi>=0.110.0",
            "python-multipart",
            "ujson",
            "a2wsgi>=1.10.6",
            "parse-accept-language",
        ]
    },
    "development_status": "Alpha",
    "installable": True,
}
