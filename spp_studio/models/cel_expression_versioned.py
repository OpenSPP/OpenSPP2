"""Add versioning capabilities to CEL expressions."""

import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class CelExpressionVersioned(models.Model):
    """Extend CEL expressions with versioning from spp_versioning.

    This adds version history, scheduled activation, and usage tracking
    to expressions. spp_cel_domain remains independent of versioning.
    """

    _name = "spp.cel.expression"
    _inherit = ["spp.cel.expression", "spp.versioned.mixin"]

    def _get_version_snapshot_fields(self):
        """Define which fields to snapshot for versioning.

        Returns:
            list: Field names to include in version snapshots
        """
        return [
            "name",
            "cel_expression",
            "expression_type",
            "context_type",
            "output_type",
            "sequence",
        ]

    def _get_test_records(self):
        """Return test records for this expression.

        Returns:
            recordset: Test records from spp_studio
        """
        if "test_ids" in self._fields:
            return self.test_ids
        return self.env["spp.logic.test"].browse()

    def action_view_versions(self):
        """View all versions for this expression using the new versioning system.

        Overrides the old spp.studio.version-based action to use spp.artifact.version.

        Returns:
            dict: Window action to view versions
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Version History: %s") % self.display_name,
            "res_model": "spp.artifact.version",
            "view_mode": "list,form",
            "domain": [
                ("model", "=", self._name),
                ("res_id", "=", self.id),
            ],
            "context": {"default_model": self._name, "default_res_id": self.id},
        }
