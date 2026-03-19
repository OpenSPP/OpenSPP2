{
    "name": "OpenSPP Scoring",
    "category": "OpenSPP/Targeting",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "development_status": "Beta",
    "summary": "Configurable scoring and assessment framework for beneficiary targeting",
    "description": """
OpenSPP Scoring & Assessment Framework
======================================

Provides a flexible, configurable scoring framework for:
- Proxy Means Test (PMT) poverty targeting
- Social Welfare Development Index (SWDI) assessments
- Vulnerability scoring for crisis response
- Custom eligibility scoring formulas

Key Features:
- Model-based scoring configuration (no code changes needed)
- Multiple calculation methods (weighted sum, CEL formula, lookup tables)
- Classification thresholds for score-to-category mapping
- Full audit trail with score breakdowns
- CEL integration for complex formulas
- Batch scoring with job_worker support
- Integration with unified variable system (spp_cel_domain) for CEL access
    """,
    "depends": [
        "base",
        "mail",
        "spp_security",
        "spp_registry",
        "spp_cel_domain",
        "spp_cel_widget",
        "job_worker",
    ],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        # Job Worker (optional, for async batch scoring)
        "data/job_worker_channel.xml",
        # Security (order matters)
        "security/privileges.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        # Views
        "views/scoring_model_views.xml",
        "views/scoring_indicator_views.xml",
        "views/scoring_threshold_views.xml",
        "views/scoring_result_views.xml",
        # Wizards (must be before menus so actions are available)
        "wizard/batch_scoring_wizard_views.xml",
        # Menus (last, references actions from other files)
        "views/menus.xml",
    ],
    "assets": {},
    "application": True,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
