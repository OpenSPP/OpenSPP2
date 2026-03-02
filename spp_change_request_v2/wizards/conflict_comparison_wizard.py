"""Conflict comparison wizard for Change Requests.

Allows validators to compare conflicting change requests side-by-side
and make decisions about which to approve/reject.
"""

import logging

from markupsafe import Markup, escape

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRConflictComparisonWizard(models.TransientModel):
    """Wizard for comparing and resolving conflicting change requests."""

    _name = "spp.cr.conflict.comparison.wizard"
    _description = "Conflict Comparison Wizard"

    # ══════════════════════════════════════════════════════════════════════════
    # FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    # Primary CR that triggered the comparison
    primary_cr_id = fields.Many2one(
        "spp.change.request",
        string="Primary Request",
        required=True,
        readonly=True,
    )

    # All CRs being compared (including primary)
    line_ids = fields.One2many(
        "spp.cr.conflict.comparison.line",
        "wizard_id",
        string="Conflicting Requests",
    )

    # Common info
    registrant_id = fields.Many2one(
        related="primary_cr_id.registrant_id",
        string="Registrant",
    )
    registrant_name = fields.Char(
        related="registrant_id.name",
    )
    conflict_field = fields.Char(
        string="Conflicting Field",
        help="The field that has conflicting values",
    )
    current_value = fields.Char(
        string="Current Value",
        help="Current value in the registrant record",
    )

    # Comparison data
    comparison_html = fields.Html(
        compute="_compute_comparison_html",
        string="Comparison",
    )

    # Quick actions
    quick_action = fields.Selection(
        [
            ("approve_latest", "Approve Latest, Decline Others"),
            ("approve_oldest", "Approve Oldest, Decline Others"),
            ("approve_selected", "Apply Selected Decisions"),
        ],
        string="Quick Action",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # DEFAULT
    # ══════════════════════════════════════════════════════════════════════════

    @api.model
    def default_get(self, fields_list):
        """Initialize wizard with conflicting change requests."""
        res = super().default_get(fields_list)

        active_id = self.env.context.get("active_id")
        if active_id:
            primary_cr = self.env["spp.change.request"].browse(active_id)
            res["primary_cr_id"] = primary_cr.id

            # Find all conflicting CRs
            conflicting_crs = self._get_conflicting_crs(primary_cr)

            lines = []
            for cr in [primary_cr] + list(conflicting_crs):
                lines.append(
                    Command.create(
                        {
                            "change_request_id": cr.id,
                            "is_primary": cr.id == primary_cr.id,
                            "decision": "none",
                        }
                    )
                )
            res["line_ids"] = lines

            # Determine conflict field from the conflict detection result
            if primary_cr.conflicting_cr_ids:
                # Use the type's conflict rules to determine which field caused the conflict
                if primary_cr.request_type_id and primary_cr.request_type_id.conflict_rule_ids:
                    first_rule = primary_cr.request_type_id.conflict_rule_ids[:1]
                    if first_rule and first_rule.field_to_check:
                        res["conflict_field"] = first_rule.field_to_check

        return res

    def _get_conflicting_crs(self, primary_cr):
        """Get all CRs that conflict with the primary CR."""
        conflicting_ids = set()

        # From the Many2many field populated by conflict detection
        if primary_cr.conflicting_cr_ids:
            for cr in primary_cr.conflicting_cr_ids:
                conflicting_ids.add(cr.id)

        # Also find CRs that have this CR in their conflicting list
        reverse_conflicts = self.env["spp.change.request"].search([("conflicting_cr_ids", "in", [primary_cr.id])])
        for cr in reverse_conflicts:
            conflicting_ids.add(cr.id)

        return self.env["spp.change.request"].browse(list(conflicting_ids))

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends("line_ids", "conflict_field", "current_value")
    def _compute_comparison_html(self):
        for rec in self:
            if not rec.line_ids:
                rec.comparison_html = ""
                continue

            # Prefetch related CR data in batch to avoid N+1 queries
            cr_ids = rec.line_ids.mapped("change_request_id")
            if cr_ids:
                cr_ids.read(["name", "create_date", "create_uid", "document_ids"])
                # Also prefetch creator names
                cr_ids.mapped("create_uid").read(["name"])

            # Build comparison table - headers are static so no escaping needed
            headers = [
                "Request",
                "Submitted",
                "By",
                "Proposed Value",
                "Documents",
                "Decision",
            ]
            header_html = Markup("").join(Markup("<th>{}</th>").format(h) for h in headers)

            rows = []
            for line in rec.line_ids.sorted(key=lambda l: l.change_request_id.create_date):
                cr = line.change_request_id
                proposed_value = rec._get_proposed_value(cr)
                doc_count = len(cr.document_ids)

                primary_badge = (
                    Markup("<span class='badge bg-primary ms-1'>Primary</span>") if line.is_primary else Markup("")
                )

                decision_class = {
                    "approve": "success",
                    "reject": "danger",
                    "none": "secondary",
                }.get(line.decision, "secondary")

                # Escape user-provided data to prevent XSS
                cr_name = escape(cr.name or "")
                create_date_str = cr.create_date.strftime("%Y-%m-%d %H:%M") if cr.create_date else ""
                creator_name = escape(cr.create_uid.name if cr.create_uid else "")
                proposed_value_escaped = escape(str(proposed_value))
                decision_label = escape(line.decision or "Pending")

                rows.append(
                    Markup("""
                    <tr>
                        <td><strong>{name}</strong>{badge}</td>
                        <td>{date}</td>
                        <td>{creator}</td>
                        <td>{proposed}</td>
                        <td><i class="fa fa-paperclip me-1"></i>{docs}</td>
                        <td><span class="badge bg-{decision_class}">{decision}</span></td>
                    </tr>
                """).format(
                        name=cr_name,
                        badge=primary_badge,
                        date=create_date_str,
                        creator=creator_name,
                        proposed=proposed_value_escaped,
                        docs=doc_count,
                        decision_class=decision_class,
                        decision=decision_label,
                    )
                )

            rec.comparison_html = Markup("""
                <div class="table-responsive">
                    <table class="table table-sm table-hover">
                        <thead class="table-light">
                            <tr>{headers}</tr>
                        </thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>
            """).format(headers=header_html, rows=Markup("").join(rows))

    def _get_proposed_value(self, cr):
        """Get the proposed value from a CR's detail record."""
        if not self.conflict_field:
            return _("(View details)")

        detail = cr.get_detail()
        if detail and hasattr(detail, self.conflict_field):
            value = getattr(detail, self.conflict_field)
            if hasattr(value, "name"):
                return value.name
            return str(value) if value else _("(empty)")

        return _("N/A")

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_approve_latest_decline_others(self):
        """Approve the most recent CR, decline all others."""
        self.ensure_one()

        sorted_lines = self.line_ids.sorted(key=lambda l: l.change_request_id.create_date, reverse=True)

        for i, line in enumerate(sorted_lines):
            if i == 0:
                line.decision = "approve"
            else:
                line.decision = "reject"

        return self._apply_decisions()

    def action_approve_oldest_decline_others(self):
        """Approve the oldest CR, decline all others."""
        self.ensure_one()

        sorted_lines = self.line_ids.sorted(key=lambda l: l.change_request_id.create_date)

        for i, line in enumerate(sorted_lines):
            if i == 0:
                line.decision = "approve"
            else:
                line.decision = "reject"

        return self._apply_decisions()

    def action_apply_decisions(self):
        """Apply the selected decisions to each CR."""
        self.ensure_one()
        return self._apply_decisions()

    def _apply_decisions(self):
        """Execute all pending decisions."""
        results = {"approved": [], "rejected": [], "errors": []}

        for line in self.line_ids:
            cr = line.change_request_id
            try:
                if line.decision == "approve":
                    if cr.approval_state == "pending":
                        if not cr.can_approve:
                            raise UserError(_("You are not authorized to approve %s.") % cr.name)
                        cr.action_approve(comment=_("Approved via conflict resolution"))
                        results["approved"].append(cr.name)
                elif line.decision == "reject":
                    if cr.approval_state == "pending":
                        if not cr.can_reject:
                            raise UserError(_("You are not authorized to decline %s.") % cr.name)
                        cr._do_reject(_("Declined via conflict resolution - another request approved"))
                        results["rejected"].append(cr.name)
            except Exception as e:
                _logger.warning("Failed to process CR ID %s: %s", cr.id, str(e))
                results["errors"].append(f"{cr.name}: {str(e)}")

        # Show results notification
        # Note: Using plain strings to avoid translation context issues in test scenarios
        message_parts = []
        if results["approved"]:
            message_parts.append(f"Approved: {', '.join(results['approved'])}")
        if results["rejected"]:
            message_parts.append(f"Declined: {', '.join(results['rejected'])}")
        if results["errors"]:
            message_parts.append(f"Errors: {', '.join(results['errors'])}")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Conflict Resolution Complete",
                "message": "\n".join(message_parts) or "No changes made",
                "type": "success" if not results["errors"] else "warning",
                "sticky": bool(results["errors"]),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_cancel(self):
        """Close without making changes."""
        return {"type": "ir.actions.act_window_close"}


class SPPCRConflictComparisonLine(models.TransientModel):
    """Line item for conflict comparison wizard."""

    _name = "spp.cr.conflict.comparison.line"
    _description = "Conflict Comparison Line"

    wizard_id = fields.Many2one(
        "spp.cr.conflict.comparison.wizard",
        required=True,
        ondelete="cascade",
    )

    change_request_id = fields.Many2one(
        "spp.change.request",
        string="Change Request",
        required=True,
        readonly=True,
    )

    is_primary = fields.Boolean(
        default=False,
        help="Whether this is the primary CR that initiated the comparison",
    )

    # Related fields for display
    cr_name = fields.Char(
        related="change_request_id.name",
    )
    cr_type = fields.Char(
        related="change_request_id.request_type_id.name",
    )
    submitted_date = fields.Datetime(
        related="change_request_id.create_date",
    )
    submitted_by = fields.Char(
        related="change_request_id.create_uid.name",
    )
    document_count = fields.Integer(
        compute="_compute_document_count",
    )

    # Decision
    decision = fields.Selection(
        [
            ("none", "No Decision"),
            ("approve", "Approve"),
            ("reject", "Decline"),
        ],
        default="none",
        string="Decision",
    )

    @api.depends("change_request_id")
    def _compute_document_count(self):
        # Batch prefetch document_ids to avoid N+1 queries
        cr_ids = self.mapped("change_request_id")
        if cr_ids:
            cr_ids.read(["document_ids"])
        for rec in self:
            rec.document_count = len(rec.change_request_id.document_ids)
