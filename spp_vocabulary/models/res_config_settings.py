import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """Extend settings to include deployment profile configuration."""

    _inherit = "res.config.settings"

    deployment_profile_id = fields.Many2one(
        comodel_name="spp.deployment.profile",
        string="Active Deployment Profile",
        help="Select the deployment profile to activate for vocabulary code filtering. "
        "This determines which vocabulary codes are available for selection in the UI.",
    )

    @api.model
    def get_values(self):
        """Get current active deployment profile."""
        res = super().get_values()
        active_profile = self.env["spp.deployment.profile"].get_active_profile()
        res.update(deployment_profile_id=active_profile.id if active_profile else False)
        return res

    def set_values(self):
        """Activate the selected deployment profile."""
        super().set_values()

        # Get the currently active profile
        active_profile = self.env["spp.deployment.profile"].get_active_profile()

        # If the selection changed, activate the new profile
        if self.deployment_profile_id != active_profile:
            if self.deployment_profile_id:
                # Activate the newly selected profile (this deactivates others)
                self.deployment_profile_id.action_activate()
            elif active_profile:
                # If no profile is selected, deactivate the current one
                active_profile.write({"is_active": False})
