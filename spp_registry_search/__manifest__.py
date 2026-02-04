# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Registry Search Portal",
    "category": "OpenSPP/Registry",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Stable",
    "summary": "Search-first registry interface for privacy protection",
    "description": """
OpenSPP Registry Search Portal
==============================

Provides a search-first interface for the registry to protect beneficiary privacy.

Features:
- Search-first landing page (no records loaded by default)
- Quick search with minimum 3 characters
- Advanced filters (phone, email, registration date)
- Recently viewed registrants (personal to each user)
- Auditor-only browse-all access

Privacy Protection:
- Regular users must search to find registrants
- No bulk browsing by default
- Audit trail of who viewed which registrants

Security Groups:
- Registry Auditor: Can browse all registrants without search
    """,
    "depends": [
        "spp_registry",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "views/registry_search_actions.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_registry_search/static/src/js/registry_search_portal.js",
            "spp_registry_search/static/src/js/hide_archive_form.js",
            "spp_registry_search/static/src/xml/registry_search_portal.xml",
            "spp_registry_search/static/src/css/registry_search.css",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}
