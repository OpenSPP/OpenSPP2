{
    "name": "OpenSPP Versioning",
    "version": "19.0.2.0.0",
    "category": "OpenSPP",
    "summary": "Artifact versioning with scheduled activation",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "depends": [
        "spp_security",
        "mail",
    ],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/artifact_version_views.xml",
        "wizard/schedule_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
