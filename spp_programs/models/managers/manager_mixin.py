# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class ManagerMixin(models.AbstractModel):
    """Manager mixin."""

    _name = "spp.manager.mixin"
    _description = "Manager Mixin"
    _rec_name = "display_name"

    manager_id = fields.Integer("Manager ID")
    manager_ref_id = fields.Reference(string="Manager", selection="_selection_manager_ref_id", required=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("manager_ref_id")
    def _compute_display_name(self):
        for record in self:
            if record.manager_ref_id:
                record.display_name = record.manager_ref_id.display_name or record.manager_ref_id.name
            else:
                record.display_name = "New Manager"

    @api.model
    def _selection_manager_ref_id(self):
        return []

    def open_manager_form(self, readonly=False):
        self.ensure_one()
        if self.manager_ref_id:
            # Get the res_model and res_id from the manager_ref_id (reference field)
            manager_ref_id = str(self.manager_ref_id)
            s = manager_ref_id.find("(")
            res_model = manager_ref_id[:s]
            res_id = self.manager_ref_id.id
            if res_id:
                action = self.env[res_model].get_formview_action()
                context = dict(self.env.context)
                if readonly:
                    context.update({
                        "create": False,
                        "edit": False,
                    })
                action.update(
                    {
                        "views": [(self.env[res_model].get_manager_view_id(), "form")],
                        "res_id": res_id,
                        "target": "new",
                        "context": context,
                        "flags": {"mode": "readonly" if readonly else "edit"},
                    }
                )
                return action

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "ERROR!",
                "message": "The Manager field must be filled-up.",
                "sticky": False,
                "type": "danger",
            },
        }
