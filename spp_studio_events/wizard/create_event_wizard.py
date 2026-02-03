"""Extension to generic event wizard for Studio event type support."""

import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class SPPCreateEventWizardStudioExtension(models.TransientModel):
    """Extend generic event wizard to detect and redirect to Studio wizard."""

    _inherit = "spp.create.event.wizard"

    def create_event(self):
        """Override to redirect to Studio wizard if applicable.

        When the selected event type is linked to an active Studio event type,
        redirect to the Studio entry wizard for proper field-by-field data entry.
        """
        self.ensure_one()

        if self.event_type_id:
            studio_event_type = self.event_type_id._get_active_studio_event_type()
            if studio_event_type:
                return self._redirect_to_studio_wizard(studio_event_type)

        return super().create_event()

    def _redirect_to_studio_wizard(self, studio_event_type):
        """Redirect to Studio entry wizard.

        Args:
            studio_event_type: spp.studio.event.type record

        Returns:
            Action dictionary to open Studio wizard
        """
        self.ensure_one()
        _logger.info(
            "Redirecting to Studio entry wizard for event type '%s' (partner: %s)",
            studio_event_type.name,
            self.partner_id.name,
        )

        # Build action with context defaults
        action = {
            "type": "ir.actions.act_window",
            "name": _("Enter Event: %(name)s", name=studio_event_type.name),
            "res_model": "spp.event.data.entry.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_studio_event_type_id": studio_event_type.id,
                "default_partner_id": self.partner_id.id,
                "default_collection_date": str(self.collection_date),
            },
        }

        # Use the generated view if available
        if studio_event_type.wizard_view_id:
            action["views"] = [(studio_event_type.wizard_view_id.id, "form")]

        return action
