{
    "name": "OpenSPP Versioning",
    "version": "19.0.2.0.0",
    "category": "OpenSPP",
    "summary": "Artifact versioning with scheduled activation",
    "description": """
OpenSPP Versioning
==================

Provides a unified versioning framework for any model that needs:

* Version history with snapshots
* Scheduled activation (future effective dates)
* Optional approval workflow for versions
* Usage tracking to prevent archiving in-use artifacts
* Temporal validity (effective dates, supersession chain)

This is a foundation module. To use versioning on your model:

1. Inherit from ``spp.versioned.mixin``
2. Implement ``_get_version_snapshot_fields()`` to define which fields to snapshot
3. Optionally implement ``_get_test_records()`` for test gate functionality

Example::

    class MyModel(models.Model):
        _inherit = ["my.model", "spp.versioned.mixin"]

        def _get_version_snapshot_fields(self):
            return ["name", "value", "config"]
    """,
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Stable",
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
}
