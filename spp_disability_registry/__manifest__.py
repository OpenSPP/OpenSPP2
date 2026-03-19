{
    "name": "OpenSPP Disability Registry",
    "version": "19.0.1.0.0",
    "category": "OpenSPP",
    "summary": "Disability assessment and registry management for social protection",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_registry",
        "spp_vocabulary",
        "spp_approval",
        "spp_cel_domain",
    ],
    "external_dependencies": {"python": []},
    "data": [
        # Security
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        # Data
        "data/id_type.xml",
        "data/vocabulary_type.xml",
        "data/vocabulary_severity.xml",
        "data/vocabulary_cause.xml",
        "data/vocabulary_device.xml",
        "data/concept_groups.xml",
        # Views
        "views/assessment_views.xml",
        "views/assistive_device_views.xml",
        "views/registrant_views.xml",
        "views/menus.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
