from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SPPCRDetailUpdateID(models.Model):
    """Detail model for Update ID Document CR type."""

    _name = "spp.cr.detail.update_id"
    _description = "CR Detail: Update ID Document"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # ID DOCUMENT INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    operation = fields.Selection(
        [
            ("add", "Add New ID"),
            ("update", "Edit ID"),
            ("remove", "Remove ID"),
        ],
        string="Operation",
        default="add",
        tracking=True,
    )
    existing_id_record_id = fields.Many2one(
        "spp.registry.id",
        string="Existing ID Record",
        tracking=True,
        domain="[('partner_id', '=', registrant_id)]",
        help="Select existing ID to update or remove",
    )
    id_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="ID Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:id-type')]",
        tracking=True,
    )
    id_value = fields.Char(
        string="ID Number/Value",
        tracking=True,
        help="The identification number or value",
    )
    expiry_date = fields.Date(
        string="Expiry Date",
        tracking=True,
    )
    description = fields.Text(
        string="Description",
        tracking=True,
    )
    document_attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Supporting Documents",
        help="Upload scanned copies or photos of the ID document",
    )
    remarks = fields.Text(string="Remarks", tracking=True)
    is_operation_locked = fields.Boolean(
        string="Operation Locked",
        default=False,
        help="Set to True when user proceeds to Documents or Review stage, locking the operation selection.",
    )
    operation_display = fields.Char(
        string="Operation",
        compute="_compute_operation_display",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    registrant_name = fields.Char(
        string="Registrant Name",
        related="change_request_id.registrant_id.name",
        readonly=True,
    )
    current_id_value = fields.Char(
        string="Current ID Value",
        related="existing_id_record_id.value",
        readonly=True,
    )

    allow_id_add = fields.Boolean(
        related="change_request_id.request_type_id.allow_id_add",
        readonly=True,
    )
    allow_id_edit = fields.Boolean(
        related="change_request_id.request_type_id.allow_id_edit",
        readonly=True,
    )
    allow_id_remove = fields.Boolean(
        related="change_request_id.request_type_id.allow_id_remove",
        readonly=True,
    )

    @api.depends("operation")
    def _compute_operation_display(self):
        labels = dict(self._fields["operation"].selection)
        for rec in self:
            rec.operation_display = labels.get(rec.operation, "")

    def action_next_documents(self):
        """Lock operation before proceeding to documents stage."""
        self.write({"is_operation_locked": True})
        return super().action_next_documents()

    def action_skip_to_review(self):
        """Lock operation before proceeding to review stage."""
        self.write({"is_operation_locked": True})
        return super().action_skip_to_review()

    @api.constrains("operation")
    def _check_operation_allowed(self):
        """Validate that the chosen operation is allowed by the CR type config."""
        for rec in self:
            if not rec.change_request_id or not rec.change_request_id.request_type_id:
                continue
            cr_type = rec.change_request_id.request_type_id
            if rec.operation == "update" and not cr_type.allow_id_edit:
                raise ValidationError(_("Edit ID operation is not allowed for this change request type."))
            if rec.operation == "remove" and not cr_type.allow_id_remove:
                raise ValidationError(_("Remove ID operation is not allowed for this change request type."))

    @api.onchange("existing_id_record_id")
    def _onchange_existing_id(self):
        """Pre-fill fields when updating existing ID."""
        if self.existing_id_record_id and self.operation in ("update", "remove"):
            self.id_type_id = self.existing_id_record_id.id_type_id
            self.id_value = self.existing_id_record_id.value
            self.expiry_date = self.existing_id_record_id.expiry_date

    @api.onchange("operation")
    def _onchange_operation(self):
        """Clear fields when operation changes. Reset if operation not allowed."""
        # Check if selected operation is allowed
        warning = None
        if self.operation == "update" and not self.allow_id_edit:
            self.operation = "add"
            warning = {
                "title": _("Operation Not Allowed"),
                "message": _("Edit ID is disabled for this change request type."),
            }
        elif self.operation == "remove" and not self.allow_id_remove:
            self.operation = "add"
            warning = {
                "title": _("Operation Not Allowed"),
                "message": _("Remove ID is disabled for this change request type."),
            }

        # Unlock operation when changed (user came back to edit)
        self.is_operation_locked = False

        # Clear fields common to all operations
        self.id_type_id = False
        self.id_value = False
        self.expiry_date = False
        if self.operation == "add":
            self.existing_id_record_id = False

        if warning:
            return {"warning": warning}
