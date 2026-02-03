# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.exceptions import AccessError


class ResPartner(models.Model):
    """Extend res.partner to track view history and control archive access for registrants."""

    _inherit = "res.partner"

    @api.model
    def get_formview_action(self, access_uid=None):
        """Override to record view history when opening registrant form.

        This ensures that whenever a registrant form is opened,
        it gets recorded in the user's view history.
        """
        action = super().get_formview_action(access_uid=access_uid)

        # Record view for registrants
        if self.is_registrant:
            self.env["spp.registry.view.history"].sudo().record_view(self.id)

        return action

    def _check_archive_permission(self):
        """Check if current user can archive/unarchive registrants.

        Only officers, managers, and admins can archive or unarchive registrants.
        Viewers and other read-only users should not have this capability.
        """
        archive_groups = [
            "base.group_system",
            "spp_security.group_spp_admin",
            "spp_registry.group_registry_manager",
            "spp_registry.group_registry_officer",
        ]
        for group in archive_groups:
            try:
                if self.env.user.has_group(group):
                    return True
            except ValueError:
                # Group doesn't exist (module not installed)
                continue
        return False

    def action_archive(self):
        """Override to restrict archive action to authorized groups."""
        # Only check for registrants
        registrants = self.filtered(lambda p: p.is_registrant)
        if registrants and not self._check_archive_permission():
            raise AccessError(_("You do not have the necessary permissions to archive registrants."))
        return super().action_archive()

    def action_unarchive(self):
        """Override to restrict unarchive action to authorized groups."""
        # Only check for registrants
        registrants = self.filtered(lambda p: p.is_registrant)
        if registrants and not self._check_archive_permission():
            raise AccessError(_("You do not have the necessary permissions to unarchive registrants."))
        return super().action_unarchive()
