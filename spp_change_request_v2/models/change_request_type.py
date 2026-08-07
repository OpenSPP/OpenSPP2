import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SPPChangeRequestType(models.Model):
    """Configuration for a change request type."""

    _name = "spp.change.request.type"
    _description = "Change Request Type"
    _order = "sequence, name"

    # ══════════════════════════════════════════════════════════════════════════
    # BASIC INFO
    # ══════════════════════════════════════════════════════════════════════════

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True, copy=False)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    icon = fields.Char(default="fa-edit")
    color = fields.Integer(default=0)

    # ══════════════════════════════════════════════════════════════════════════
    # EDITABILITY FLAGS (Three-tier customization model)
    # ══════════════════════════════════════════════════════════════════════════

    is_studio_editable = fields.Boolean(
        string="Studio Editable",
        default=True,
        help="Can be modified via Studio UI. Set to False for Python-only types.",
    )
    is_studio_cloneable = fields.Boolean(
        string="Studio Cloneable",
        default=True,
        help="Can be cloned via Studio UI to create a new type based on this one.",
    )
    is_system_type = fields.Boolean(
        string="System Type",
        default=False,
        readonly=True,
        help="Defined by module data. System types cannot be deleted via UI.",
    )
    source_module = fields.Char(
        string="Source Module",
        readonly=True,
        help="Module that installed this type (for system types).",
    )
    cloned_from_id = fields.Many2one(
        "spp.change.request.type",
        string="Cloned From",
        readonly=True,
        ondelete="set null",
        help="Original type this was cloned from (if applicable).",
    )
    locked_reason = fields.Text(
        string="Locked Reason",
        translate=True,
        help="Explanation of why this type cannot be edited via Studio.",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TARGET CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    target_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group/Household"),
            ("both", "Both"),
        ],
        default="both",
        required=True,
    )

    is_requires_registrant = fields.Boolean(
        string="Requires Registrant",
        default=True,
        help="Require selecting a registrant when creating this type of change request. "
        "Disable for types like 'Create New Group' that don't apply to an existing registrant.",
    )

    is_requires_applicant = fields.Boolean(
        string="Requires Applicant",
        default=False,
        help="Require an applicant (person submitting on behalf of registrant)",
    )

    # OP#876: group-creation-specific config. Only read by the Create Group
    # detail/strategy today, but lives on the type so each group-creating CR
    # type can ship its own defaults (e.g. cooperatives may not require a head
    # while households do).
    allow_empty_members = fields.Boolean(
        string="Allow Empty Groups",
        default=False,
        help="When set, the Create Group flow asks whether the user wants to add members "
        "instead of forcing it. When unset, the user must add at least one member.",
    )
    requires_head = fields.Boolean(
        string="Requires Head of Household",
        default=False,
        help="When set, the Create Group flow requires exactly one member to be assigned "
        "the 'head' role from the group-membership-type vocabulary before the CR can apply.",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # DETAIL MODEL CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    detail_model = fields.Char(
        string="Detail Model",
        required=True,
        help="Technical model name (e.g., spp.cr.detail.add_member)",
    )

    detail_form_view_id = fields.Many2one(
        "ir.ui.view",
        string="Detail Form View",
        help="Form view for the detail model. If empty, uses default.",
    )

    is_detail_model_exists = fields.Boolean(
        string="Detail Model Exists",
        compute="_compute_detail_model_exists",
        help="Whether the detail model exists in the database",
    )

    available_field_ids = fields.Many2many(
        "ir.model.fields",
        string="Available Fields",
        compute="_compute_available_field_ids",
        help="Available fields from the detail model that can be marked as required",
    )

    required_field_ids = fields.Many2many(
        "ir.model.fields",
        string="Required Detail Fields",
        help="Fields that must be filled in the detail form before submission",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # DOCUMENT REQUIREMENTS
    # ══════════════════════════════════════════════════════════════════════════

    available_document_ids = fields.Many2many(
        "spp.vocabulary.code",
        "cr_type_available_doc_rel",
        "type_id",
        "doc_id",
        string="Available Documents",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:cr_document_type')]",
        help="Document types that can be uploaded for this change request type",
    )
    required_document_ids = fields.Many2many(
        "spp.vocabulary.code",
        "cr_type_required_doc_rel",
        "type_id",
        "doc_id",
        string="Required Documents",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:cr_document_type'), "
        "('id', 'in', available_document_ids)]",
        help="Subset of available documents that are required",
    )
    # Legacy field for backward compatibility - deprecated
    required_document_type_ids = fields.Many2many(
        "spp.dms.category",
        string="Required Documents (Deprecated)",
        help="Deprecated: Use required_document_ids instead",
    )
    # Per-reason document rules (OP#873). When a CR type exposes a "reason"
    # (e.g. Change Head of Household), the required documents can be driven by
    # the chosen reason instead of the flat required_document_ids list.
    supports_reason_documents = fields.Boolean(
        string="Supports Reason-based Documents",
        compute="_compute_supports_reason_documents",
        help="True when the detail model exposes a 'reason' field, so required "
        "documents can depend on the chosen reason.",
    )
    reason_document_ids = fields.One2many(
        "spp.cr.type.reason.document",
        "cr_type_id",
        string="Required Documents by Reason",
        help="Optional: make required documents depend on the request's Reason. "
        "When set and the request has a matching reason, these documents are "
        "required in place of the flat 'Required Documents' list.",
    )
    allow_document_download = fields.Boolean(
        string="Allow Document Download",
        default=False,
        help="Allow users to download attached documents from the change request.",
    )

    document_validation_mode = fields.Selection(
        [
            ("none", "No Validation"),
            ("warning", "Warning if Missing"),
            ("required", "Block if Missing"),
        ],
        default="none",
    )

    @api.onchange("available_document_ids")
    def _onchange_available_document_ids(self):
        """Validate that required documents remain in available documents list."""
        if self.required_document_ids and self.available_document_ids:
            # Check if any required documents are not in available documents
            missing_from_available = self.required_document_ids - self.available_document_ids

            if missing_from_available:
                # Automatically add back the missing required documents
                self.available_document_ids = self.available_document_ids | missing_from_available

                missing_names = ", ".join(missing_from_available.mapped("display_name"))
                return {
                    "warning": {
                        "title": _("Required Documents Cannot Be Removed"),
                        "message": _(
                            "The following document types are marked as required and have been "
                            "automatically restored to 'Available Documents':\n\n"
                            "%s\n\n"
                            "To remove them, please first remove them from 'Required Documents'."
                        )
                        % missing_names,
                    }
                }

    # ══════════════════════════════════════════════════════════════════════════
    # APPROVAL CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Workflow",
    )
    auto_approve_from_event = fields.Boolean(default=False)
    use_dynamic_approval = fields.Boolean(
        string="Dynamic Approval",
        default=False,
        help="When enabled, user selects a single field to modify per CR. "
        "The selected field determines which approval workflow applies.",
    )
    candidate_definition_ids = fields.Many2many(
        "spp.approval.definition",
        "cr_type_candidate_definition_rel",
        "type_id",
        "definition_id",
        string="Candidate Approval Definitions",
        help="Evaluated in sequence order; first matching CEL condition wins. "
        "If none match, the default Approval Workflow is used.",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # CONFLICT DETECTION
    # ══════════════════════════════════════════════════════════════════════════

    enable_conflict_detection = fields.Boolean(
        string="Enable Conflict Detection",
        default=False,
        help="Enable automatic detection of conflicting change requests",
    )

    conflict_rule_ids = fields.One2many(
        "spp.cr.conflict.rule",
        "cr_type_id",
        string="Conflict Rules",
        help="Rules for detecting conflicting change requests",
    )

    conflict_rule_count = fields.Integer(
        compute="_compute_conflict_rule_count",
        string="Conflict Rules",
    )

    enable_duplicate_detection = fields.Boolean(
        string="Enable Duplicate Detection",
        default=False,
        help="Enable automatic detection of duplicate change requests",
    )

    duplicate_detection_config_id = fields.Many2one(
        "spp.cr.duplicate.config",
        string="Duplicate Detection Config",
        help="Configuration for duplicate detection",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ID OPERATIONS CONFIGURATION (for update_id type)
    # ══════════════════════════════════════════════════════════════════════════

    allow_id_add = fields.Boolean(
        string="Allow Add ID",
        default=True,
        help="Allow adding new ID documents via this CR type.",
    )
    allow_id_edit = fields.Boolean(
        string="Allow Edit ID",
        default=True,
        help="Allow editing existing ID documents via this CR type.",
    )
    allow_id_remove = fields.Boolean(
        string="Allow Remove ID",
        default=True,
        help="Allow removing ID documents via this CR type.",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # APPLY CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    apply_strategy = fields.Selection(
        [
            ("field_mapping", "Field Mapping"),
            ("custom", "Custom Method"),
            ("manual", "Manual Application"),
        ],
        default="field_mapping",
        required=True,
    )

    # For field_mapping strategy
    apply_mapping_ids = fields.One2many(
        "spp.change.request.type.mapping",
        "type_id",
        string="Apply Mappings",
    )

    # For custom strategy
    apply_model = fields.Char(help="Model containing apply method")
    apply_method = fields.Char(default="apply")
    auto_apply_on_approve = fields.Boolean(default=True)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED
    # ══════════════════════════════════════════════════════════════════════════

    change_request_count = fields.Integer(
        compute="_compute_change_request_count",
        string="Change Requests",
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Proactively guard the unique code constraint so tests get a
        # ValidationError instead of a raw database IntegrityError.
        for vals in vals_list:
            code = vals.get("code")
            if code:
                existing = self.search([("code", "=", code)], limit=1)
                if existing:
                    raise ValidationError(_("CR type code must be unique! Code '%s' already exists.") % code)
        return super().create(vals_list)

    @api.depends("detail_model")
    def _compute_detail_model_exists(self):
        """Check if the detail model exists in the database."""
        for rec in self:
            rec.is_detail_model_exists = bool(rec.detail_model and rec.detail_model in self.env)

    @api.depends("detail_model")
    def _compute_supports_reason_documents(self):
        """A CR type supports reason-driven documents only when its detail model
        exposes a reason field (Change HoH's ``reason``, Split Household's
        ``split_reason`` or Remove Member's ``end_reason``)."""
        for rec in self:
            model = self.env[rec.detail_model] if (rec.detail_model and rec.detail_model in self.env) else None
            rec.supports_reason_documents = bool(
                model
                and ("reason" in model._fields or "split_reason" in model._fields or "end_reason" in model._fields)
            )

    @api.depends("detail_model")
    def _compute_available_field_ids(self):
        """Compute available fields from the detail model."""
        for rec in self:
            if not rec.detail_model or rec.detail_model not in self.env:
                rec.available_field_ids = False
                continue

            # System fields to exclude
            excluded_fields = [
                "id",
                "create_uid",
                "create_date",
                "write_uid",
                "write_date",
                "__last_update",
                "display_name",
                "message_ids",
                "message_follower_ids",
                "message_partner_ids",
                "message_attachment_count",
                "website_message_ids",
                "activity_ids",
                "activity_state",
                "activity_user_id",
                "activity_type_id",
                "activity_date_deadline",
                "activity_summary",
                "message_is_follower",
                "message_needaction",
                "message_needaction_counter",
                "message_has_error",
                "message_has_error_counter",
                "message_unread",
                "message_unread_counter",
            ]

            # Get all fields for the detail model
            fields_model = self.env["ir.model.fields"].search(
                [
                    ("model", "=", rec.detail_model),
                    ("name", "not in", excluded_fields),
                    ("store", "=", True),  # Only stored fields
                ]
            )
            rec.available_field_ids = fields_model

    @api.depends()
    def _compute_change_request_count(self):
        for rec in self:
            rec.change_request_count = self.env["spp.change.request"].search_count([("request_type_id", "=", rec.id)])

    @api.depends("conflict_rule_ids")
    def _compute_conflict_rule_count(self):
        for rec in self:
            rec.conflict_rule_count = len(rec.conflict_rule_ids)

    # ══════════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ══════════════════════════════════════════════════════════════════════════

    _code_uniq = models.Constraint("UNIQUE(code)", "CR type code must be unique!")

    @api.constrains("code")
    def _check_code_unique(self):
        """Python constraint for code uniqueness (supplements SQL constraint)."""
        for rec in self:
            if rec.code:
                existing = self.search([("code", "=", rec.code), ("id", "!=", rec.id)], limit=1)
                if existing:
                    raise ValidationError(_("CR type code must be unique! Code '%s' already exists.") % rec.code)

    @api.constrains("detail_model")
    def _check_detail_model(self):
        for rec in self:
            if rec.detail_model and rec.detail_model not in self.env:
                raise ValidationError(_("Detail model does not exist: %s") % rec.detail_model)

    @api.constrains("apply_strategy", "apply_model")
    def _check_apply_config(self):
        for rec in self:
            if rec.apply_strategy == "custom" and not rec.apply_model:
                raise ValidationError(_("Custom apply strategy requires an apply model."))

    # ══════════════════════════════════════════════════════════════════════════
    # METHODS
    # ══════════════════════════════════════════════════════════════════════════

    def get_detail_form_view_id(self):
        """Get the form view ID for the detail model."""
        self.ensure_one()
        if self.detail_form_view_id:
            return self.detail_form_view_id.id
        # Find default view for detail model
        view = self.env["ir.ui.view"].search(
            [
                ("model", "=", self.detail_model),
                ("type", "=", "form"),
            ],
            limit=1,
        )
        return view.id if view else False

    def get_apply_strategy(self):
        """Get the apply strategy handler."""
        self.ensure_one()
        if self.apply_strategy == "field_mapping":
            return self.env["spp.cr.strategy.field_mapping"]
        elif self.apply_strategy == "custom" and self.apply_model:
            if self.apply_model in self.env:
                return self.env[self.apply_model]
            raise UserError(_("Apply model not found: %s") % self.apply_model)
        return self.env["spp.cr.strategy.manual"]

    def action_view_change_requests(self):
        """View all change requests of this type."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Change Requests - %s") % self.name,
            "res_model": "spp.change.request",
            "view_mode": "list,form",
            "domain": [("request_type_id", "=", self.id)],
            "context": {"default_request_type_id": self.id},
        }

    def action_view_conflict_rules(self):
        """View conflict rules for this CR type."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Conflict Rules - %s") % self.name,
            "res_model": "spp.cr.conflict.rule",
            "view_mode": "list,form",
            "domain": [("cr_type_id", "=", self.id)],
            "context": {"default_cr_type_id": self.id},
        }

    def validate_required_fields(self, detail_record):
        """Validate that all required fields are filled in the detail record.

        Args:
            detail_record: recordset of the detail model

        Returns:
            tuple: (is_valid, list of missing field labels)
        """
        self.ensure_one()
        if not self.required_field_ids or not detail_record:
            return True, []

        missing_fields = []
        for field in self.required_field_ids:
            field_name = field.name
            field_value = detail_record[field_name]

            # Check if field is empty based on field type
            is_empty = False
            if field.ttype in ("char", "text", "html"):
                is_empty = not field_value or not field_value.strip()
            elif field.ttype in ("many2one", "many2many", "one2many"):
                is_empty = not field_value
            elif field.ttype in ("integer", "float", "monetary"):
                is_empty = field_value is False or field_value == 0
            elif field.ttype == "boolean":
                # Booleans are always considered filled
                is_empty = False
            elif field.ttype in ("date", "datetime"):
                is_empty = not field_value
            elif field.ttype == "selection":
                is_empty = not field_value
            else:
                is_empty = not field_value

            if is_empty:
                missing_fields.append(field.field_description)

        return len(missing_fields) == 0, missing_fields


class SPPCRTypeReasonDocument(models.Model):
    """Maps a request reason to the set of documents required for it (OP#873/#877).

    Configured on a change request type; consumed by
    spp.change.request._get_effective_required_document_ids(). The reason values
    union the reasons of the CR types that expose a reason (Change HoH, Split
    Household); only the values relevant to a given type's reason will match."""

    _name = "spp.cr.type.reason.document"
    _description = "CR Type: Required Documents by Reason"
    _order = "cr_type_id, reason"

    cr_type_id = fields.Many2one(
        "spp.change.request.type",
        string="Change Request Type",
        required=True,
        ondelete="cascade",
    )
    reason = fields.Selection(
        [
            # Change Head of Household reasons
            ("deceased", "Head Deceased"),
            ("incapacitated", "Head Incapacitated"),
            ("left_household", "Head Left Household"),
            ("age_change", "Age-based Change"),
            # Split Household reasons
            ("marriage", "Marriage"),
            ("separation", "Separation/Divorce"),
            ("independence", "Member Independence"),
            ("relocation", "Relocation"),
            # Remove Member reasons (deceased / left_household shared above)
            ("migrated", "Migrated"),
            # Shared
            ("correction", "Data Correction"),
            ("other", "Other"),
        ],
        string="Reason",
        required=True,
    )
    required_document_ids = fields.Many2many(
        "spp.vocabulary.code",
        "cr_type_reason_doc_rel",
        "rule_id",
        "doc_id",
        string="Required Documents",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:cr_document_type')]",
        help="Documents required when the request's reason matches this rule.",
    )

    _reason_uniq = models.Constraint(
        "unique(cr_type_id, reason)",
        "A reason can only have one document rule per change request type.",
    )
