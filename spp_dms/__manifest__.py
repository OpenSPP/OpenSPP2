# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP Document Management System",
    "category": "OpenSPP",
    "version": "19.0.1.4.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "base",
        "web",
        "spp_security",
    ],
    "external_dependencies": {"python": ["Pillow>=9.0.1"]},
    "data": [
        "security/privileges.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizard/restore_version_wizard_views.xml",
        "views/main_view.xml",
        "views/dms_directory_views.xml",
        "views/dms_file_version_views.xml",
        "views/dms_file_views.xml",
        "views/dms_category_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_dms/static/src/js/preview_binary_field.esm.js",
            "spp_dms/static/src/xml/preview_binary_field.xml",
        ],
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": "The OpenSPP Dms module provides a centralized system for managing and organizing program-related documents within a structured directory tree. It facilitates efficient document retrieval through categorization and indexed storage, automatically capturing essential file metadata such as size, type, and data integrity checksums.",
}
