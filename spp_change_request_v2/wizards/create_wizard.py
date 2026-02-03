"""Creation wizard for Change Requests.

Provides a simple 1-step wizard for creating change requests:
- Select type (required)
- Select registrant (required, shown after type selection)
- Click "Create" to create draft CR and open full form

The wizard focuses on quick selection. Actual details are filled
in the full CR form view after creation.
"""

import logging

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRCreateWizard(models.TransientModel):
    """Simple wizard for creating change requests."""

    _name = "spp.cr.create.wizard"
    _description = "Create Change Request Wizard"

    # ══════════════════════════════════════════════════════════════════════════
    # TYPE SELECTION
    # ══════════════════════════════════════════════════════════════════════════

    request_type_id = fields.Many2one(
        "spp.change.request.type",
        string="Request Type",
        domain="[('active', '=', True)]",
    )

    # For filtering types by category
    type_category = fields.Selection(
        [
            ("all", "All Types"),
            ("household", "Household Changes"),
            ("information", "Information Updates"),
            ("status", "Status Changes"),
        ],
        string="Category",
        default="all",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # REGISTRANT SELECTION
    # ══════════════════════════════════════════════════════════════════════════

    registrant_id = fields.Many2one(
        "res.partner",
        string="Registrant",
    )

    registrant_domain = fields.Char(
        compute="_compute_registrant_domain",
        string="Registrant Domain",
    )

    # Display info for selected registrant
    registrant_info_html = fields.Html(
        compute="_compute_registrant_info",
        string="Registrant Info",
    )

    # Flag to check if registrant is required/visible
    show_registrant = fields.Boolean(
        compute="_compute_show_registrant",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # FREEZE PERIOD CHECK
    # ══════════════════════════════════════════════════════════════════════════

    is_frozen = fields.Boolean(
        compute="_compute_freeze_status",
    )
    freeze_message = fields.Html(
        compute="_compute_freeze_status",
        string="Freeze Status",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # DEFAULT VALUES
    # ══════════════════════════════════════════════════════════════════════════

    @api.model
    def default_get(self, fields_list):
        """Pre-fill registrant if opened from registrant form."""
        res = super().default_get(fields_list)

        # Check if opened from a registrant context
        if self.env.context.get("active_model") == "res.partner":
            active_id = self.env.context.get("active_id")
            if active_id:
                partner = self.env["res.partner"].browse(active_id)
                if partner.exists() and partner.is_registrant:
                    res["registrant_id"] = partner.id

        return res

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED METHODS
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends("request_type_id")
    def _compute_show_registrant(self):
        for rec in self:
            rec.show_registrant = bool(rec.request_type_id)

    @api.depends("request_type_id")
    def _compute_registrant_domain(self):
        for rec in self:
            base_domain = [("is_registrant", "=", True)]
            if rec.request_type_id and rec.request_type_id.target_type:
                target = rec.request_type_id.target_type
                if target == "individual":
                    base_domain.append(("is_group", "=", False))
                elif target == "group":
                    base_domain.append(("is_group", "=", True))
            rec.registrant_domain = str(base_domain)

    @api.depends("registrant_id")
    def _compute_registrant_info(self):
        for rec in self:
            if rec.registrant_id:
                reg = rec.registrant_id
                info_parts = []

                # Get primary ID if available (from reg_ids)
                primary_id = ""
                if hasattr(reg, "reg_ids") and reg.reg_ids:
                    first_id = reg.reg_ids[0]
                    if first_id.value:
                        primary_id = first_id.value

                # Build compact single-line info
                # Format: Name (ID) - Type info - Address
                if primary_id:
                    name_part = Markup("<strong>{}</strong> <span class='text-muted'>({})</span>").format(
                        escape(reg.name or "Unknown"), escape(primary_id)
                    )
                else:
                    name_part = Markup("<strong>{}</strong>").format(escape(reg.name or "Unknown"))

                info_parts.append(name_part)

                # Type indicator with icon
                if reg.is_group:
                    member_count = len(reg.group_membership_ids) if hasattr(reg, "group_membership_ids") else 0
                    info_parts.append(
                        Markup(
                            "<span class='text-muted ms-2'><i class='fa fa-users me-1'></i>{} members</span>"
                        ).format(member_count)
                    )
                else:
                    info_parts.append(
                        Markup("<span class='text-muted ms-2'><i class='fa fa-user me-1'></i>Individual</span>")
                    )

                # Address on same line if available
                if reg.street:
                    addr = escape(reg.street)
                    if reg.city:
                        addr = Markup("{}, {}").format(escape(reg.street), escape(reg.city))
                    info_parts.append(
                        Markup("<span class='text-muted ms-2'><i class='fa fa-map-marker me-1'></i>{}</span>").format(
                            addr
                        )
                    )

                rec.registrant_info_html = Markup(" ").join(info_parts)
            else:
                rec.registrant_info_html = ""

    @api.depends("request_type_id")
    def _compute_freeze_status(self):
        for rec in self:
            rec.is_frozen = False
            rec.freeze_message = ""

            if rec.request_type_id and rec.request_type_id.approval_definition_id:
                definition = rec.request_type_id.approval_definition_id
                if definition.is_respect_system_freeze:
                    freeze_status = self.env["spp.approval.freeze"].is_frozen(
                        model_name="spp.change.request",
                    )
                    if freeze_status.get("frozen"):
                        rec.is_frozen = True
                        reason = escape(freeze_status.get("reason", "System is frozen"))
                        rec.freeze_message = Markup("""
                            <div class="alert alert-warning mb-0">
                                <h5 class="mb-1"><i class="fa fa-pause-circle me-2"></i>Submissions Paused</h5>
                                <p class="mb-0">{}</p>
                                <small class="text-muted">
                                    You can still create drafts. Submissions will resume after the freeze period.
                                </small>
                            </div>
                        """).format(reason)

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_create_draft(self):
        """Create a draft change request and open its detail form for editing."""
        self.ensure_one()

        if not self.request_type_id:
            raise UserError(_("Please select a request type."))
        if not self.registrant_id:
            raise UserError(_("Please select a registrant."))

        # Validate registrant matches target type
        target = self.request_type_id.target_type
        is_group = self.registrant_id.is_group
        if target == "individual" and is_group:
            raise UserError(_("This request type requires an individual registrant, not a group."))
        if target == "group" and not is_group:
            raise UserError(_("This request type requires a group registrant, not an individual."))

        # Create the draft CR (this auto-creates the detail record)
        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.request_type_id.id,
                "registrant_id": self.registrant_id.id,
                "source_type": "manual",
            }
        )

        # Open the detail form directly for editing
        detail = cr.get_detail()
        if detail:
            view_id = self.request_type_id.get_detail_form_view_id()
            return {
                "type": "ir.actions.act_window",
                "name": "Change Request Details",
                "res_model": cr.detail_res_model,
                "res_id": detail.id,
                "view_mode": "form",
                "view_id": view_id,
                "target": "current",
                "context": {
                    "create": False,
                    "delete": False,
                    "form_view_initial_mode": "edit",
                },
            }

        # Fallback: open CR form if no detail model configured
        return {
            "type": "ir.actions.act_window",
            "name": "Change Request",
            "res_model": "spp.change.request",
            "res_id": cr.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "form_view_initial_mode": "edit",
            },
        }

    def action_cancel(self):
        """Cancel and close the wizard."""
        return {"type": "ir.actions.act_window_close"}

    # ══════════════════════════════════════════════════════════════════════════
    # ONCHANGE
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange("request_type_id")
    def _onchange_request_type(self):
        """Clear registrant if it doesn't match the new target type."""
        if self.request_type_id and self.registrant_id:
            target = self.request_type_id.target_type
            is_group = self.registrant_id.is_group
            if (target == "individual" and is_group) or (target == "group" and not is_group):
                self.registrant_id = False
