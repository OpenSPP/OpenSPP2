"""Studio lifecycle mixin for all Studio configurations."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StudioMixin(models.AbstractModel):
    """Mixin providing lifecycle management for Studio configurations.

    Provides:
    - Draft → Active → Inactive lifecycle
    - Audit tracking via spp_audit (unified audit system)
    - Created/modified by tracking
    - Activation/deactivation with impact warnings
    """

    _name = "spp.studio.mixin"
    _description = "Studio Configuration Mixin"
    # Note: mail.thread/mail.activity.mixin removed to avoid MRO conflicts
    # when this mixin is used to extend models that already have them.
    # Models using this mixin should add mail mixins directly if needed.

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
        index=True,
        help="Draft: Configuration is being edited, not yet in use.\n"
        "Active: Configuration is in use and affects live data.\n"
        "Inactive: Configuration was deactivated, can be reactivated.",
    )

    # Audit fields
    created_by_id = fields.Many2one(
        "res.users",
        string="Created By",
        readonly=True,
        copy=False,
        default=lambda self: self.env.user,
    )
    created_date = fields.Datetime(
        string="Created On",
        readonly=True,
        copy=False,
        default=fields.Datetime.now,
    )
    activated_by_id = fields.Many2one(
        "res.users",
        string="Activated By",
        readonly=True,
        copy=False,
    )
    activated_date = fields.Datetime(
        string="Activated On",
        readonly=True,
        copy=False,
    )
    deactivated_by_id = fields.Many2one(
        "res.users",
        string="Deactivated By",
        readonly=True,
        copy=False,
    )
    deactivated_date = fields.Datetime(
        string="Deactivated On",
        readonly=True,
        copy=False,
    )

    # Link to programs (optional, for program-specific configs)
    program_ids = fields.Many2many(
        "spp.program",
        string="Programs",
        help="If set, this configuration is only visible in these programs. " "Leave empty for global visibility.",
    )

    def action_activate(self):
        """Activate the configuration, making it available for use."""
        self.ensure_one()
        if self.state == "active":
            return

        # Hook for subclasses to validate before activation
        self._pre_activate()

        self.write(
            {
                "state": "active",
                "activated_by_id": self.env.user.id,
                "activated_date": fields.Datetime.now(),
            }
        )

        # Create audit log entry
        self._create_audit_log("activate")

        # Hook for subclasses to perform actions after activation
        self._post_activate()

        return True

    def action_deactivate(self):
        """Deactivate the configuration."""
        self.ensure_one()
        if self.state == "inactive":
            return

        if self.state == "draft":
            raise UserError(
                _(
                    "This configuration is still in Draft state.\n\n"
                    "To delete it: You can safely delete draft configurations directly.\n"
                    "To deactivate it: First activate it, then deactivate."
                )
            )

        # Hook for subclasses to check impact before deactivation
        impact = self._get_deactivation_impact()
        if impact:
            # Return a confirmation wizard if there's impact
            return self._show_deactivation_warning(impact)  # pylint: disable=assignment-from-none

        return self._do_deactivate()

    def _do_deactivate(self):
        """Actually perform the deactivation."""
        self.ensure_one()

        # Hook for subclasses to validate before deactivation
        self._pre_deactivate()

        self.write(
            {
                "state": "inactive",
                "deactivated_by_id": self.env.user.id,
                "deactivated_date": fields.Datetime.now(),
            }
        )

        # Create audit log entry
        self._create_audit_log("deactivate")

        # Hook for subclasses to perform actions after deactivation
        self._post_deactivate()

        return True

    def action_reactivate(self):
        """Reactivate a previously deactivated configuration."""
        self.ensure_one()
        if self.state != "inactive":
            raise UserError(_("Only inactive configurations can be reactivated."))

        return self.action_activate()

    def action_set_draft(self):
        """Return configuration to draft state (only from inactive)."""
        self.ensure_one()
        if self.state == "active":
            raise UserError(_("Cannot return active configuration to draft. Deactivate it first."))

        self.write({"state": "draft"})
        self._create_audit_log("set_draft")
        return True

    # Hook methods for subclasses to override
    def _pre_activate(self):
        """Hook called before activation. Override to add validation."""
        pass

    def _post_activate(self):
        """Hook called after activation. Override to perform actions."""
        pass

    def _pre_deactivate(self):
        """Hook called before deactivation. Override to add validation."""
        pass

    def _post_deactivate(self):
        """Hook called after deactivation. Override to perform cleanup."""
        pass

    def _get_deactivation_impact(self):
        """Return impact description if deactivating would affect data.

        Override in subclasses to check for usage and return a description
        of what would be affected.

        Returns:
            str or None: Impact description, or None if no impact.
        """
        return None

    def _show_deactivation_warning(self, impact):
        """Show a warning dialog about deactivation impact.

        Override to customize the warning dialog.
        """
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirm Deactivation"),
            "res_model": "spp.studio.deactivate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_config_model": self._name,
                "default_config_id": self.id,
                "default_impact_message": impact,
            },
        }

    def _create_audit_log(self, action):
        """Create an audit log entry for this action using spp_audit.

        Args:
            action: One of 'activate', 'deactivate', 'set_draft'
        """
        if "spp.audit.rule" not in self.env:
            return

        # Build old/new values based on action for audit trail
        if action == "activate":
            old_values = {"state": "draft"}
            new_values = {"state": "active"}
        elif action == "deactivate":
            old_values = {"state": "active"}
            new_values = {"state": "inactive"}
        elif action == "set_draft":
            old_values = {"state": "inactive"}
            new_values = {"state": "draft"}
        else:
            old_values = {}
            new_values = {}

        self.env["spp.audit.rule"].log_lifecycle_action(
            model_name=self._name,
            record_id=self.id,
            action=action,
            old_values=old_values,
            new_values=new_values,
        )

    @api.model
    def _get_studio_config_type(self):
        """Return a human-readable type name for this configuration.

        Override in subclasses to provide a specific name.
        """
        return _("Configuration")

    def unlink(self):
        """Prevent deletion of active configurations."""
        for record in self:
            if record.state == "active":
                raise UserError(
                    _(
                        "Cannot delete '%(name)s' because it is currently Active.\n\n"
                        "Active configurations may be in use by programs or other components.\n"
                        "To delete: First click 'Deactivate', then delete.",
                        name=record.display_name,
                    )
                )
        return super().unlink()
