# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Consent",
    "category": "OpenSPP",
    "version": "19.0.2.0.2",
    "summary": """DPV-aligned consent management for social protection programs.

Implements ISO/IEC TS 27560:2023 consent record information structure
using W3C Data Privacy Vocabulary (DPV) concepts. Provides GDPR-compliant
consent lifecycle management with full audit trail.""",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "base",
        "mail",
        "spp_registry",
        "spp_security",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Data - DPV taxonomies and org types
        "data/org_types.xml",
        "data/dpv_purposes.xml",
        "data/dpv_personal_data.xml",
        "data/dpv_processing.xml",
        "data/default_privacy_notices.xml",
        # Views
        "views/consent_view.xml",
        "views/registrant_view.xml",
        "views/expired_consent_view.xml",
        # Wizards
        "wizard/record_consent.xml",
        "wizard/bulk_record_consent.xml",
        # Scheduled Actions
        "data/consent_cron.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
