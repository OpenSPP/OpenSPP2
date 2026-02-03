"""Batch approval wizard for Change Requests.

Allows validators to approve, reject, or request changes on multiple
change requests at once with a single comment.
"""

import logging

from markupsafe import Markup, escape

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRBatchApprovalWizard(models.TransientModel):
    """Wizard for batch approval operations on change requests."""

    _name = "spp.cr.batch.approval.wizard"
    _description = "Batch Approval Wizard"

    # ══════════════════════════════════════════════════════════════════════════
    # FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    line_ids = fields.One2many(
        "spp.cr.batch.approval.line",
        "wizard_id",
        string="Change Requests",
    )

    # Computed counts
    total_count = fields.Integer(
        compute="_compute_counts",
        string="Total",
    )
    valid_count = fields.Integer(
        compute="_compute_counts",
        string="Valid",
    )
    invalid_count = fields.Integer(
        compute="_compute_counts",
        string="Invalid",
    )

    # Action settings
    action_type = fields.Selection(
        [
            ("approve", "Approve"),
            ("reject", "Decline"),
            ("revision", "Request Changes"),
        ],
        default="approve",
        required=True,
        string="Action",
    )

    comment = fields.Text(
        string="Comment",
        help="Comment to apply to all selected change requests",
    )

    # Results
    result_html = fields.Html(
        compute="_compute_result_html",
        string="Results",
    )
    success_count = fields.Integer(
        string="Successful",
        readonly=True,
    )
    failed_count = fields.Integer(
        string="Failed",
        readonly=True,
    )
    show_results = fields.Boolean(
        default=False,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # DEFAULT
    # ══════════════════════════════════════════════════════════════════════════

    @api.model
    def default_get(self, fields_list):
        """Initialize wizard with selected change requests."""
        res = super().default_get(fields_list)

        active_ids = self.env.context.get("active_ids", [])
        if active_ids and "line_ids" in fields_list:
            crs = self.env["spp.change.request"].browse(active_ids)
            # Prefetch all needed fields in a single query to avoid N+1
            crs.read(["approval_state", "can_approve", "display_state"])
            lines = []
            for cr in crs:
                can_process = cr.approval_state == "pending" and cr.can_approve
                lines.append(
                    Command.create(
                        {
                            "change_request_id": cr.id,
                            "can_process": can_process,
                            "error_message": "" if can_process else self._get_error_message(cr),
                        }
                    )
                )
            res["line_ids"] = lines

        return res

    def _get_error_message(self, cr):
        """Get error message explaining why CR cannot be processed.

        Note: Plain strings are used here instead of _() to avoid translation
        context issues during default_get() in test scenarios.
        """
        if cr.approval_state != "pending":
            return f"Not pending approval (state: {cr.display_state})"
        if not cr.can_approve:
            return "You are not authorized to approve this request"
        return ""

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends("line_ids", "line_ids.can_process")
    def _compute_counts(self):
        for rec in self:
            rec.total_count = len(rec.line_ids)
            rec.valid_count = len(rec.line_ids.filtered("can_process"))
            rec.invalid_count = rec.total_count - rec.valid_count

    @api.depends("line_ids", "line_ids.result_status", "line_ids.result_message")
    def _compute_result_html(self):
        for rec in self:
            if not rec.show_results:
                rec.result_html = ""
                continue

            # Prefetch related CR data in batch to avoid N+1 queries
            cr_ids = rec.line_ids.mapped("change_request_id")
            if cr_ids:
                cr_ids.read(["name", "request_type_id"])
                # Also prefetch request_type names
                cr_ids.mapped("request_type_id").read(["name"])

            lines = []
            for line in rec.line_ids:
                if line.result_status == "success":
                    icon = "check-circle text-success"
                    status_text = str(_("Completed"))
                elif line.result_status == "error":
                    icon = "times-circle text-danger"
                    status_text = str(line.result_message or _("Failed"))
                else:
                    icon = "minus-circle text-muted"
                    status_text = str(_("Skipped"))

                # Escape user-provided data to prevent XSS
                cr_name = escape(line.change_request_id.name or "")
                cr_type_name = escape(line.change_request_id.request_type_id.name or "")
                status_text_escaped = escape(status_text)

                lines.append(
                    Markup("""
                    <tr>
                        <td><i class="fa fa-{icon} me-2"></i></td>
                        <td><strong>{name}</strong></td>
                        <td>{type_name}</td>
                        <td>{status}</td>
                    </tr>
                """).format(icon=icon, name=cr_name, type_name=cr_type_name, status=status_text_escaped)
                )

            rec.result_html = Markup("""
                <table class="table table-sm">
                    <thead>
                        <tr><th></th><th>Reference</th><th>Type</th><th>Result</th></tr>
                    </thead>
                    <tbody>{}</tbody>
                </table>
            """).format(Markup("").join(lines))

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_confirm(self):
        """Execute the batch action."""
        self.ensure_one()

        if not self.valid_count:
            raise UserError(_("No valid change requests to process."))

        valid_lines = self.line_ids.filtered("can_process")
        success_count = 0
        failed_count = 0

        for line in valid_lines:
            cr = line.change_request_id
            try:
                if self.action_type == "approve":
                    # action_approve already has permission checks
                    cr.action_approve(comment=self.comment)
                elif self.action_type == "reject":
                    if not self.comment:
                        raise UserError(_("A reason is required for declining requests."))
                    # Check permission before calling _do_reject
                    if not cr.can_reject:
                        raise UserError(_("You are not authorized to decline this request."))
                    cr._do_reject(self.comment)
                elif self.action_type == "revision":
                    if not self.comment:
                        raise UserError(_("Notes are required when requesting changes."))
                    # Check permission before calling _do_request_revision
                    if not cr.can_reject:
                        raise UserError(_("You are not authorized to request changes on this request."))
                    cr._do_request_revision(self.comment)

                line.result_status = "success"
                success_count += 1

            except Exception as e:
                _logger.warning("Batch action failed for CR %s: %s", cr.name, str(e))
                line.result_status = "error"
                line.result_message = str(e)
                failed_count += 1

        # Mark skipped lines
        for line in self.line_ids.filtered(lambda l: not l.can_process):
            line.result_status = "skipped"

        self.success_count = success_count
        self.failed_count = failed_count
        self.show_results = True

        # Reopen wizard to show results
        return {
            "type": "ir.actions.act_window",
            "name": _("Batch Action Results"),
            "res_model": "spp.cr.batch.approval.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("spp_change_request_v2.view_spp_cr_batch_approval_wizard_form_results").id,
            "target": "new",
        }

    def action_done(self):
        """Close the wizard and refresh the list."""
        return {"type": "ir.actions.act_window_close"}


class SPPCRBatchApprovalLine(models.TransientModel):
    """Line item for batch approval wizard."""

    _name = "spp.cr.batch.approval.line"
    _description = "Batch Approval Line"

    wizard_id = fields.Many2one(
        "spp.cr.batch.approval.wizard",
        required=True,
        ondelete="cascade",
    )

    change_request_id = fields.Many2one(
        "spp.change.request",
        string="Change Request",
        required=True,
        readonly=True,
    )

    # Related fields for display
    cr_name = fields.Char(
        related="change_request_id.name",
        string="Reference",
    )
    cr_type = fields.Char(
        related="change_request_id.request_type_id.name",
        string="Type",
    )
    registrant_name = fields.Char(
        related="change_request_id.registrant_id.name",
        string="Registrant",
    )
    document_count = fields.Integer(
        compute="_compute_document_count",
        string="Documents",
    )

    # Validation
    can_process = fields.Boolean(
        default=True,
    )
    error_message = fields.Char()

    # Results
    result_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("success", "Success"),
            ("error", "Error"),
            ("skipped", "Skipped"),
        ],
        default="pending",
    )
    result_message = fields.Char()

    @api.depends("change_request_id")
    def _compute_document_count(self):
        # Batch prefetch document_ids to avoid N+1 queries
        cr_ids = self.mapped("change_request_id")
        if cr_ids:
            cr_ids.read(["document_ids"])
        for rec in self:
            rec.document_count = len(rec.change_request_id.document_ids)
