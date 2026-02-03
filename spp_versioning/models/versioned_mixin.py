"""Versioned Mixin for artifacts that need version history and lifecycle management."""

import logging

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class VersionedMixin(models.AbstractModel):
    """Mixin for any model that needs versioning with lifecycle management.

    IMPORTANT: Approval is on VERSIONS, not artifacts. This mixin provides
    the artifact-side hooks; approval workflow lives in spp.artifact.version.

    To use this mixin:
    1. Inherit from it: _inherit = ["my.model", "spp.versioned.mixin"]
    2. Implement _get_version_snapshot_fields() to define which fields to snapshot
    3. Optionally implement _get_test_records() for test gate functionality
    """

    _name = "spp.versioned.mixin"
    _description = "Versioned Artifact Mixin"

    # === Versioning Configuration ===
    # NOTE: No computed fields for versioning info because they conflict with
    # spp_audit decorator (recursion during read). Use helper methods instead:
    # - get_version_count()
    # - get_current_version()
    # - get_version_ids()

    # === Test Gate (per-artifact) ===
    is_test_pass_required = fields.Boolean(
        string="Require Tests Pass",
        default=True,
        help="If true, all tests must pass before publishing new versions",
    )

    # === Approval Configuration ===
    is_approval_required = fields.Boolean(
        string="Require Approval",
        default=False,
        help="If true, new versions require approval before scheduling/activation",
    )

    # === Usage Tracking Configuration ===
    # NOTE: No computed fields for usage info for the same reason.
    # Use helper methods instead:
    # - get_usage_count()
    # - get_is_in_use()
    # - get_usage_ids()

    def get_version_count(self):
        """Return the number of versions for this artifact.

        Use this method instead of a computed field to avoid recursion
        issues with spp_audit decorator.

        Returns:
            int: Number of versions
        """
        self.ensure_one()
        return self.env["spp.artifact.version"].search_count(
            [
                ("model", "=", self._name),
                ("res_id", "=", self.id),
            ]
        )

    def get_current_version(self):
        """Return the currently active version.

        Use this method instead of a computed field to avoid recursion
        issues with spp_audit decorator.

        Returns:
            spp.artifact.version: Current version record or empty recordset
        """
        self.ensure_one()
        return self.env["spp.artifact.version"].search(
            [
                ("model", "=", self._name),
                ("res_id", "=", self.id),
                ("state", "=", "current"),
            ],
            limit=1,
        )

    def get_usage_count(self):
        """Return the number of usage records for this artifact.

        Use this method instead of a computed field to avoid recursion
        issues with spp_audit decorator.

        Returns:
            int: Number of usages
        """
        self.ensure_one()
        return self.env["spp.artifact.usage"].search_count(
            [
                ("artifact_model", "=", self._name),
                ("artifact_res_id", "=", self.id),
            ]
        )

    def get_is_in_use(self):
        """Check if this artifact is in use by any consumer.

        Use this method instead of a computed field to avoid recursion
        issues with spp_audit decorator.

        Returns:
            bool: True if the artifact has any usages
        """
        return self.get_usage_count() > 0

    def get_version_ids(self):
        """Return all versions for this artifact.

        Use this method instead of a computed field to avoid recursion issues
        with spp_audit decorator.

        Returns:
            recordset: spp.artifact.version records ordered by version desc
        """
        self.ensure_one()
        return self.env["spp.artifact.version"].search(
            [
                ("model", "=", self._name),
                ("res_id", "=", self.id),
            ],
            order="version desc",
        )

    def get_usage_ids(self):
        """Return all usage records for this artifact.

        Use this method instead of a computed field to avoid recursion issues
        with spp_audit decorator.

        Returns:
            recordset: spp.artifact.usage records
        """
        self.ensure_one()
        return self.env["spp.artifact.usage"].search(
            [
                ("artifact_model", "=", self._name),
                ("artifact_res_id", "=", self.id),
            ]
        )

    def unlink(self):
        """Clean up orphan versions and usages when artifact is deleted."""
        Version = self.env["spp.artifact.version"]
        Usage = self.env["spp.artifact.usage"]
        # Batch operation to avoid N+1 queries
        Version.search(
            [
                ("model", "=", self._name),
                ("res_id", "in", self.ids),
            ]
        ).unlink()
        Usage.search(
            [
                ("artifact_model", "=", self._name),
                ("artifact_res_id", "in", self.ids),
            ]
        ).unlink()
        return super().unlink()

    # === Hooks (override in subclass) ===
    def _get_version_snapshot_fields(self):
        """Return list of field specifications to snapshot. Override per model.

        Field specifications support different versioning strategies for relations:

        Supported formats:
            - String: "field_name" - scalar or relation with default (shallow) strategy
            - Tuple (strategy): ("field_name", "strategy") - relation with specific strategy
            - Tuple (options): ("field_name", {...}) - relation with full options dict

        Versioning strategies for relational fields:

        **shallow** (default):
            Store only ID(s). Relations must exist when restoring.
            Example: "category_id" or ("category_id", "shallow")
            Serialized: {"category_id": 5}

        **embed**:
            Store ID(s) + snapshot of related record's fields.
            Useful for preserving reference data even if related record is deleted.
            Example: ("category_id", "embed") or ("category_id", {"strategy": "embed", "fields": ["name", "code"]})
            Serialized: {"category_id": {"_ref": 5, "_data": {"name": "Eligibility", "code": "ELIG"}}}
            If "fields" not specified, defaults to ["name"] or ["name", "code"] if code exists.

        **follow**:
            Cascade versioning to related records (create versions for them too).
            Useful for maintaining consistency across related artifacts.
            Example: ("program_id", "follow")
            Serialized: {"program_id": {"_ref": 5, "_version_id": 101}}
            Only works if related model inherits from spp.versioned.mixin.

        Example implementation:
            def _get_version_snapshot_fields(self):
                return [
                    "name",                          # scalar field
                    "description",                   # scalar field
                    "category_id",                   # relation (shallow by default)
                    ("program_id", "embed"),         # relation with embed strategy
                    ("variable_ids", "follow"),      # cascade version to related
                ]

        Returns:
            list: Field specifications (strings or tuples) to include in version snapshots
        """
        return []

    def _get_test_records(self):
        """Return test records for this artifact. Override per model.

        Returns:
            recordset: Test records to check before publishing
        """
        # Return empty recordset - this method should be overridden by models
        # that have associated tests. The spp.logic.test model is defined in
        # spp_studio which may not be installed.
        try:
            return self.env["spp.logic.test"].browse()  # Empty recordset
        except KeyError:
            # Model doesn't exist - return an empty list-like object
            return []

    def _check_can_publish(self):
        """Validation before publishing. Override to add checks."""
        self._check_test_pass_gate()

    def _check_test_pass_gate(self):
        """Enforce test pass gate if configured."""
        if not self.is_test_pass_required:
            return
        tests = self._get_test_records()
        if not tests:
            return  # No tests = no gate
        failing = tests.filtered(lambda t: t.last_run_status != "passed")
        if failing:
            raise ValidationError(
                _("%(count)d test(s) must pass before publishing: %(names)s")
                % {
                    "count": len(failing),
                    "names": ", ".join(failing.mapped("name")),
                }
            )

    def action_create_version(self, change_summary=None):
        """Create a version snapshot of current state.

        Args:
            change_summary: Description of what changed in this version

        Returns:
            spp.artifact.version: The created version record
        """
        self.ensure_one()
        return self.env["spp.artifact.version"].create_version(
            model=self._name,
            res_id=self.id,
            change_summary=change_summary,
        )

    def action_open_schedule_wizard(self):
        """Open the version scheduling wizard.

        Returns:
            dict: Window action to open the wizard
        """
        self.ensure_one()
        # First create a draft version
        version = self.action_create_version(change_summary=_("Draft version"))
        return {
            "type": "ir.actions.act_window",
            "name": _("Schedule Version"),
            "res_model": "spp.artifact.version.schedule.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_version_id": version.id},
        }

    def action_view_versions(self):
        """View all versions for this artifact.

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

    def action_archive(self):
        """Archive with usage check."""
        if self.get_is_in_use():
            raise ValidationError(
                _("Cannot archive: used by %(count)d program(s). Remove usages first.")
                % {"count": self.get_usage_count()}
            )
        # Call parent archive method if it exists
        if hasattr(super(), "action_archive"):
            return super().action_archive()
        # Otherwise just set active to False if the field exists
        if "active" in self._fields:
            return self.write({"active": False})
        return True
