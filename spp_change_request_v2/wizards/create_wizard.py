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

    search_text = fields.Char(string="Search Registrant")
    search_results_html = fields.Html(
        string="Search Results",
        sanitize=False,
    )

    # Bridge fields: JS writes integers here, onchange handles the logic
    _selected_partner_id = fields.Integer(string="Selected Partner ID")
    _search_page = fields.Integer(string="Search Page", default=0)

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
                lines = []

                # Line 1: Name + Type
                name = escape(reg.name or "Unknown")
                if reg.is_group:
                    member_count = (
                        len(reg.group_membership_ids)
                        if hasattr(reg, "group_membership_ids")
                        else 0
                    )
                    type_badge = Markup(
                        "<span class='text-muted ms-2'>"
                        "<i class='fa fa-users me-1'></i>{} members</span>"
                    ).format(member_count)
                else:
                    type_badge = Markup(
                        "<span class='text-muted ms-2'>"
                        "<i class='fa fa-user me-1'></i>Individual</span>"
                    )
                lines.append(
                    Markup("<div><strong>{}</strong>{}</div>").format(
                        name, type_badge
                    )
                )

                # Line 2: All IDs
                if hasattr(reg, "reg_ids") and reg.reg_ids:
                    id_parts = []
                    for rid in reg.reg_ids:
                        if rid.value:
                            label = rid.id_type_as_str or "ID"
                            id_parts.append(
                                Markup(
                                    "<span class='badge text-bg-light border me-1'>"
                                    "{}: {}</span>"
                                ).format(escape(label), escape(rid.value))
                            )
                    if id_parts:
                        lines.append(
                            Markup("<div class='mt-1'>{}</div>").format(
                                Markup("").join(id_parts)
                            )
                        )

                rec.registrant_info_html = Markup("").join(lines)
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
    # SEARCH ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange("_selected_partner_id")
    def _onchange_selected_partner(self):
        """Convert the bridge integer to a Many2one registrant_id."""
        if self._selected_partner_id:
            self.registrant_id = self.env["res.partner"].browse(
                self._selected_partner_id
            )

    _SEARCH_PAGE_SIZE = 10

    @api.onchange("search_text")
    def _onchange_search_text(self):
        """Reset page and run search when text changes."""
        self.search_results_html = False
        self.registrant_id = False
        self._search_page = 0

        if not self.search_text or len(self.search_text) < 2:
            return

        self._render_search_results()

    @api.onchange("_search_page")
    def _onchange_search_page(self):
        """Re-render results when page changes."""
        if self.search_text and len(self.search_text) >= 2:
            self._render_search_results()

    def _get_search_domain(self):
        """Build the search domain based on search text and target type."""
        domain = [("is_registrant", "=", True)]
        if self.request_type_id and self.request_type_id.target_type:
            target = self.request_type_id.target_type
            if target == "individual":
                domain.append(("is_group", "=", False))
            elif target == "group":
                domain.append(("is_group", "=", True))
        return domain + [
            "|",
            ("name", "ilike", self.search_text),
            ("reg_ids.value", "ilike", self.search_text),
        ]

    def _render_search_results(self):
        """Search and render paginated HTML results."""
        search_domain = self._get_search_domain()
        total = self.env["res.partner"].search_count(search_domain)

        if not total:
            self.search_results_html = Markup(
                "<p class='text-muted'>No registrants found.</p>"
            )
            return

        page = self._search_page or 0
        page_size = self._SEARCH_PAGE_SIZE
        max_page = (total - 1) // page_size
        page = min(page, max_page)

        offset = page * page_size
        partners = self.env["res.partner"].search(
            search_domain, limit=page_size, offset=offset
        )

        rows = []
        for p in partners:
            # Build ALL IDs in "TypeName (value)" format, show max 2
            id_parts = []
            if p.reg_ids:
                for rid in p.reg_ids:
                    if rid.value:
                        label = rid.id_type_as_str or "ID"
                        id_parts.append(f"{label} ({rid.value})")
            if not id_parts:
                id_html = Markup("")
                id_title = ""
            elif len(id_parts) <= 2:
                id_html = escape(", ".join(id_parts))
                id_title = ""
            else:
                visible = escape(", ".join(id_parts[:2]))
                extra = len(id_parts) - 2
                id_html = Markup(
                    '{} <span class="badge text-bg-secondary ms-1">'
                    "+{} <i class='fa fa-info-circle'></i></span>"
                ).format(visible, extra)
                id_title = ", ".join(id_parts)
            ptype = (
                '<i class="fa fa-users"></i> Group'
                if p.is_group
                else '<i class="fa fa-user"></i> Individual'
            )
            rows.append(
                Markup(
                    '<tr class="o_cr_search_result" style="cursor:pointer"'
                    ' data-partner-id="{}" data-partner-name="{}">'
                    "<td>{}</td>"
                    '<td title="{}">{}</td>'
                    "<td>{}</td></tr>"
                ).format(
                    p.id,
                    escape(p.name or ""),
                    escape(p.name or ""),
                    escape(id_title),
                    id_html,
                    Markup(ptype),
                )
            )

        table = Markup(
            '<table class="table table-hover table-sm mb-0 w-100">'
            "<thead><tr><th>Name</th><th>ID</th><th>Type</th></tr></thead>"
            "<tbody>{}</tbody></table>"
        ).format(Markup("").join(rows))

        # Pagination header
        start = offset + 1
        end = min(offset + page_size, total)
        prev_cls = "text-muted" if page == 0 else "o_cr_page_prev"
        next_cls = "text-muted" if page >= max_page else "o_cr_page_next"
        pagination = Markup(
            '<div class="d-flex justify-content-between align-items-center mb-2 px-1">'
            '<small class="text-muted">{}-{} of {}</small>'
            "<div>"
            '<a class="{} me-3" style="cursor:pointer" data-page="{}">← Previous</a>'
            '<a class="{}" style="cursor:pointer" data-page="{}">Next →</a>'
            "</div></div>"
        ).format(start, end, total, prev_cls, page - 1, next_cls, page + 1)

        self.search_results_html = pagination + table

    def action_clear_registrant(self):
        """Clear selected registrant, re-run search, and reopen wizard."""
        self.ensure_one()
        self._selected_partner_id = False
        self.registrant_id = False
        # Re-run search with existing search_text to repopulate results
        self._onchange_search_text()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Change Request"),
            "res_model": "spp.cr.create.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

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

        # Close wizard modal and open detail form using client action
        # The client action ensures the modal is fully closed before navigating
        detail = cr.get_detail()
        if detail:
            view_id = self.request_type_id.get_detail_form_view_id()
            return {
                "type": "ir.actions.client",
                "tag": "open_cr_close_modal",
                "params": {
                    "name": _("Change Request Details"),
                    "res_model": cr.detail_res_model,
                    "res_id": detail.id,
                    "view_id": view_id,
                    "context": {
                        "create": False,
                        "delete": False,
                        "form_view_initial_mode": "edit",
                    },
                },
            }

        # Fallback: open CR form if no detail model configured
        return {
            "type": "ir.actions.client",
            "tag": "open_cr_close_modal",
            "params": {
                "name": _("Change Request"),
                "res_model": "spp.change.request",
                "res_id": cr.id,
                "context": {
                    "form_view_initial_mode": "edit",
                },
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
        """Clear registrant and search if type changes."""
        self.search_text = False
        if self.request_type_id and self.registrant_id:
            target = self.request_type_id.target_type
            is_group = self.registrant_id.is_group
            if (target == "individual" and is_group) or (target == "group" and not is_group):
                self.registrant_id = False
