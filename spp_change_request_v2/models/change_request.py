import logging

from markupsafe import escape as html_escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .frozen_value import normalize_frozen_value

_logger = logging.getLogger(__name__)


class SPPChangeRequest(models.Model):
    """Change request - base model with approval workflow."""

    _name = "spp.change.request"
    _description = "Change Request"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "spp.approval.mixin",
        "spp.cr.conflict.mixin",
    ]
    _order = "create_date desc"

    # ══════════════════════════════════════════════════════════════════════════
    # CORE FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        default="New",
        tracking=True,
    )

    request_type_id = fields.Many2one(
        "spp.change.request.type",
        string="Request Type",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    request_type_code = fields.Char(
        related="request_type_id.code",
        store=True,
        index=True,
    )
    allow_document_download = fields.Boolean(
        related="request_type_id.allow_document_download",
    )

    stage = fields.Selection(
        [
            ("details", "Edit Details"),
            ("documents", "Upload Documents"),
            ("review", "Review & Submit"),
        ],
        string="Stage",
        default="details",
        tracking=True,
    )

    is_cr_manager = fields.Boolean(
        compute="_compute_is_cr_manager",
    )

    def _compute_is_cr_manager(self):
        is_manager = self.env.user.has_group("spp_change_request_v2.group_cr_manager")
        for rec in self:
            rec.is_cr_manager = is_manager

    # ══════════════════════════════════════════════════════════════════════════
    # REGISTRANT & APPLICANT
    # ══════════════════════════════════════════════════════════════════════════

    registrant_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        index=True,
        tracking=True,
    )
    registrant_domain = fields.Char(
        compute="_compute_registrant_domain",
        store=False,
    )

    applicant_id = fields.Many2one(
        "res.partner",
        string="Applicant",
        help="Person submitting on behalf of registrant",
        domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
    )
    applicant_phone = fields.Char()

    # ══════════════════════════════════════════════════════════════════════════
    # DETAIL REFERENCE
    # ══════════════════════════════════════════════════════════════════════════

    detail_res_model = fields.Char(
        related="request_type_id.detail_model",
        store=True,
        string="Detail Model",
    )
    detail_res_id = fields.Many2oneReference(
        string="Detail Record",
        model_field="detail_res_model",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SOURCE TRACKING
    # ══════════════════════════════════════════════════════════════════════════

    source_type = fields.Selection(
        [
            ("manual", "Manual Entry"),
            ("event", "Event Data"),
            ("api", "External API"),
            ("import", "Bulk Import"),
        ],
        default="manual",
        readonly=True,
    )

    source_event_id = fields.Many2one("spp.event.data", readonly=True)
    source_reference = fields.Char(help="External reference ID")

    # ══════════════════════════════════════════════════════════════════════════
    # APPLICATION TRACKING
    # ══════════════════════════════════════════════════════════════════════════

    is_applied = fields.Boolean(default=False, readonly=True, tracking=True)
    applied_date = fields.Datetime(readonly=True)
    applied_by_id = fields.Many2one("res.users", readonly=True)
    apply_error = fields.Text(readonly=True)

    # ══════════════════════════════════════════════════════════════════════════
    # DYNAMIC APPROVAL
    # ══════════════════════════════════════════════════════════════════════════

    selected_field_name = fields.Char(
        string="Field Being Modified",
        readonly=True,
        help="The detail field selected for modification (set when detail is saved). "
        "Used by CEL conditions to determine the approval workflow.",
    )
    selected_field_old_value = fields.Char(
        string="Old Value",
        readonly=True,
        help="Human-readable old value of the selected field (from registrant). Stored for audit trail.",
    )
    selected_field_new_value = fields.Char(
        string="New Value",
        readonly=True,
        help="Human-readable new value of the selected field (from detail). Stored for audit trail.",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # LOG
    # ══════════════════════════════════════════════════════════════════════════

    log_ids = fields.One2many(
        "spp.change.request.log",
        "change_request_id",
        string="Change Request Log",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # DOCUMENTS & NOTES
    # ══════════════════════════════════════════════════════════════════════════

    dms_directory_id = fields.Many2one(
        "spp.dms.directory",
        string="Document Directory",
        readonly=True,
        ondelete="restrict",
        help="Automatically created directory for this change request's documents",
    )
    document_ids = fields.Many2many("spp.dms.file", string="Documents")
    description = fields.Text()
    notes = fields.Text(string="Internal Notes")

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED
    # ══════════════════════════════════════════════════════════════════════════

    display_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Under Review"),
            ("revision", "Needs Changes"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("applied", "Applied"),
        ],
        compute="_compute_display_state",
        store=True,
    )

    preview_html = fields.Html(
        string="Preview of Changes",
        compute="_compute_preview_html",
        sanitize=False,
    )
    review_comparison_html = fields.Html(
        string="Review Comparison",
        compute="_compute_review_comparison_html",
        sanitize=False,
    )
    preview_html_snapshot = fields.Html(
        string="Preview Snapshot",
        help="Stored snapshot of preview taken before applying changes",
        sanitize=False,
    )
    review_comparison_html_snapshot = fields.Html(
        string="Review Comparison Snapshot",
        help="Stored snapshot of review comparison taken before applying changes",
        sanitize=False,
    )
    preview_json_snapshot = fields.Text(
        string="Preview JSON Snapshot",
        help="Stored JSON snapshot of preview taken before applying changes",
    )
    review_documents_html = fields.Html(
        string="Review Documents",
        compute="_compute_review_documents_html",
        sanitize=False,
    )
    registrant_summary_html = fields.Html(
        string="Registrant Summary",
        compute="_compute_registrant_summary_html",
        sanitize=False,
    )
    is_creator = fields.Boolean(
        string="Is Creator",
        compute="_compute_is_creator",
        help="True if current user created this change request",
    )
    has_proposed_changes = fields.Boolean(
        string="Has Proposed Changes",
        compute="_compute_has_proposed_changes",
        help="True if there are proposed changes in the detail record",
    )
    multitier_approval_message = fields.Char(
        string="Multi-tier Approval Message",
        compute="_compute_multitier_approval_message",
        help="Message shown when awaiting next level approval in multi-tier workflow",
    )
    target_type_message = fields.Char(
        string="Target Type Message",
        compute="_compute_target_type_message",
        help="Message indicating what type of registrant this CR type applies to",
    )

    missing_required_document_ids = fields.Many2many(
        "spp.vocabulary.code",
        compute="_compute_missing_required_documents",
        string="Missing Required Documents",
    )
    documents_complete = fields.Boolean(
        compute="_compute_missing_required_documents",
        string="All Required Documents Uploaded",
    )
    stage_banner_html = fields.Html(
        compute="_compute_stage_banner_html",
        sanitize=False,
        string="Stage Banner",
    )
    required_documents_html = fields.Html(
        compute="_compute_required_documents_html",
        sanitize=False,
        string="Required Documents Status",
    )

    def _compute_is_creator(self):
        """Check if current user is the creator of this CR."""
        for rec in self:
            rec.is_creator = rec.create_uid == self.env.user

    @api.depends("detail_res_id", "detail_res_model")
    def _compute_has_proposed_changes(self):
        """Check if there are actual proposed changes in the detail record."""
        for rec in self:
            rec.has_proposed_changes = False

            if not rec.detail_res_id or not rec.detail_res_model or not rec.request_type_id:
                continue

            try:
                # Use sudo to bypass record rules (e.g. global disabled-registrant
                # rules on spp.group.membership) — this is read-only preview logic.
                sudo_rec = rec.sudo()  # nosemgrep: odoo-sudo-without-context
                strategy = sudo_rec.request_type_id.get_apply_strategy()
                changes = strategy.preview(sudo_rec) or {}

                # Remove metadata keys that don't represent actual changes
                changes.pop("_action", None)
                changes.pop("_message", None)

                # If there are remaining keys, there are actual changes
                rec.has_proposed_changes = bool(changes)
            except Exception:
                # If preview fails, default to checking if detail exists
                rec.has_proposed_changes = bool(rec.detail_res_id)

    @api.depends(
        "approval_state",
        "approval_review_ids",
        "approval_review_ids.status",
        "approval_review_ids.tier_review_ids",
        "approval_review_ids.tier_review_ids.status",
    )
    def _compute_multitier_approval_message(self):
        """Compute message showing approval status and pending approver."""
        for rec in self:
            rec.multitier_approval_message = ""

            if rec.approval_state != "pending":
                continue

            # Get the active pending review
            active_review = rec.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]
            if not active_review:
                continue

            if active_review.is_multitier:
                # Multi-tier approval
                tier_reviews = active_review.tier_review_ids
                approved_tiers = tier_reviews.filtered(lambda t: t.status == "approved")
                pending_tiers = tier_reviews.filtered(lambda t: t.status == "pending")
                waiting_tiers = tier_reviews.filtered(lambda t: t.status == "waiting")

                if pending_tiers:
                    current_tier = pending_tiers.sorted("sequence")[:1]
                    group_name = ""
                    if current_tier.tier_id and current_tier.tier_id.approval_group_id:
                        group_name = current_tier.tier_id.approval_group_id.name

                    if group_name:
                        total_tiers = len(tier_reviews)
                        completed = len(approved_tiers)
                        msg = _("Awaiting approval from: %s (Level %d of %d)") % (
                            group_name,
                            completed + 1,
                            total_tiers,
                        )

                        # Show next approver group if there are waiting tiers
                        if waiting_tiers:
                            next_tier = waiting_tiers.sorted("sequence")[:1]
                            if next_tier.tier_id and next_tier.tier_id.approval_group_id:
                                next_group = next_tier.tier_id.approval_group_id.name
                                msg += "\n" + _("Next: %s") % next_group

                        rec.multitier_approval_message = msg
            else:
                # Single-tier approval - get group from definition
                definition = active_review.definition_id
                if definition and definition.approval_group_id:
                    group_name = definition.approval_group_id.name
                    rec.multitier_approval_message = _("Awaiting approval from: %s") % group_name

    @api.depends("request_type_id", "request_type_id.target_type")
    def _compute_target_type_message(self):
        """Compute message indicating valid registrant types for this CR type."""
        for rec in self:
            rec.target_type_message = ""
            if not rec.request_type_id or not rec.request_type_id.target_type:
                continue

            target_type = rec.request_type_id.target_type
            if target_type == "individual":
                rec.target_type_message = _("This request type applies to individuals only.")
            elif target_type == "group":
                rec.target_type_message = _("This request type applies to groups/households only.")
            else:
                rec.target_type_message = _("This request type applies to both individuals and groups/households.")

    @api.depends("name", "request_type_id", "registrant_id")
    def _compute_stage_banner_html(self):
        for rec in self:
            cr_ref = html_escape(rec.name or "")
            cr_type = html_escape(rec.request_type_id.name) if rec.request_type_id else ""
            html = f'<span class="fw-bold">{cr_ref}</span><span class="text-muted mx-2">|</span><span>{cr_type}</span>'
            if rec.registrant_id:
                registrant = html_escape(rec.registrant_id.name or "")
                html += (
                    f'<span class="text-muted mx-2">|</span>'
                    f'<i class="fa fa-user me-1 text-muted"></i>'
                    f"<span>{registrant}</span>"
                )
            rec.stage_banner_html = html

    def _get_effective_required_document_ids(self):
        """Return the document types required for this request.

        When the request type defines per-reason document rules (OP#873) and the
        request's detail exposes a matching reason, that rule's documents take
        precedence over the flat ``required_document_ids`` list. A configured
        rule with no documents means nothing is required for that reason."""
        self.ensure_one()
        empty = self.env["spp.vocabulary.code"]
        rt = self.request_type_id
        if not rt:
            return empty
        reason_rules = rt.reason_document_ids
        if reason_rules:
            detail = self.get_detail()
            # The reason lives on `reason` (Change HoH), `split_reason` (Split)
            # or `end_reason` (Remove Member).
            reason = False
            if detail:
                for rfield in ("reason", "split_reason", "end_reason"):
                    if rfield in detail._fields and detail[rfield]:
                        reason = detail[rfield]
                        break
            if reason:
                rule = reason_rules.filtered(lambda r: r.reason == reason)
                return rule[:1].required_document_ids if rule else empty
        return rt.required_document_ids

    @api.depends(
        "document_ids",
        "document_ids.document_type_id",
        "request_type_id.required_document_ids",
        "request_type_id.reason_document_ids",
    )
    def _compute_missing_required_documents(self):
        for rec in self:
            required = rec._get_effective_required_document_ids() if rec.request_type_id else None
            if not required:
                rec.missing_required_document_ids = self.env["spp.vocabulary.code"]
                rec.documents_complete = True
                continue
            uploaded = rec.document_ids.mapped("document_type_id").filtered(lambda c: c)
            missing = required - uploaded
            rec.missing_required_document_ids = missing
            rec.documents_complete = not bool(missing)

    @api.depends(
        "document_ids",
        "document_ids.document_type_id",
        "request_type_id.required_document_ids",
        "request_type_id.reason_document_ids",
    )
    def _compute_required_documents_html(self):
        for rec in self:
            required = rec._get_effective_required_document_ids() if rec.request_type_id else None
            if not required:
                rec.required_documents_html = (
                    '<div class="alert alert-info mb-3 py-2">'
                    '<i class="fa fa-info-circle me-2"></i>'
                    "Documents are optional for this request type. "
                    "You may upload supporting documents or proceed to the next step."
                    "</div>"
                )
                continue

            uploaded_types = rec.document_ids.mapped("document_type_id").filtered(lambda c: c)
            items = []
            for doc_type in required:
                escaped_name = html_escape(doc_type.display_name)
                if doc_type in uploaded_types:
                    items.append(f'<li class="text-success"><i class="fa fa-check-circle me-1"></i>{escaped_name}</li>')
                else:
                    items.append(f'<li class="text-danger"><i class="fa fa-times-circle me-1"></i>{escaped_name}</li>')

            rec.required_documents_html = (
                '<div class="mb-3">'
                "<strong>Required Documents:</strong>"
                f'<ul class="list-unstyled mt-1 mb-0">{"".join(items)}</ul>'
                "</div>"
            )

    @api.depends("approval_state", "is_applied")
    def _compute_display_state(self):
        for rec in self:
            if rec.is_applied:
                rec.display_state = "applied"
            else:
                rec.display_state = rec.approval_state

    @api.depends("request_type_id.target_type")
    def _compute_registrant_domain(self):
        """Compute dynamic domain for registrant based on CR type target."""
        for rec in self:
            base_domain = [("is_registrant", "=", True)]

            if rec.request_type_id and rec.request_type_id.target_type:
                target_type = rec.request_type_id.target_type
                if target_type == "individual":
                    # Only individuals (not groups)
                    base_domain.append(("is_group", "=", False))
                elif target_type == "group":
                    # Only groups
                    base_domain.append(("is_group", "=", True))
                # else: target_type == "both" - no additional filter

            rec.registrant_domain = str(base_domain)

    def _compute_preview_html(self):
        """Compute HTML preview of changes for the review panel."""
        for rec in self:
            # If already applied, show the stored snapshot
            if rec.is_applied and rec.preview_html_snapshot:
                rec.preview_html = rec.preview_html_snapshot
            else:
                # Generate fresh preview
                rec.preview_html = rec._generate_preview_html()

    def _compute_review_comparison_html(self):
        """Compute side-by-side comparison HTML for the review stage.

        For field-mapping CR types: shows a three-column table (Field | Current | Proposed).
        For action CR types: shows a clean summary table of the action details.
        Uses stored snapshot after apply (since current == proposed post-apply).
        """
        for rec in self:
            if rec.is_applied and rec.review_comparison_html_snapshot:
                rec.review_comparison_html = rec.review_comparison_html_snapshot
            else:
                rec.review_comparison_html = rec._generate_review_comparison_html()

    @api.depends("document_ids")
    def _compute_review_documents_html(self):
        """Compute HTML table for documents matching the proposed changes table style."""
        for rec in self:
            if not rec.document_ids:
                rec.review_documents_html = (
                    '<div class="text-muted"><i class="fa fa-info-circle me-2"></i>No documents attached.</div>'
                )
                continue

            html = ['<table class="table table-sm table-bordered mb-0" style="width:100%;table-layout:fixed">']
            html.append(
                "<thead><tr>"
                '<th class="bg-light" style="width:45%">File</th>'
                '<th class="bg-light" style="width:35%">Document Type</th>'
                '<th class="bg-light" style="width:20%">Uploaded</th>'
                "</tr></thead>"
            )
            html.append("<tbody>")

            for doc in rec.document_ids:
                doc_name = html_escape(doc.name or "")
                doc_type = html_escape(doc.document_type_id.display_name) if doc.document_type_id else ""
                uploaded = doc.create_date.strftime("%Y-%m-%d") if doc.create_date else ""
                html.append(
                    f"<tr>"
                    f'<td style="max-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                    f'<a class="o_cr_doc_preview" data-doc-id="{doc.id}" '
                    f'style="cursor:pointer" title="{doc_name}">'
                    f'<i class="fa fa-eye text-primary me-2"></i></a>{doc_name}</td>'
                    f"<td>{doc_type}</td>"
                    f"<td>{uploaded}</td>"
                    f"</tr>"
                )

            html.append("</tbody></table>")
            rec.review_documents_html = "".join(html)

    def _compute_registrant_summary_html(self):
        """Compute HTML summary of the registrant for the review panel."""
        for rec in self:
            if not rec.registrant_id:
                rec.registrant_summary_html = '<div class="text-muted">No registrant selected.</div>'
                continue

            reg = rec.registrant_id
            html_parts = ['<div class="o_registrant_summary">']

            # Header with name and ID
            html_parts.append('<div class="d-flex align-items-center mb-2">')
            if reg.is_group:
                html_parts.append('<i class="fa fa-users fa-lg text-primary me-2"></i>')
            else:
                html_parts.append('<i class="fa fa-user fa-lg text-primary me-2"></i>')
            html_parts.append(f"<strong>{html_escape(reg.name or '')}</strong>")
            html_parts.append("</div>")

            # ID badge
            if hasattr(reg, "spp_id") and reg.spp_id:
                escaped_id = html_escape(reg.spp_id)
                html_parts.append(f'<div class="mb-2"><span class="badge bg-secondary">ID: {escaped_id}</span></div>')

            # Address
            address_parts = []
            if reg.street:
                address_parts.append(html_escape(reg.street))
            if reg.city:
                address_parts.append(html_escape(reg.city))
            if address_parts:
                html_parts.append(
                    f'<div class="text-muted small mb-2">'
                    f'<i class="fa fa-map-marker me-1"></i>'
                    f"{', '.join(address_parts)}"
                    f"</div>"
                )

            # Group member count
            if reg.is_group and hasattr(reg, "group_membership_ids"):
                member_count = len(reg.group_membership_ids or [])
                html_parts.append(
                    f'<div class="badge bg-info"><i class="fa fa-users me-1"></i>{member_count} member(s)</div>'
                )

            html_parts.append("</div>")
            rec.registrant_summary_html = "".join(html_parts)

    @api.onchange("request_type_id")
    def _onchange_request_type_id(self):
        """Clear registrant if it doesn't match the new target type."""
        if self.request_type_id and self.registrant_id:
            target_type = self.request_type_id.target_type
            is_group = self.registrant_id.is_group

            # Check if registrant conflicts with new target type
            should_clear = False
            if target_type == "individual" and is_group:
                # Changed to individual type but registrant is a group
                should_clear = True
            elif target_type == "group" and not is_group:
                # Changed to group type but registrant is an individual
                should_clear = True

            if should_clear:
                self.registrant_id = False
                return {
                    "warning": {
                        "title": _("Registrant Cleared"),
                        "message": _(
                            "The selected registrant was cleared because it doesn't match "
                            "the target type of the new request type. Please select a "
                            "compatible registrant."
                        ),
                    }
                }

    # ══════════════════════════════════════════════════════════════════════════
    # CRUD
    # ══════════════════════════════════════════════════════════════════════════

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("spp.change.request") or "New"
        records = super().create(vals_list)
        for record in records:
            # Auto-create DMS directory
            record._create_dms_directory()
            # Auto-create detail record
            record._ensure_detail()
            record._create_audit_event("created", None, "draft")
            record._create_log("created")
            # Run conflict detection after creation
            # Skip for dynamic approval — field_to_modify isn't set yet at create time.
            # Checks run when selected_field_name is written (see conflict model's write()).
            if hasattr(record, "_run_conflict_checks") and not (
                record.request_type_id and record.request_type_id.use_dynamic_approval
            ):
                record._run_conflict_checks()
        return records

    # Fields that bind a submitted CR to exactly what was routed and approved:
    # the dynamic-approval selection (synced from the detail's field_to_modify in
    # draft) and the detail record pointer that get_detail() resolves for both
    # routing and apply. Once the CR leaves draft/revision these are frozen — else
    # a user could route on a low-risk field / benign detail and then swap the
    # selection or repoint detail_res_id to a substituted detail before apply.
    # Editing requires reset to draft, which re-routes. (These fields are never
    # written by the apply strategies, so the guard needs no apply-path exemption.)
    _FROZEN_ON_SUBMIT_FIELDS = (
        "selected_field_name",
        "selected_field_old_value",
        "selected_field_new_value",
        "detail_res_id",
        "detail_res_model",
    )

    def _detail_row_belongs_to_self(self, detail_id):
        """Whether ``detail_id`` is a detail row already pointing at this request.

        Used to tell binding a detail apart from substituting one. Reads with
        ``sudo()`` because the caller may not have access to the detail model,
        and the answer is only ever used to reject or allow, never returned.
        """
        self.ensure_one()
        if not detail_id or not self.detail_res_model:
            return False
        model = self.env.get(self.detail_res_model)
        if model is None:
            return False
        parent_field = "x_change_request_id" if "x_change_request_id" in model._fields else "change_request_id"
        if parent_field not in model._fields:
            return False
        # sudo: the caller may hold no access to the detail model, and the answer
        # is only ever used to accept or reject the write -- the record itself is
        # never returned or exposed. Reads a single field on a single row.
        detail = model.sudo().browse(int(detail_id)).exists()  # nosemgrep: odoo-sudo-without-context
        return bool(detail) and detail[parent_field].id == self.id

    def _alters_frozen_field(self, field, value):
        """Whether writing ``value`` to ``field`` changes what was approved."""
        self.ensure_one()
        if normalize_frozen_value(value) == normalize_frozen_value(self[field]):
            return False
        # Binding a detail row for the first time is not a re-route. A submitted
        # request that never got one cannot be opened at all -- get_detail()
        # resolves nothing -- and ``_ensure_detail()`` exists to repair exactly
        # that, so refusing the write left the record permanently unopenable
        # from any context, sudo included. Only a row that already points back
        # at this request is accepted, so this cannot be used to attach a
        # substituted detail after approval.
        if field == "detail_res_id" and not normalize_frozen_value(self[field]):
            return not self._detail_row_belongs_to_self(value)
        return True

    def write(self, vals):
        guarded = [f for f in self._FROZEN_ON_SUBMIT_FIELDS if f in vals]
        if guarded:
            for rec in self:
                if rec.approval_state in ("draft", "revision") or not rec.approval_state:
                    continue
                if any(rec._alters_frozen_field(f, vals[f]) for f in guarded):
                    raise UserError(
                        _(
                            "A submitted change request is locked to the change it was "
                            "routed and approved for; its selected field and detail record "
                            "cannot be changed. Reset the request to draft to re-route."
                        )
                    )
        return super().write(vals)

    def unlink(self):
        """Delete associated detail records and archive DMS directory."""
        directories_to_archive = self.env["spp.dms.directory"]
        for rec in self:
            detail = rec.get_detail()
            if detail:
                detail.unlink()
            # Collect directory for archiving (instead of deletion to avoid FK constraint violations)
            if rec.dms_directory_id:
                directories_to_archive |= rec.dms_directory_id
        result = super().unlink()
        # Archive directories after CR is deleted to preserve files and avoid constraint issues
        if directories_to_archive:
            directories_to_archive.write({"active": False})
            _logger.info(
                "Archived %d DMS directories after CR deletion",
                len(directories_to_archive),
            )
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # DMS DIRECTORY MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════

    def _get_parent_directory(self):
        """Get the parent 'Change Request' directory.

        Returns:
            spp.dms.directory: The parent Change Request directory
        """
        parent_dir = self.env.ref(
            "spp_change_request_v2.dms_directory_change_request_root",
            raise_if_not_found=False,
        )
        if not parent_dir:
            _logger.warning(
                "Parent 'Change Request' directory not found. Please ensure data/dms_directories.xml is loaded."
            )
        return parent_dir

    def _create_dms_directory(self):
        """Create a DMS directory for this change request.

        Creates a subdirectory under the 'Change Request' parent directory
        with the CR reference as the name.
        """
        self.ensure_one()
        if self.dms_directory_id:
            # Directory already exists
            return

        if self.name == "New":
            # Skip if name is still default (shouldn't happen after sequence)
            _logger.warning("Skipping DMS directory creation for CR with name 'New'")
            return

        # Get parent directory
        parent_dir = self._get_parent_directory()
        if not parent_dir:
            _logger.error(
                "Cannot create DMS directory for CR %s: parent directory not found",
                self.name,
            )
            return

        # Create subdirectory for this CR
        directory = self.env["spp.dms.directory"].create(
            {
                "name": self.name,
                "parent_id": parent_dir.id,
                "is_root_directory": False,
                "change_request_id": self.id,
            }
        )
        self.dms_directory_id = directory.id
        _logger.info(
            "Created DMS directory '%s' for change request %s",
            directory.complete_name,
            self.name,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # DETAIL HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def get_detail(self):
        """Get the detail record for this CR.

        Uses with_prefetch() to isolate from _ensure_detail's sudo()
        prefetch set — without this, non-stored computed fields can
        trigger record-rule checks against the wrong user.
        """
        self.ensure_one()
        if self.detail_res_model and self.detail_res_id:
            return self.env[self.detail_res_model].browse(self.detail_res_id).with_prefetch()
        return None

    def _ensure_detail(self):
        """Ensure detail record exists, create if needed.

        Handles both Python-defined models (with change_request_id) and
        Studio-created models (with x_change_request_id).

        Uses sudo() for creation since users may not have create permission
        on detail models (especially Studio-created ones where we disable
        create permission to prevent the "New" button from appearing).
        """
        self.ensure_one()
        if not self.detail_res_id and self.detail_res_model:
            # Determine the correct field name for the change request reference
            # Studio-created models use x_change_request_id (Odoo naming convention)
            # Python-defined models use change_request_id
            detail_model = self.env[self.detail_res_model]
            if "x_change_request_id" in detail_model._fields:
                cr_field = "x_change_request_id"
            else:
                cr_field = "change_request_id"

            # Use sudo() for creation - users don't need create permission
            # Detail records are always created by the system automatically
            detail = detail_model.sudo().create({cr_field: self.id})  # nosemgrep: odoo-sudo-without-context
            self.detail_res_id = detail.id

            # Pre-fill detail from registrant if the detail model supports it
            if hasattr(detail, "prefill_from_registrant"):
                detail.prefill_from_registrant()

        return self.get_detail()

    # ══════════════════════════════════════════════════════════════════════════
    # APPROVAL ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_approve(self, comment=None):
        """Override to log intermediate tier approvals in multi-tier workflow.

        The base _on_approve hook only fires after ALL tiers are approved.
        This captures each intermediate tier approval in the CR log.
        """
        # Capture pre-approval state per record
        pre_states = {}
        for record in self:
            if record.approval_state == "pending" and record.is_multitier_approval:
                pre_states[record.id] = record.current_tier_name

        result = super().action_approve(comment=comment)

        # Log intermediate tier approvals
        # (final approval is already logged by _on_approve)
        for record in self:
            if record.id in pre_states and record.approval_state == "pending":
                record._create_log("approved")

        return result

    def action_submit_for_approval(self):
        """Submit for approval with document and required field validation.

        Checks required detail fields and documents before submission.
        """
        for record in self:
            # Validate required detail fields first
            if record.request_type_id.required_field_ids:
                detail = record.get_detail()
                if detail:
                    is_valid, missing_fields = record.request_type_id.validate_required_fields(detail)
                    if not is_valid:
                        missing_list = "\n".join(f"• {field}" for field in missing_fields)
                        raise ValidationError(
                            _(
                                "Cannot submit change request. The following required fields are missing:\n\n%s\n\n"
                                "Please fill in all required fields before submitting."
                            )
                            % missing_list
                        )

            # Check document validation
            doc_validation_result = record._validate_documents()

            # Proceed with submission
            super(SPPChangeRequest, record).action_submit_for_approval()

            # Build success notification with redirect to CR list
            list_action = {
                "type": "ir.actions.client",
                "tag": "navigate_cr_list",
            }

            type_name = record.request_type_id.name or ""
            success_message = _("%s %s successfully submitted for approval.") % (
                record.name,
                type_name,
            )

            # If warning mode and documents missing, append doc warning to message
            if doc_validation_result and doc_validation_result.get("notification"):
                notification = doc_validation_result["notification"]
                success_message += "\n" + notification["message"]

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": success_message,
                    "type": "success",
                    "sticky": False,
                    "next": list_action,
                },
            }

        return super().action_submit_for_approval()

    # ══════════════════════════════════════════════════════════════════════════
    # APPROVAL HOOKS (from spp.approval.mixin)
    # ══════════════════════════════════════════════════════════════════════════

    def _get_approval_definition(self):
        self.ensure_one()
        cr_type = self.request_type_id

        # Dynamic approval: evaluate candidates using selected field + values
        if cr_type.use_dynamic_approval and cr_type.candidate_definition_ids:
            definition = self._resolve_dynamic_approval()
            if definition:
                return definition

        # Fallback to static definition (existing behavior)
        definition = cr_type.approval_definition_id
        if not definition:
            raise UserError(
                _(
                    "No approval workflow configured for request type '%s'. "
                    "Please configure an approval definition in Change Request > "
                    "Configuration > CR Types."
                )
                % cr_type.name
            )
        return definition

    def _resolve_dynamic_approval(self):
        """Evaluate candidate definitions against selected field and values.

        Iterates candidates in sequence order; first match wins.
        Returns spp.approval.definition record, or None if no candidate matches.
        """
        self.ensure_one()

        if not self.selected_field_name:
            return None

        extra_context = self._compute_field_values_for_cel()
        evaluator = self.env["spp.cel.evaluator"]

        for candidate in self.request_type_id.candidate_definition_ids.sorted("sequence"):
            if not candidate.use_cel_condition or not candidate.cel_condition:
                # No condition = catch-all (matches everything)
                return candidate
            try:
                result = evaluator.evaluate(candidate.cel_condition, self, extra_context)
                if result:
                    return candidate
            except Exception:
                _logger.warning(
                    "CEL evaluation failed for candidate definition '%s' on CR %s, skipping",
                    candidate.name,
                    self.name,
                    exc_info=True,
                )
                continue

        return None

    def _compute_field_values_for_cel(self):
        """Compute typed old and new values for CEL evaluation.

        Returns a dict with old_value and new_value typed according to field type.
        """
        self.ensure_one()
        field_name = self.selected_field_name
        cr_type = self.request_type_id

        if not field_name:
            return {"old_value": None, "new_value": None}

        mapping = cr_type.apply_mapping_ids.filtered(lambda m: m.source_field == field_name)[:1]

        detail = self.get_detail()
        registrant = self.registrant_id

        old_raw = None
        new_raw = None

        if mapping and registrant:
            old_raw = getattr(registrant, mapping.target_field, None)
        if detail:
            new_raw = getattr(detail, field_name, None)

        return {
            "old_value": self._normalize_value_for_cel(old_raw, registrant, mapping.target_field if mapping else None),
            "new_value": self._normalize_value_for_cel(new_raw, detail, field_name),
        }

    def _normalize_value_for_cel(self, value, record, field_name):
        """Normalize an Odoo field value for use in CEL expressions."""
        if value is None or value is False:
            if record and field_name and field_name in record._fields:
                field = record._fields[field_name]
                if field.type == "boolean":
                    return False
                if field.type in ("integer", "float", "monetary"):
                    return 0
            return None

        if record and field_name and field_name in record._fields:
            field = record._fields[field_name]
            if field.type in ("char", "text", "selection", "html"):
                return value or ""
            if field.type in ("integer", "float", "monetary"):
                return value or 0
            if field.type == "boolean":
                return bool(value)
            if field.type in ("date", "datetime"):
                return value
            if field.type == "many2one":
                # IDs are exposed for internal CEL evaluation only, not for external APIs.
                result = {
                    "id": value.id if value else 0,
                    "name": value.display_name if value else "",
                }
                # Vocabulary models: expose machine-readable code for stable CEL matching
                if value and "code" in value._fields:
                    result["code"] = value.code or ""
                # Hierarchical vocabularies: expose parent category
                if value and "parent_id" in value._fields and value.parent_id:
                    parent = value.parent_id
                    result["parent"] = {
                        "id": parent.id,
                        "name": parent.display_name,
                        "code": parent.code if "code" in parent._fields else "",
                    }
                return result
            if field.type in ("one2many", "many2many"):
                return {
                    "ids": value.ids if value else [],
                    "count": len(value) if value else 0,
                }

        return value

    def _on_approve(self):
        super()._on_approve()
        # Signal ORM that approval_state changed (set via raw SQL in _do_approve)
        # so stored computed fields like display_state get recomputed
        self.modified(["approval_state"])
        self._create_audit_event("approved", "pending", "approved")
        self._create_log("approved")
        if self.request_type_id.auto_apply_on_approve:
            # Auto-apply is authorized by the approval workflow itself, so it
            # runs with sudo: ``action_apply``'s manager gate exempts
            # ``env.su``, which lets the approver be a validator rather than a
            # manager. Going through the public entry point rather than the
            # internal mechanism keeps ``action_apply`` the single extension
            # point for apply -- downstream modules override it to hang
            # post-apply work off the apply, and routing around it left those
            # overrides silently not running on approval. ``sudo()`` sets
            # ``su`` without changing ``uid``, so ``applied_by_id`` still
            # records the real approver.
            self.sudo().action_apply()

    def _on_reject(self, reason):
        super()._on_reject(reason)
        self._create_audit_event("rejected", "pending", "rejected")
        self._create_log("rejected", notes=reason)

    def _check_can_submit(self):
        """Override to allow resubmission and validate dynamic approval field selection."""
        self.ensure_one()
        if self.approval_state not in ("draft", "revision"):
            raise UserError(_("Only draft or revision-requested records can be submitted for approval."))
        cr_type = self.request_type_id
        if cr_type.use_dynamic_approval and not self.selected_field_name:
            raise ValidationError(
                _(
                    "Please select a field to modify on the detail form before "
                    "submitting for approval. This CR type requires a single "
                    "field selection for dynamic approval routing."
                )
            )

    def _on_submit(self):
        # Run conflict checks before submission
        if hasattr(self, "_run_conflict_checks"):
            check_result = self._run_conflict_checks()
            if not check_result["can_proceed"]:
                raise UserError(
                    _("Cannot submit due to blocking conflicts:\n\n%s") % "\n".join(check_result["messages"])
                )

        super()._on_submit()
        old_state = "draft" if self.approval_state == "draft" else "revision"
        action = "resubmitted" if old_state == "revision" else "submitted"
        self._create_audit_event("submitted", old_state, "pending")
        self._create_log(action)
        self.stage = "review"

    def _on_request_revision(self, notes):
        super()._on_request_revision(notes)
        self._create_audit_event("revision_requested", "pending", "revision")
        self._create_log("revision_requested", notes=notes)
        self.stage = "review"

    def _on_reset_to_draft(self):
        super()._on_reset_to_draft()
        self._create_audit_event("reset_to_draft", self.approval_state, "draft")
        self._create_log("reset_to_draft")
        self.stage = "details"

    # ══════════════════════════════════════════════════════════════════════════
    # APPLY
    # ══════════════════════════════════════════════════════════════════════════

    def _generate_preview_html(self):
        """Generate preview HTML from current state (extracted for reuse)."""
        self.ensure_one()

        if not self.request_type_id or not self.detail_res_id:
            return '<div class="text-muted"><i class="fa fa-info-circle me-2"></i>No changes to preview yet.</div>'

        try:
            # Use sudo() so validators can preview memberships of disabled registrants
            sudo_self = self.sudo()  # nosemgrep: odoo-sudo-without-context
            strategy = sudo_self.request_type_id.get_apply_strategy()
            changes = strategy.preview(sudo_self) or {}
        except Exception as e:
            _logger.warning("Error computing preview for CR ID %s: %s", self.id, e)
            return (
                '<div class="alert alert-warning">'
                '<i class="fa fa-exclamation-triangle me-2"></i>'
                "Could not load preview."
                "</div>"
            )

        # Build HTML preview
        html_parts = ['<div class="o_preview_changes">']

        action = changes.pop("_action", "update")
        action_labels = {
            "update": "Update Fields",
            "create": "Create New Record",
            "delete": "Remove Record",
            "add_member": "Add Member",
            "remove_member": "Remove Member",
            "transfer": "Transfer",
        }
        action_label = action_labels.get(action, action.replace("_", " ").title())
        html_parts.append(
            f'<div class="mb-3 d-flex align-items-center">'
            f'<span class="badge bg-primary me-2">{html_escape(action_label)}</span>'
            f"</div>"
        )

        if changes:
            html_parts.append('<table class="table table-sm table-striped mb-0">')
            html_parts.append("<thead><tr><th>Field</th><th>Change</th></tr></thead>")
            html_parts.append("<tbody>")

            for key, value in changes.items():
                if key.startswith("_"):
                    continue
                display_key = html_escape(key.replace("_", " ").title())

                # Handle dict with old/new structure
                if isinstance(value, dict) and "new" in value:
                    old_val = value.get("old")
                    new_val = value.get("new")
                    # Format old value
                    if old_val is None or old_val is False or old_val == "":
                        old_display = '<span class="text-muted">—</span>'
                    else:
                        old_display = html_escape(str(old_val))
                    # Format new value
                    if new_val is None or new_val is False or new_val == "":
                        new_display = '<span class="text-muted">—</span>'
                    else:
                        new_display = f"<strong>{html_escape(str(new_val))}</strong>"
                    display_value = f"{old_display} → {new_display}"
                elif isinstance(value, list):
                    if value:
                        display_value = "<br/>".join(html_escape(str(v)) for v in value)
                    else:
                        display_value = '<span class="text-muted">Not set</span>'
                elif value is None or value is False or value == "":
                    # Empty/unset values - show as "Not set"
                    display_value = '<span class="text-muted">Not set</span>'
                elif isinstance(value, bool):
                    # Only True reaches here (False caught above)
                    display_value = '<span class="badge text-bg-success">Yes</span>'
                else:
                    display_value = html_escape(str(value))

                html_parts.append(f"<tr><td><strong>{display_key}</strong></td><td>{display_value}</td></tr>")

            html_parts.append("</tbody></table>")
        else:
            html_parts.append(
                '<p class="text-muted mb-0"><i class="fa fa-info-circle me-2"></i>No field changes detected.</p>'
            )

        html_parts.append("</div>")
        return "".join(html_parts)

    def _generate_review_comparison_html(self):
        """Generate comparison HTML for the review stage.

        For field-mapping types (old/new pairs): renders a three-column
        comparison table showing Field | Current | Proposed.
        For action types: renders a summary table of the action details.
        """
        self.ensure_one()

        if not self.request_type_id or not self.detail_res_id:
            return '<div class="text-muted"><i class="fa fa-info-circle me-2"></i>No changes to review yet.</div>'

        try:
            # Use sudo() so validators can preview memberships of disabled registrants
            sudo_self = self.sudo()  # nosemgrep: odoo-sudo-without-context
            strategy = sudo_self.request_type_id.get_apply_strategy()
            changes = strategy.preview(sudo_self) or {}
        except Exception as e:
            _logger.warning("Error computing review comparison for CR ID %s: %s", self.id, e)
            return (
                '<div class="alert alert-warning">'
                '<i class="fa fa-exclamation-triangle me-2"></i>'
                "Could not load review data."
                "</div>"
            )

        action = changes.pop("_action", None)
        header = changes.pop("_header", None)
        tables = changes.pop("_tables", None)
        sections = changes.pop("_sections", None)

        # Determine if this is a field-mapping type (has old/new dicts)
        has_comparison = any(isinstance(v, dict) and "old" in v and "new" in v for v in changes.values())

        if has_comparison:
            html = self._render_comparison_table(changes, header=header)
        else:
            html = self._render_action_summary(action, changes, header=header)
        if tables:
            html += self._render_data_tables(tables)
        if sections:
            html += self._render_data_sections(sections)
        return html

    def _render_data_tables(self, tables):
        """Render preview() ``_tables`` entries as separate HTML tables.

        Each entry is ``{"title", "columns", "rows"}`` where ``rows`` is a list
        of cell-string lists. Used to show one2many data (phones, bank accounts,
        ID documents, ...) on the review page instead of a bare count (OP#876).
        """
        out = []
        for table in tables:
            columns = table.get("columns") or []
            rows = table.get("rows") or []
            out.append(f'<h6 class="mt-3 mb-1">{html_escape(table.get("title") or "")}</h6>')
            if not rows:
                out.append('<div class="text-muted small mb-0"><i class="fa fa-info-circle me-2"></i>None.</div>')
                continue
            out.append('<table class="table table-sm table-bordered mb-0" style="width:100%">')
            out.append(
                "<thead><tr>"
                + "".join(f'<th class="bg-light">{html_escape(c)}</th>' for c in columns)
                + "</tr></thead>"
            )
            out.append("<tbody>")
            for row in rows:
                out.append(
                    "<tr>" + "".join(f"<td>{html_escape('' if c is None else str(c))}</td>" for c in row) + "</tr>"
                )
            out.append("</tbody></table>")
        return "".join(out)

    def _render_data_sections(self, sections):
        """Render preview() ``_sections`` entries — one labelled detail block per
        entity (e.g. each new group member): its fields as a key/value table plus
        any nested ``tables`` (e.g. that member's phone numbers) (OP#876).
        """
        out = []
        for section in sections:
            out.append(f'<h6 class="mt-3 mb-1">{html_escape(section.get("title") or "")}</h6>')
            field_rows = section.get("fields") or []
            if field_rows:
                out.append('<table class="table table-sm table-bordered mb-0" style="width:100%">')
                out.append("<tbody>")
                for label, value in field_rows:
                    display = html_escape(value) if value else '<span class="text-muted">—</span>'
                    out.append(
                        f'<tr><td class="bg-light" style="width:30%"><strong>{html_escape(label)}</strong></td>'
                        f"<td>{display}</td></tr>"
                    )
                out.append("</tbody></table>")
            nested = section.get("tables")
            if nested:
                out.append(self._render_data_tables(nested))
        return "".join(out)

    def _render_comparison_table(self, changes, header=None):
        """Render a three-column comparison table for field-mapping CR types."""
        html = []
        if header:
            html.append(f"<h4>{html_escape(header)}</h4>")
        html.append('<table class="table table-sm table-bordered mb-0" style="width:100%">')
        html.append(
            "<thead><tr>"
            '<th class="bg-light"></th>'
            '<th class="bg-light">Current</th>'
            '<th class="bg-light">Proposed</th>'
            "</tr></thead>"
        )
        html.append("<tbody>")

        for key, value in changes.items():
            if key.startswith("_"):
                continue
            # Use key as-is if it contains spaces (human-readable), otherwise convert
            display_key = html_escape(key if " " in key else key.replace("_", " ").title())

            if isinstance(value, dict) and "old" in value:
                old_val = value.get("old")
                new_val = value.get("new")
                old_display = self._format_review_value(old_val)
                new_display = self._format_review_value(new_val)

                # Highlight changed values
                changed = old_val != new_val
                new_class = ' class="text-success fw-bold"' if changed else ""
                old_class = ' class="text-muted"' if changed else ""

                html.append(
                    f"<tr>"
                    f'<td class="bg-light"><strong>{display_key}</strong></td>'
                    f"<td{old_class}>{old_display}</td>"
                    f"<td{new_class}>{new_display}</td>"
                    f"</tr>"
                )
            else:
                # Non-comparison field — span across both columns
                display_value = self._format_review_value(value)
                html.append(
                    f"<tr>"
                    f'<td class="bg-light"><strong>{display_key}</strong></td>'
                    f'<td colspan="2">{display_value}</td>'
                    f"</tr>"
                )

        html.append("</tbody></table>")
        return "".join(html)

    def _render_action_summary(self, action, changes, header=None):
        """Render a summary table for action-based CR types."""
        html = []

        if header:
            html.append(f"<h4>{html_escape(header)}</h4>")

        if not changes:
            html.append('<p class="text-muted mb-0"><i class="fa fa-info-circle me-2"></i>No details to display.</p>')
            return "".join(html)

        html.append('<table class="table table-sm table-bordered mb-0" style="width:100%">')
        html.append('<thead><tr><th class="bg-light"></th><th class="bg-light">Value</th></tr></thead>')
        html.append("<tbody>")

        for key, value in changes.items():
            if key.startswith("_"):
                continue
            display_key = html_escape(key if " " in key else key.replace("_", " ").title())
            display_value = self._format_review_value(value)
            html.append(f'<tr><td class="bg-light"><strong>{display_key}</strong></td><td>{display_value}</td></tr>')

        html.append("</tbody></table>")
        return "".join(html)

    def _format_review_value(self, value):
        """Format a single value for display in review tables."""
        if value is None or value is False or value == "":
            return '<span class="text-muted">—</span>'
        if isinstance(value, bool):
            return '<span class="badge text-bg-success">Yes</span>'
        if isinstance(value, list):
            if value:
                return "<br/>".join(html_escape(str(v)) for v in value)
            return '<span class="text-muted">—</span>'
        return html_escape(str(value))

    def _capture_preview_snapshot(self):
        """Capture and store the preview HTML and JSON before applying changes."""
        self.ensure_one()
        import json

        self.preview_html_snapshot = self._generate_preview_html()
        self.review_comparison_html_snapshot = self._generate_review_comparison_html()

        # Also capture the JSON data (use sudo for record-rule bypass)
        sudo_self = self.sudo()  # nosemgrep: odoo-sudo-without-context
        strategy = sudo_self.request_type_id.get_apply_strategy()
        changes = strategy.preview(sudo_self) or {}
        self.preview_json_snapshot = json.dumps(changes, indent=2, default=str)

    def action_apply(self):
        """Apply the change request(s) to the registrant.

        Public entrypoint (review button / RPC). Applying runs the apply
        strategy under sudo (see ``_do_apply``), which can write models CR
        roles cannot (e.g. ``spp.group.membership``), so it must be gated
        server-side to managers: the XML button ``groups=`` is NOT an
        authorization boundary because Odoo object methods are callable over
        RPC. Superuser (sudo) callers and the auto-apply-on-approve path (which
        invokes ``_apply_change_request`` directly, already authorized by the
        approval workflow) are unaffected.
        """
        if not (self.env.su or self.env.user.has_group("spp_change_request_v2.group_cr_manager")):
            raise AccessError(_("Only Change Request managers can apply change requests."))
        for rec in self:
            rec._apply_change_request()

    def _apply_change_request(self):
        """Apply a single approved change request (no authorization gate).

        Internal mechanism shared by ``action_apply`` (manager-gated public
        entrypoint) and auto-apply-on-approve (``_on_approve``, already
        authorized by the approval workflow). Underscore-prefixed so it is not
        callable over RPC — the authorization boundary lives on
        ``action_apply``.
        """
        self.ensure_one()
        if self.is_applied:
            raise UserError(_("Changes have already been applied."))
        if self.approval_state != "approved":
            raise UserError(_("Change request must be approved first."))

        try:
            # Capture preview snapshot before applying
            self._capture_preview_snapshot()

            self._do_apply()
            self.write(
                {
                    "is_applied": True,
                    "applied_date": fields.Datetime.now(),
                    "applied_by_id": self.env.user.id,
                    "apply_error": False,
                }
            )
            self._create_audit_event("applied", "approved", "applied")
            self._create_log("applied")
        except Exception as e:
            _logger.exception("Failed to apply change request %s", self.name)
            self.write({"apply_error": str(e)})
            raise

    def _do_apply(self):
        """Execute the apply strategy.

        Uses sudo() because the apply operation is a system action that
        executes already-approved changes. The approval workflow (single
        or multi-tier) is the security gate — by the time we reach here,
        approval_state == 'approved' has been verified. Strategies may
        need to modify models the validator doesn't have direct access
        to (e.g. spp.group.membership blocked by global record rules).
        """
        self.ensure_one()
        sudo_self = self.sudo()  # nosemgrep: odoo-sudo-without-context
        strategy = sudo_self.request_type_id.get_apply_strategy()
        strategy.apply(sudo_self)

    def action_preview_changes(self):
        """Preview what changes will be applied (returns data dict)."""
        self.ensure_one()
        strategy = self.request_type_id.get_apply_strategy()
        return strategy.preview(self)

    def action_open_preview_wizard(self):
        """Open wizard to preview changes (UI action)."""
        self.ensure_one()
        wizard = self.env["spp.cr.preview.wizard"].create(
            {
                "change_request_id": self.id,
            }
        )
        return {
            "name": _("Preview Changes"),
            "type": "ir.actions.act_window",
            "res_model": "spp.cr.preview.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_registrant(self):
        """Open the registrant form view."""
        self.ensure_one()
        if not self.registrant_id:
            return

        # Use the OpenSPP registry form view (works for both individuals and groups)
        form_view = self.env.ref("spp_registry.view_individuals_form", raise_if_not_found=False)

        return {
            "name": self.registrant_id.name,
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": self.registrant_id.id,
            "view_mode": "form",
            "view_id": form_view.id if form_view else False,
            "target": "current",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # VALIDATION
    # ══════════════════════════════════════════════════════════════════════════

    def _validate_documents(self):
        """Check document requirements.

        Returns:
            dict or None: Warning dictionary if validation_mode is 'warning' and documents missing,
                         None otherwise
        """
        self.ensure_one()
        cr_type = self.request_type_id

        # Skip validation if mode is 'none'
        if cr_type.document_validation_mode == "none":
            return None

        # Use new vocabulary-based required documents
        required = cr_type.required_document_ids
        if not required:
            # Fall back to legacy field if available
            if cr_type.required_document_type_ids:
                _logger.warning(
                    "CR Type %s using deprecated required_document_type_ids. Please migrate to required_document_ids",
                    cr_type.name,
                )
            return None

        # Get missing documents
        missing = None
        if not self.document_ids:
            missing = required
        else:
            provided = self.document_ids.mapped("document_type_id").filtered(lambda c: c)
            missing = required - provided

        if not missing:
            return None

        missing_names = ", ".join(missing.mapped("display_name"))

        # Handle validation based on mode
        if cr_type.document_validation_mode == "required":
            # BLOCK submission
            raise ValidationError(_("Missing required documents:\n%s") % missing_names)
        elif cr_type.document_validation_mode == "warning":
            # WARN but allow submission - return notification dict
            return {
                "notification": {
                    "title": _("Submitted with Missing Documents"),
                    "message": _("The request has been submitted for review."),
                    "type": "warning",
                    "sticky": False,
                }
            }

        return None

    # ══════════════════════════════════════════════════════════════════════════
    # AUDIT (ADR-002)
    # ══════════════════════════════════════════════════════════════════════════

    def _create_log(self, action, notes=False):
        """Create a log entry for this change request."""
        self.ensure_one()
        self.env["spp.change.request.log"].sudo().create(  # nosemgrep: odoo-sudo-without-context
            {
                "change_request_id": self.id,
                "action": action,
                "user_id": self.env.user.id,
                "notes": notes,
            }
        )

    def _create_audit_event(self, action, old_state, new_state):
        """Create event data record for audit trail."""
        self.ensure_one()
        if "spp.event.data" not in self.env:
            return

        # Skip audit event if no registrant (e.g., Create Group type)
        if not self.registrant_id:
            return

        event_type = self.env.ref(
            "spp_change_request_v2.event_type_cr_audit",
            raise_if_not_found=False,
        )
        if not event_type:
            return

        self.env["spp.event.data"].sudo().create(  # nosemgrep: odoo-sudo-without-context
            {
                "event_type_id": event_type.id,
                "partner_id": self.registrant_id.id,
                "collection_date": fields.Date.today(),
                "state": "active",
                "data_record_id": self.id,
                "model": self.detail_res_model if self.detail_res_model else None,
                "res_id": self.detail_res_id if self.detail_res_id else None,
                "data_json": {
                    "change_request_id": self.id,
                    "change_request_name": self.name,
                    "request_type": self.request_type_code,
                    "action": action,
                    "old_state": old_state,
                    "new_state": new_state,
                    "user_id": self.env.user.id,
                    "user_name": self.env.user.name,
                },
            }
        )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_open_detail(self):
        """Open the detail form for editing.

        The detail record is automatically created via _ensure_detail() and
        should only be edited, never created manually by the user.
        """
        self.ensure_one()
        detail = self._ensure_detail()
        view_id = self.request_type_id.get_detail_form_view_id()
        return {
            "type": "ir.actions.act_window",
            "res_model": self.detail_res_model,
            "res_id": detail.id,
            "view_mode": "form",
            "views": [[view_id, "form"]],
            "target": "current",
            "context": {
                "create": False,
                "delete": False,
                "form_view_initial_mode": "edit",
            },
        }

    def action_view_registrant(self):
        """View the registrant record in a popup for easy navigation back."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Registrant"),
            "res_model": "res.partner",
            "res_id": self.registrant_id.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_upload_document(self):
        """Open wizard to upload a document."""
        self.ensure_one()
        return {
            "name": _("Upload Document"),
            "type": "ir.actions.act_window",
            "res_model": "spp.cr.document.upload.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_change_request_id": self.id,
            },
        }

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE NAVIGATION
    # ══════════════════════════════════════════════════════════════════════════

    def action_open_stage_form(self):
        """Open the appropriate form view based on the current stage.

        - **Draft / revision**: route by `stage` to the editable stage form
          (details / documents / review).
        - **Submitted+ (pending, approved, applied, rejected)**: always open
          the review-stage form. That form already renders state-aware
          headers (Approve/Reject for validators, Apply for managers,
          Applied ribbon for completed, Start Over for rejected) and shows
          the same Edit Details → Upload Documents → Review & Submit
          breadcrumb. Without this, validators/managers (and demo-applied
          CRs opened from the list) landed on the legacy main form view
          which lacks the breadcrumb and the pager-hide treatment. See
          OP#920 round-2.
        """
        self.ensure_one()

        if self.approval_state in ("draft", "revision"):
            if self.stage == "documents":
                return self._action_open_documents_form()
            if self.stage == "review":
                return self._action_open_review_form()
            return self.action_open_detail()

        # pending / approved / applied / rejected
        return self._action_open_review_form()

    def _action_open_review_form(self):
        """Open the CR in the Review & Submit stage form view."""
        self.ensure_one()
        view = self.env.ref(
            "spp_change_request_v2.spp_change_request_review_form",
            raise_if_not_found=False,
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "spp.change.request",
            "res_id": self.id,
            "view_mode": "form",
            "views": [[view.id if view else False, "form"]],
            "target": "current",
        }

    def _action_open_documents_form(self):
        """Open the CR in the Upload Documents stage form view."""
        self.ensure_one()
        view = self.env.ref(
            "spp_change_request_v2.spp_change_request_documents_form",
            raise_if_not_found=False,
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "spp.change.request",
            "res_id": self.id,
            "view_mode": "form",
            "views": [[view.id if view else False, "form"]],
            "target": "current",
        }

    def action_goto_details(self):
        """Navigate to the details stage (replaces breadcrumb via client action)."""
        self.ensure_one()
        self.stage = "details"
        detail = self._ensure_detail()
        return {
            "type": "ir.actions.client",
            "tag": "navigate_cr_stage",
            "params": {
                "name": _("Change Request Details"),
                "res_model": self.detail_res_model,
                "res_id": detail.id,
                "context": {
                    "create": False,
                    "delete": False,
                    "form_view_initial_mode": "edit",
                },
            },
        }

    def action_start_over(self):
        """Create a new CR with the same type/registrant and open its detail form."""
        self.ensure_one()
        cr_vals = {
            "request_type_id": self.request_type_id.id,
            "source_type": "manual",
        }
        if self.registrant_id:
            cr_vals["registrant_id"] = self.registrant_id.id
        new_change_request = self.env["spp.change.request"].create(cr_vals)

        detail = new_change_request.get_detail()
        if detail:
            view_id = self.request_type_id.get_detail_form_view_id()
            return {
                "type": "ir.actions.client",
                "tag": "navigate_cr_stage",
                "params": {
                    "name": _("Change Request Details"),
                    "res_model": new_change_request.detail_res_model,
                    "res_id": detail.id,
                    "view_id": view_id,
                    "context": {
                        "create": False,
                        "delete": False,
                        "form_view_initial_mode": "edit",
                    },
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "navigate_cr_stage",
            "params": {
                "name": _("Change Request"),
                "res_model": "spp.change.request",
                "res_id": new_change_request.id,
                "context": {
                    "form_view_initial_mode": "edit",
                },
            },
        }

    def action_save_and_go_to_list(self):
        """Save current state and navigate back to the CR list."""
        return {
            "type": "ir.actions.client",
            "tag": "navigate_cr_list",
        }

    def action_goto_documents(self):
        """Navigate to the documents stage (replaces breadcrumb via client action)."""
        self.ensure_one()
        self.stage = "documents"
        return {
            "type": "ir.actions.client",
            "tag": "navigate_cr_stage",
            "params": {
                "name": _("Documents - %s") % self.name,
                "res_model": "spp.change.request",
                "res_id": self.id,
                "context": {
                    "form_view_ref": "spp_change_request_v2.spp_change_request_documents_form",
                    "form_view_initial_mode": "edit",
                },
            },
        }

    def action_goto_review(self):
        """Navigate to the review stage (replaces breadcrumb via client action)."""
        self.ensure_one()
        self.stage = "review"
        return {
            "type": "ir.actions.client",
            "tag": "navigate_cr_stage",
            "params": {
                "name": _("Review - %s") % self.name,
                "res_model": "spp.change.request",
                "res_id": self.id,
                "context": {
                    "form_view_ref": "spp_change_request_v2.spp_change_request_review_form",
                    "form_view_initial_mode": "edit",
                },
            },
        }
