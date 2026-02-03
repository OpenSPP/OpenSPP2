import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

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

    # ══════════════════════════════════════════════════════════════════════════
    # REGISTRANT & APPLICANT
    # ══════════════════════════════════════════════════════════════════════════

    registrant_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        required=True,
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
            ("rejected", "Declined"),
            ("applied", "Completed"),
        ],
        compute="_compute_display_state",
        store=True,
    )

    preview_html = fields.Html(
        string="Preview of Changes",
        compute="_compute_preview_html",
        sanitize=False,
    )
    preview_html_snapshot = fields.Html(
        string="Preview Snapshot",
        help="Stored snapshot of preview taken before applying changes",
        sanitize=False,
    )
    preview_json_snapshot = fields.Text(
        string="Preview JSON Snapshot",
        help="Stored JSON snapshot of preview taken before applying changes",
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
                # Use the strategy's preview method to check for actual changes
                strategy = rec.request_type_id.get_apply_strategy()
                changes = strategy.preview(rec) or {}

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

                if pending_tiers:
                    # Get the current approver group name from the tier
                    pending_tier = pending_tiers.sorted("sequence")[:1]
                    tier = pending_tier.tier_id
                    group_name = ""
                    if tier and tier.approval_group_id:
                        group_name = tier.approval_group_id.name

                    if group_name:
                        if approved_tiers:
                            rec.multitier_approval_message = _(
                                "Approved at previous level. Awaiting approval from: %s"
                            ) % group_name
                        else:
                            rec.multitier_approval_message = _(
                                "Awaiting approval from: %s"
                            ) % group_name
            else:
                # Single-tier approval - get group from definition
                definition = active_review.definition_id
                if definition and definition.approval_group_id:
                    group_name = definition.approval_group_id.name
                    rec.multitier_approval_message = _(
                        "Awaiting approval from: %s"
                    ) % group_name

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
            html_parts.append(f"<strong>{reg.name}</strong>")
            html_parts.append("</div>")

            # ID badge
            if hasattr(reg, "spp_id") and reg.spp_id:
                html_parts.append(
                    f'<div class="mb-2">' f'<span class="badge bg-secondary">ID: {reg.spp_id}</span>' f"</div>"
                )

            # Address
            address_parts = []
            if reg.street:
                address_parts.append(reg.street)
            if reg.city:
                address_parts.append(reg.city)
            if address_parts:
                html_parts.append(
                    f'<div class="text-muted small mb-2">'
                    f'<i class="fa fa-map-marker me-1"></i>'
                    f'{", ".join(address_parts)}'
                    f"</div>"
                )

            # Group member count
            if reg.is_group and hasattr(reg, "group_membership_ids"):
                member_count = len(reg.group_membership_ids or [])
                html_parts.append(
                    f'<div class="badge bg-info">'
                    f'<i class="fa fa-users me-1"></i>'
                    f"{member_count} member(s)"
                    f"</div>"
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
            # Run conflict detection after creation
            if hasattr(record, "_run_conflict_checks"):
                record._run_conflict_checks()
        return records

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
            _logger.info("Archived %d DMS directories after CR deletion", len(directories_to_archive))
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
                "Parent 'Change Request' directory not found. " "Please ensure data/dms_directories.xml is loaded."
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
            _logger.error("Cannot create DMS directory for CR %s: parent directory not found", self.name)
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
        """Get the detail record for this CR."""
        self.ensure_one()
        if self.detail_res_model and self.detail_res_id:
            return self.env[self.detail_res_model].browse(self.detail_res_id)
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
            detail = detail_model.sudo().create({cr_field: self.id})
            self.detail_res_id = detail.id

            # Pre-fill detail from registrant if the detail model supports it
            if hasattr(detail, "prefill_from_registrant"):
                detail.prefill_from_registrant()

        return self.get_detail()

    # ══════════════════════════════════════════════════════════════════════════
    # APPROVAL ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

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
            result = super(SPPChangeRequest, record).action_submit_for_approval()

            # If warning mode and documents missing, show notification after submission
            if doc_validation_result and doc_validation_result.get("notification"):
                notification = doc_validation_result["notification"]

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": notification["title"],
                        "message": notification["message"],
                        "type": notification["type"],
                        "sticky": notification.get("sticky", False),
                        "next": result if isinstance(result, dict) else {"type": "ir.actions.act_window_close"},
                    },
                }

            # Return normal result if no notification needed
            return result

        return super().action_submit_for_approval()

    # ══════════════════════════════════════════════════════════════════════════
    # APPROVAL HOOKS (from spp.approval.mixin)
    # ══════════════════════════════════════════════════════════════════════════

    def _get_approval_definition(self):
        self.ensure_one()
        definition = self.request_type_id.approval_definition_id
        if not definition:
            raise UserError(
                _(
                    "No approval workflow configured for request type '%s'. "
                    "Please configure an approval definition in Change Request > Configuration > CR Types."
                )
                % self.request_type_id.name
            )
        return definition

    def _on_approve(self):
        super()._on_approve()
        self._create_audit_event("approved", "pending", "approved")
        if self.request_type_id.auto_apply_on_approve:
            self.action_apply()

    def _on_reject(self, reason):
        super()._on_reject(reason)
        self._create_audit_event("rejected", "pending", "rejected")

    def _check_can_submit(self):
        """Override to allow resubmission from revision state."""
        self.ensure_one()
        if self.approval_state not in ("draft", "revision"):
            raise UserError(_("Only draft or revision-requested records can be submitted for approval."))

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
        self._create_audit_event("submitted", old_state, "pending")

    def _on_request_revision(self, notes):
        super()._on_request_revision(notes)
        self._create_audit_event("revision_requested", "pending", "revision")

    def _on_reset_to_draft(self):
        super()._on_reset_to_draft()
        self._create_audit_event("reset_to_draft", self.approval_state, "draft")

    # ══════════════════════════════════════════════════════════════════════════
    # APPLY
    # ══════════════════════════════════════════════════════════════════════════

    def _generate_preview_html(self):
        """Generate preview HTML from current state (extracted for reuse)."""
        self.ensure_one()

        if not self.request_type_id or not self.detail_res_id:
            return (
                '<div class="text-muted">'
                '<i class="fa fa-info-circle me-2"></i>'
                "No changes to preview yet."
                "</div>"
            )

        try:
            strategy = self.request_type_id.get_apply_strategy()
            changes = strategy.preview(self) or {}
        except Exception as e:
            _logger.warning("Error computing preview for CR %s: %s", self.name, e)
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
            f'<span class="badge bg-primary me-2">{action_label}</span>'
            f"</div>"
        )

        if changes:
            html_parts.append('<table class="table table-sm table-striped mb-0">')
            html_parts.append("<thead><tr><th>Field</th><th>Change</th></tr></thead>")
            html_parts.append("<tbody>")

            for key, value in changes.items():
                if key.startswith("_"):
                    continue
                display_key = key.replace("_", " ").title()

                # Handle dict with old/new structure
                if isinstance(value, dict) and "new" in value:
                    old_val = value.get("old")
                    new_val = value.get("new")
                    # Format old value
                    if old_val is None or old_val is False or old_val == "":
                        old_display = '<span class="text-muted">—</span>'
                    else:
                        old_display = str(old_val)
                    # Format new value
                    if new_val is None or new_val is False or new_val == "":
                        new_display = '<span class="text-muted">—</span>'
                    else:
                        new_display = f"<strong>{new_val}</strong>"
                    display_value = f"{old_display} → {new_display}"
                elif isinstance(value, list):
                    if value:
                        display_value = "<br/>".join(str(v) for v in value)
                    else:
                        display_value = '<span class="text-muted">Not set</span>'
                elif value is None or value is False or value == "":
                    # Empty/unset values - show as "Not set"
                    display_value = '<span class="text-muted">Not set</span>'
                elif isinstance(value, bool):
                    # Only True reaches here (False caught above)
                    display_value = '<span class="badge text-bg-success">Yes</span>'
                else:
                    display_value = str(value)

                html_parts.append(f"<tr><td><strong>{display_key}</strong></td>" f"<td>{display_value}</td></tr>")

            html_parts.append("</tbody></table>")
        else:
            html_parts.append(
                '<p class="text-muted mb-0">'
                '<i class="fa fa-info-circle me-2"></i>'
                "No field changes detected."
                "</p>"
            )

        html_parts.append("</div>")
        return "".join(html_parts)

    def _capture_preview_snapshot(self):
        """Capture and store the preview HTML and JSON before applying changes."""
        self.ensure_one()
        import json

        self.preview_html_snapshot = self._generate_preview_html()

        # Also capture the JSON data
        strategy = self.request_type_id.get_apply_strategy()
        changes = strategy.preview(self) or {}
        self.preview_json_snapshot = json.dumps(changes, indent=2, default=str)

    def action_apply(self):
        """Apply the change request to the registrant."""
        for rec in self:
            if rec.is_applied:
                raise UserError(_("Changes have already been applied."))
            if rec.approval_state != "approved":
                raise UserError(_("Change request must be approved first."))

            try:
                # Capture preview snapshot before applying
                rec._capture_preview_snapshot()

                rec._do_apply()
                rec.write(
                    {
                        "is_applied": True,
                        "applied_date": fields.Datetime.now(),
                        "applied_by_id": self.env.user.id,
                        "apply_error": False,
                    }
                )
                rec._create_audit_event("applied", "approved", "applied")
            except Exception as e:
                _logger.exception("Failed to apply change request %s", rec.name)
                rec.write({"apply_error": str(e)})
                raise

    def _do_apply(self):
        """Execute the apply strategy."""
        self.ensure_one()
        strategy = self.request_type_id.get_apply_strategy()
        strategy.apply(self)

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
                    "CR Type %s using deprecated required_document_type_ids. "
                    "Please migrate to required_document_ids",
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

    def _create_audit_event(self, action, old_state, new_state):
        """Create event data record for audit trail."""
        self.ensure_one()
        if "spp.event.data" not in self.env:
            return

        event_type = self.env.ref(
            "spp_change_request_v2.event_type_cr_audit",
            raise_if_not_found=False,
        )
        if not event_type:
            return

        self.env["spp.event.data"].sudo().create(
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
            "view_id": view_id,
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
