import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SPPCRConflictWizard(models.TransientModel):
    """Wizard for resolving change request conflicts."""

    _name = "spp.cr.conflict.wizard"
    _description = "Change Request Conflict Resolution Wizard"

    # ══════════════════════════════════════════════════════════════════════════
    # BASIC FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    change_request_id = fields.Many2one(
        "spp.change.request",
        required=True,
        ondelete="cascade",
    )

    conflict_status = fields.Selection(
        related="change_request_id.conflict_status",
        readonly=True,
    )

    conflict_messages = fields.Text(
        related="change_request_id.conflict_messages",
        readonly=True,
    )

    conflicting_cr_ids = fields.Many2many(
        related="change_request_id.conflicting_cr_ids",
        readonly=True,
    )

    conflict_count = fields.Integer(
        related="change_request_id.conflict_count",
        readonly=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # RESOLUTION ACTION - User-friendly labels
    # ══════════════════════════════════════════════════════════════════════════

    resolution_action = fields.Selection(
        [
            ("view_details", "View the other request(s) first"),
            ("cancel_this", "Withdraw my request"),
            ("request_review", "Ask a supervisor to decide"),
            ("cancel_conflicting", "Withdraw the other request(s)"),
            ("wait", "Do nothing - wait for the other request"),
        ],
        default="view_details",
        required=True,
        string="What would you like to do?",
        help="Choose how to resolve the conflict between these requests",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SUPERVISOR APPROVAL FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    override_reason = fields.Text(
        string="Approval Justification",
        help="Explain why both requests can be processed (e.g., no actual conflict, both valid, etc.)",
    )

    can_override = fields.Boolean(
        compute="_compute_can_override",
    )

    @api.depends("change_request_id")
    def _compute_can_override(self):
        for rec in self:
            rec.can_override = self.env.user.has_group("spp_change_request_v2.group_cr_conflict_approver")

    # ══════════════════════════════════════════════════════════════════════════
    # CANCEL FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    crs_to_cancel = fields.Many2many(
        "spp.change.request",
        "spp_cr_conflict_wizard_cancel_rel",
        "wizard_id",
        "cr_id",
        string="Requests to Cancel",
        domain="[('id', 'in', conflicting_cr_ids)]",
    )

    cancel_reason = fields.Text(
        string="Reason",
        help="Reason for cancellation",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # COMPARISON HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    comparison_html = fields.Html(
        compute="_compute_comparison_html",
    )

    @api.depends("change_request_id", "conflicting_cr_ids")
    def _compute_comparison_html(self):
        for rec in self:
            if not rec.change_request_id or not rec.conflicting_cr_ids:
                rec.comparison_html = ""
                continue

            html = self._build_comparison_table(
                rec.change_request_id,
                rec.conflicting_cr_ids[:5],  # Limit to first 5
            )
            rec.comparison_html = html

    def _build_comparison_table(self, main_cr, conflicting_crs):
        """Build HTML comparison table with user-friendly styling."""
        rows = []

        # Calculate column count
        total_cols = 2 + len(conflicting_crs)  # Field + Your Request + Other CRs

        # Header row with better styling
        header = "<tr class='table-primary fw-bold'>"
        header += "<th style='min-width: 150px; max-width: 250px;'>Field</th>"
        header += "<th style='min-width: 200px;'>Your Request</th>"
        for cr in conflicting_crs:
            header += f"<th style='min-width: 200px;'>{cr.name}</th>"
        header += "</tr>"
        rows.append(header)

        # Basic info section
        rows.append(
            f"<tr class='table-light'><td colspan='{total_cols}'><strong>Request Information</strong></td></tr>"
        )

        rows.append(
            self._comparison_row(
                "Beneficiary",
                main_cr.registrant_id.name,
                [cr.registrant_id.name for cr in conflicting_crs],
            )
        )
        rows.append(
            self._comparison_row(
                "Request Type",
                main_cr.request_type_id.name,
                [cr.request_type_id.name for cr in conflicting_crs],
            )
        )
        rows.append(
            self._comparison_row(
                "Status",
                main_cr.display_state,
                [cr.display_state for cr in conflicting_crs],
            )
        )
        rows.append(
            self._comparison_row(
                "Submitted",
                self._format_datetime(main_cr.create_date),
                [self._format_datetime(cr.create_date) for cr in conflicting_crs],
            )
        )
        rows.append(
            self._comparison_row(
                "By",
                main_cr.create_uid.name,
                [cr.create_uid.name for cr in conflicting_crs],
            )
        )

        # Detail fields (only show fields with differences)
        main_detail = main_cr.get_detail()
        if main_detail:
            detail_rows = []
            for field_name, field_obj in main_detail._fields.items():
                # Skip system fields
                if field_name in (
                    "id",
                    "create_date",
                    "write_date",
                    "create_uid",
                    "write_uid",
                    "change_request_id",
                    "registrant_id",
                    "approval_state",
                    "is_applied",
                    "display_name",
                    "__last_update",
                ):
                    continue
                if not field_obj.store:
                    continue

                # Get formatted values
                main_value = self._format_field_value(main_detail, field_name, field_obj)
                conflicting_values = []
                has_conflict = False

                for cr in conflicting_crs:
                    cr_detail = cr.get_detail()
                    if cr_detail and field_name in cr_detail._fields:
                        value = self._format_field_value(cr_detail, field_name, field_obj)
                        conflicting_values.append(value)
                        if value != main_value and value and main_value:
                            has_conflict = True
                    else:
                        conflicting_values.append("-")

                # Only show fields that have values or conflicts
                if (main_value and main_value != "-") or has_conflict:
                    detail_rows.append(
                        self._comparison_row(
                            field_obj.string or field_name,
                            main_value,
                            conflicting_values,
                        )
                    )

            # Add detail section if there are any rows
            if detail_rows:
                rows.append(
                    f"<tr class='table-light'><td colspan='{total_cols}'><strong>Changes Being Made</strong></td></tr>"
                )
                rows.extend(detail_rows)

        # Build table with proper styling for horizontal scrolling
        table_style = "width: 100%; table-layout: auto; white-space: nowrap;"
        return f"""
        <div style="overflow-x: auto; max-width: 100%;">
            <table class='table table-bordered table-hover table-sm' style='{table_style}'>
                {"".join(rows)}
            </table>
        </div>
        """

    def _comparison_row(self, label, main_value, other_values):
        """Build a single comparison row with highlighting for differences."""
        # Escape HTML in values
        main_value_display = self._escape_html(str(main_value or "-"))
        row = f"<tr><td class='fw-bold text-muted'>{label}</td><td>{main_value_display}</td>"
        for val in other_values:
            style = ""
            val_display = self._escape_html(str(val or "-"))
            if val != main_value and val and main_value and val != "-" and main_value != "-":
                # Highlight differences with warning color
                style = " class='table-warning fw-bold'"
            row += f"<td{style}>{val_display}</td>"
        row += "</tr>"
        return row

    def _format_field_value(self, record, field_name, field_obj):
        """Format a field value for display."""
        try:
            value = getattr(record, field_name, None)

            # Handle empty values
            if value is False and field_obj.type != "boolean":
                return "-"
            if value is None:
                return "-"

            # Format based on field type
            if field_obj.type == "many2one":
                return value.display_name if value else "-"
            elif field_obj.type == "many2many":
                return ", ".join(value.mapped("display_name")) if value else "-"
            elif field_obj.type == "one2many":
                return f"{len(value)} item(s)" if value else "-"
            elif field_obj.type == "boolean":
                return "✓ Yes" if value else "✗ No"
            elif field_obj.type == "selection":
                if hasattr(field_obj, "selection"):
                    selection_dict = dict(field_obj.selection)
                    return selection_dict.get(value, str(value))
                return str(value)
            elif field_obj.type in ("date", "datetime"):
                return self._format_datetime(value) if value else "-"
            elif field_obj.type in ("float", "monetary"):
                return f"{value:.2f}" if value else "-"
            elif field_obj.type == "integer":
                return str(value) if value else "0"
            else:
                return str(value) if value else "-"
        except Exception as e:
            _logger.warning(f"Error formatting field {field_name}: {e}")
            return "-"

    def _format_datetime(self, dt_value):
        """Format datetime for display."""
        if not dt_value:
            return "-"
        try:
            # Format as "Jan 15, 2025 14:30"
            return dt_value.strftime("%b %d, %Y %H:%M")
        except Exception:
            return str(dt_value)[:16]

    def _escape_html(self, text):
        """Escape HTML special characters."""
        if not text or text == "-":
            return text
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_resolve(self):
        """Execute the selected resolution action."""
        self.ensure_one()

        if self.resolution_action == "view_details":
            return self.action_view_conflicting_crs()
        elif self.resolution_action == "request_review":
            return self._action_request_review()
        elif self.resolution_action == "cancel_conflicting":
            return self._action_cancel_conflicting()
        elif self.resolution_action == "cancel_this":
            return self._action_cancel_this()
        else:  # wait
            return {"type": "ir.actions.act_window_close"}

    def _action_request_review(self):
        """Request supervisor approval to proceed despite conflict."""
        if not self.can_override:
            raise UserError(
                _("Only supervisors can approve conflicting requests. Please contact your supervisor for assistance.")
            )

        if not self.override_reason or len(self.override_reason.strip()) < 10:
            raise ValidationError(
                _("Please explain why this request should proceed (at least 10 characters required).")
            )

        self.change_request_id.action_override_conflict(self.override_reason)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Approved to Proceed"),
                "message": _("This request has been approved. You can now submit it for processing."),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _action_cancel_conflicting(self):
        """Cancel selected conflicting CRs."""
        if not self.crs_to_cancel:
            raise ValidationError(_("Please select at least one request to cancel."))

        # Note: Use 'change_req' instead of 'cr' to avoid conflict with Odoo 19's
        # translation introspection which looks for 'cr' (cursor) in the call stack
        for change_req in self.crs_to_cancel:
            if change_req.approval_state not in ("draft", "pending"):
                raise UserError(
                    _(
                        "Cannot cancel request %(name)s because it has already been processed. "
                        "Only draft or pending requests can be cancelled.",
                        name=change_req.name,
                    )
                )
            # Check if user owns the CR or has validator rights
            if change_req.create_uid != self.env.user and not self.env.user.has_group(
                "spp_change_request_v2.group_cr_validator"
            ):
                raise UserError(
                    _(
                        "You cannot cancel request %(name)s because it was created by %(user)s. "
                        "You can only cancel your own requests, or contact a supervisor.",
                        name=change_req.name,
                        user=change_req.create_uid.name,
                    )
                )

        # Reject the selected CRs
        reason = self.cancel_reason or _("Cancelled due to conflict with %s") % self.change_request_id.name

        # Store values before any database operations might invalidate cursor
        count = len(self.crs_to_cancel)
        change_request = self.change_request_id

        # Pre-translate messages before deletions (avoid cursor invalidation issues)
        title = _("Requests Cancelled")
        message = _("%(count)d request(s) have been cancelled. Your request can now be submitted.") % {"count": count}

        for change_req in self.crs_to_cancel:
            if change_req.approval_state == "pending":
                # Use internal rejection method (not action_reject which opens wizard)
                change_req._do_reject(reason)
            else:  # draft
                # Delete detail record first to avoid FK violation
                detail = change_req.get_detail()
                if detail:
                    detail.unlink()
                change_req.unlink()

        # Re-check conflicts
        change_request._run_conflict_checks()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _action_cancel_this(self):
        """Cancel this CR."""
        # Note: Use 'change_req' instead of 'cr' to avoid conflict with Odoo 19's
        # translation introspection which looks for 'cr' (cursor) in the call stack
        change_req = self.change_request_id
        reason = self.cancel_reason or _("Cancelled due to conflicts")

        # Pre-translate messages before deletions (avoid cursor invalidation issues)
        title_cancelled = _("Request Cancelled")
        message_cancelled = _("Your change request has been cancelled.")
        title_list = _("Change Requests")

        if change_req.approval_state == "pending":
            # Use internal rejection method (not action_reject which opens wizard)
            change_req._do_reject(reason)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": title_cancelled,
                    "message": message_cancelled,
                    "type": "info",
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        elif change_req.approval_state == "draft":
            # Delete detail record first to avoid FK violation
            detail = change_req.get_detail()
            if detail:
                detail.unlink()
            change_req.unlink()
            return {
                "type": "ir.actions.act_window",
                "name": title_list,
                "res_model": "spp.change.request",
                "view_mode": "list,form",
                "target": "current",
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title_cancelled,
                "message": message_cancelled,
                "type": "info",
            },
        }

    def action_view_conflicting_crs(self):
        """Open list view of conflicting CRs."""
        self.ensure_one()
        return self.change_request_id.action_view_conflicts()

    def action_recheck(self):
        """Re-run conflict detection."""
        self.ensure_one()
        self.change_request_id._run_conflict_checks()
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
