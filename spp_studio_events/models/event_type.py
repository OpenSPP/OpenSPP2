"""Extension to spp.event.type for Studio integration."""

from odoo import fields, models


class SPPEventTypeStudioExtension(models.Model):
    """Add Studio event type reference to spp.event.type."""

    _inherit = "spp.event.type"

    # Reverse lookup to find if this event type came from Studio
    studio_event_type_ids = fields.One2many(
        "spp.studio.event.type",
        "spp_event_type_id",
        string="Studio Event Types",
        help="Studio event type(s) that created this event type",
    )

    def _get_active_studio_event_type(self):
        """Get the active Studio event type for this event type, if any.

        Returns:
            spp.studio.event.type record or empty recordset
        """
        self.ensure_one()
        return self.studio_event_type_ids.filtered(lambda s: s.state == "active")[:1]
