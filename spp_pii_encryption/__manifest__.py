# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP PII Encryption",
    "summary": "Field-level encryption for PII data with searchable blind indexes",
    "category": "OpenSPP/Configuration",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "base",
        "spp_key_management",  # Centralized key management
        "spp_security",
    ],
    "external_dependencies": {
        "python": [
            "cryptography",
        ],
    },
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "views/audit_log_views.xml",
        "views/field_encryption_config_views.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_pii_encryption/static/src/js/masked_field.js",
            "spp_pii_encryption/static/src/xml/masked_field.xml",
            "spp_pii_encryption/static/src/scss/masked_field.scss",
        ],
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
