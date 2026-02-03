"""Add versioning capabilities to CEL variables."""

import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class CelVariableVersioned(models.Model):
    """Extend CEL variables with versioning from spp_versioning.

    This adds version history, scheduled activation, and usage tracking
    to variables. spp_cel_domain remains independent of versioning.
    """

    _name = "spp.cel.variable"
    _inherit = ["spp.cel.variable", "spp.versioned.mixin"]

    def _get_version_snapshot_fields(self):
        """Define which fields to snapshot for versioning.

        Returns:
            list: Field names to include in version snapshots
        """
        return [
            "name",
            "description",
            "cel_accessor",
            "source_type",
            "source_model",
            "source_field",
            "cel_expression",
            "default_value",
            "aggregate_type",
            "aggregate_target",
            "aggregate_filter",
            "applies_to",
            "category_id",
        ]

    def action_activate_with_version(self):
        """Activate the variable and create a version snapshot.

        This is an enhanced activation that also records the change.

        Returns:
            bool: True if activation successful
        """
        self.ensure_one()
        self._check_can_publish()

        # Update state to active if field exists
        if "state" in self._fields:
            self.write({"state": "active"})

        # Create version snapshot
        self.action_create_version(change_summary=_("Variable activated"))
        return True
