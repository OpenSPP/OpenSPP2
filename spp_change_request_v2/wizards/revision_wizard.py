from odoo import _, models


class ApprovalRevisionWizard(models.TransientModel):
    _inherit = "spp.approval.revision.wizard"

    def action_request_revision(self):
        """Override to redirect to CR list with notification after requesting changes."""
        self.ensure_one()
        result = super().action_request_revision()

        if self.res_model == "spp.change.request":
            record = self.env[self.res_model].browse(self.res_id)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": _(
                        "%s %s has been sent back for revision.",
                        record.name,
                        record.request_type_id.name,
                    ),
                    "type": "warning",
                    "sticky": False,
                    "next": {
                        "type": "ir.actions.client",
                        "tag": "navigate_cr_list",
                    },
                },
            }

        return result
