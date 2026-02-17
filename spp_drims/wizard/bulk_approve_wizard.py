# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DrimsBulkApproveWizard(models.TransientModel):
    _name = "spp.drims.bulk.approve.wizard"
    _description = "DRIMS Bulk Approve Wizard"

    request_ids = fields.Many2many(
        "spp.drims.request",
        string="Requests to Approve",
        required=True,
    )
    request_count = fields.Integer(
        compute="_compute_summary",
    )
    total_value = fields.Float(
        compute="_compute_summary",
    )
    summary = fields.Html(
        compute="_compute_summary",
    )

    @api.depends("request_ids")
    def _compute_summary(self):
        for wizard in self:
            requests = wizard.request_ids
            wizard.request_count = len(requests)
            wizard.total_value = sum(requests.mapped("total_value"))

            # Build summary HTML
            priority_counts = {}
            for req in requests:
                priority = req.priority_id.display if req.priority_id else _("No Priority")
                priority_counts[priority] = priority_counts.get(priority, 0) + 1

            summary_lines = [f"<li><b>{count}</b> {priority}</li>" for priority, count in priority_counts.items()]
            wizard.summary = f"""
                <div>
                    <p><b>{wizard.request_count}</b> requests totaling
                       <b>{wizard.total_value:,.2f}</b></p>
                    <ul>{"".join(summary_lines)}</ul>
                </div>
            """

    def action_approve(self):
        """Approve all selected requests."""
        self.ensure_one()
        if not self.request_ids:
            raise UserError(_("No requests selected."))

        approved_count = 0
        for request in self.request_ids:
            if request.approval_state == "pending":
                request.action_approve()
                approved_count += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Approval Complete"),
                "message": _("%d requests approved.") % approved_count,
                "type": "success",
                "sticky": False,
            },
        }

    def action_reject(self):
        """Open rejection wizard for bulk rejection."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Requests"),
            "res_model": "spp.drims.bulk.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_request_ids": self.request_ids.ids,
            },
        }


class DrimsBulkRejectWizard(models.TransientModel):
    _name = "spp.drims.bulk.reject.wizard"
    _description = "DRIMS Bulk Reject Wizard"

    request_ids = fields.Many2many(
        "spp.drims.request",
        string="Requests to Reject",
        required=True,
    )
    reason = fields.Text(
        string="Rejection Reason",
        required=True,
    )

    def action_reject(self):
        """Reject all selected requests with reason."""
        self.ensure_one()
        if not self.reason:
            raise UserError(_("Please provide a rejection reason."))

        rejected_count = 0
        for request in self.request_ids:
            if request.approval_state == "pending":
                request.rejection_reason = self.reason
                request.action_reject()
                rejected_count += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Rejection Complete"),
                "message": _("%d requests rejected.") % rejected_count,
                "type": "warning",
                "sticky": False,
            },
        }
