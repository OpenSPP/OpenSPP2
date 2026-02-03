# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class OpenSPPRegistrant(models.Model):
    _inherit = "res.partner"

    event_data_ids = fields.One2many("spp.event.data", "partner_id", string="Event Data")
    event_data_count = fields.Integer(compute="_compute_event_data_count", string="Events")

    # Denormalized cache for active events (scalability optimization)
    active_event_ids_cache = fields.Json(
        string="Active Event IDs Cache",
        help="JSON cache of active event IDs by type for O(1) lookup",
    )

    def _compute_event_data_count(self):
        for rec in self:
            rec.event_data_count = len(rec.event_data_ids)

    def open_create_event_wizard(self):
        """Open the wizard to create a new event."""
        for rec in self:
            view = self.env.ref("spp_event_data.view_spp_create_event_wizard_form")
            wiz = self.env["spp.create.event.wizard"].create({"partner_id": rec.id})
            return {
                "name": _("Create Event Data"),
                "view_mode": "form",
                "res_model": "spp.create.event.wizard",
                "res_id": wiz.id,
                "view_id": view.id,
                "type": "ir.actions.act_window",
                "target": "new",
                "context": self.env.context,
            }

    def action_view_events(self):
        """View all events for this registrant."""
        self.ensure_one()
        return {
            "name": _("Events"),
            "type": "ir.actions.act_window",
            "res_model": "spp.event.data",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def _get_active_event_id(self, model=None, event_type_code=None):
        """
        Get the active event ID for this registrant.

        :param model: Legacy - The Model name (deprecated).
        :param event_type_code: The event type code to look up.
        :return: Active Event Data ID or None.
        """
        self.ensure_one()

        # Check cache first (O(1) lookup)
        if event_type_code and self.active_event_ids_cache:
            cache = self.active_event_ids_cache or {}
            if event_type_code in cache:
                return cache[event_type_code]

        # Fall back to search
        domain = [("partner_id", "=", self.id), ("state", "=", "active")]

        if event_type_code:
            domain.append(("event_type_code", "=", event_type_code))
        elif model:
            # Legacy support
            domain.append(("model", "=", model))

        active_event = self.env["spp.event.data"].search(domain, limit=1)
        return active_event.id if active_event else None

    def get_active_event(self, event_type_code):
        """
        Get the active event record for a given type.

        :param event_type_code: The event type code.
        :return: spp.event.data record or empty recordset.
        """
        self.ensure_one()
        event_id = self._get_active_event_id(event_type_code=event_type_code)
        if event_id:
            return self.env["spp.event.data"].browse(event_id)
        return self.env["spp.event.data"]

    def get_event_data_value(self, event_type_code, field_name, default=None):
        """
        Get a specific value from the active event of a given type.

        :param event_type_code: The event type code.
        :param field_name: The field name within event data.
        :param default: Default value if not found.
        :return: The field value or default.
        """
        self.ensure_one()
        event = self.get_active_event(event_type_code)
        if event:
            return event.get_data_value(field_name, default)
        return default

    def _refresh_active_event_cache(self):
        """
        Refresh the denormalized active event cache.
        Called when events are activated/deactivated.
        """
        for partner in self:
            active_events = self.env["spp.event.data"].search(
                [("partner_id", "=", partner.id), ("state", "=", "active")]
            )
            cache = {}
            for event in active_events:
                if event.event_type_code:
                    cache[event.event_type_code] = event.id
            partner.active_event_ids_cache = cache

    def get_events_by_type(self, event_type_code, states=None, limit=None):
        """
        Get all events of a given type for this registrant.

        :param event_type_code: The event type code.
        :param states: List of states to filter (default: all).
        :param limit: Maximum number of records.
        :return: spp.event.data recordset.
        """
        self.ensure_one()
        domain = [
            ("partner_id", "=", self.id),
            ("event_type_code", "=", event_type_code),
        ]
        if states:
            domain.append(("state", "in", states))
        return self.env["spp.event.data"].search(domain, limit=limit)
