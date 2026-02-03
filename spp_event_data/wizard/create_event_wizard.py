# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import _, api, fields, models


class SPPCreateEventWizard(models.TransientModel):
    _name = "spp.create.event.wizard"
    _description = "Create Event Wizard"

    # New event type selection (preferred)
    event_type_id = fields.Many2one(
        "spp.event.type",
        string="Event Type",
        domain=[("active", "=", True)],
    )

    # Legacy event model selection (backward compatibility)
    event_data_model = fields.Selection(
        [("default", "None")],
        "Legacy Event Type",
        default="default",
    )

    partner_id = fields.Many2one(
        "res.partner",
        domain=[("is_registrant", "=", True)],
        required=True,
    )

    # Legacy field - maps to collector_name
    registrar = fields.Char()

    collection_date = fields.Date(default=lambda self: date.today(), required=True)
    expiry_date = fields.Date()

    # For JSON data storage
    event_data = fields.Json(string="Event Data")

    @api.onchange("event_type_id")
    def _onchange_event_type_id(self):
        """Set expiry date based on event type configuration."""
        if self.event_type_id and self.event_type_id.auto_expire_days:
            self.expiry_date = fields.Date.add(
                self.collection_date or date.today(),
                days=self.event_type_id.auto_expire_days,
            )

    def get_event_data_vals(self):
        """
        Returns the event data values for creating spp.event.data record.
        :return: Event Data Values dictionary.
        """
        self.ensure_one()
        vals = {
            "partner_id": self.partner_id.id,
            "collection_date": self.collection_date or False,
            "expiry_date": self.expiry_date or False,
        }

        if self.event_type_id:
            # New style with event_type_id
            vals["event_type_id"] = self.event_type_id.id
            vals["collector_name"] = self.registrar or False
            if self.event_data:
                vals["data_json"] = self.event_data
        else:
            # Legacy style with model
            vals["model"] = self.event_data_model
            vals["registrar"] = self.registrar or False

        return vals

    def create_event(self):
        """Create the event and return to partner form."""
        self.ensure_one()

        if self.event_type_id:
            # Create event with new style
            vals = self.get_event_data_vals()
            event = self.env["spp.event.data"].create(vals)

            # If event type uses dedicated model, redirect to that wizard
            if self.event_type_id.data_model_id:
                return self._redirect_to_data_wizard(event)

            return {
                "type": "ir.actions.act_window",
                "res_model": "spp.event.data",
                "res_id": event.id,
                "view_mode": "form",
                "target": "current",
            }

        # Legacy behavior
        return self.next_page()

    def next_page(self):
        """
        Legacy method: Set up the event data model then proceed to its view.
        """
        for rec in self:
            if rec.event_data_model and rec.event_data_model != "default":
                model_name = rec.event_data_model
                # compute wizard model name
                wizard_list = model_name.split(".")
                wizard_model = f"{wizard_list[0]}.create."
                wizard_list.pop(0)
                view_name = self.env["ir.model"].search([("model", "=", model_name)]).name
                for split_wizard in wizard_list:
                    wizard_model += f"{split_wizard}."
                wizard_model += "wizard"
                view_id = rec.get_view_id(wizard_model)

                # create the event data and pass it to event_data_model wizard
                vals_list = rec.get_event_data_vals()
                event_id = self.env["spp.event.data"].create(vals_list)

                wiz = self.env[wizard_model].create({"event_id": event_id.id})

                return {
                    "name": _("Create %s", view_name),
                    "view_mode": "form",
                    "res_model": wizard_model,
                    "res_id": wiz.id,
                    "view_id": view_id,
                    "type": "ir.actions.act_window",
                    "target": "new",
                    "context": self.env.context,
                }
        return {"type": "ir.actions.act_window_close"}

    def _redirect_to_data_wizard(self, event):
        """Redirect to dedicated data model wizard if available."""
        self.ensure_one()
        data_model = self.event_type_id.data_model_id.model

        # Try to find a wizard for this model
        wizard_model = data_model.replace(".", ".create.") + ".wizard"
        if wizard_model in self.env:
            view_id = self.get_view_id(wizard_model)
            wiz = self.env[wizard_model].create({"event_id": event.id})
            return {
                "name": _("Create %s", self.event_type_id.name),
                "view_mode": "form",
                "res_model": wizard_model,
                "res_id": wiz.id,
                "view_id": view_id,
                "type": "ir.actions.act_window",
                "target": "new",
                "context": self.env.context,
            }

        # No wizard found, return to event form
        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.event.data",
            "res_id": event.id,
            "view_mode": "form",
            "target": "current",
        }

    def get_view_id(self, model_name):
        """
        Retrieves the Model View ID.
        :param model_name: The Model.
        :return: Model View ID.
        """
        return self.env["ir.ui.view"].search([("model", "=", model_name), ("type", "=", "form")], limit=1).id
