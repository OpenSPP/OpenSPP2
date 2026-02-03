from odoo import api, fields, models


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
            ("update", "Update Existing ID"),
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
        "spp.id.type",
        string="ID Type",
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

    @api.onchange("existing_id_record_id")
    def _onchange_existing_id(self):
        """Pre-fill fields when updating existing ID."""
        if self.existing_id_record_id and self.operation in ("update", "remove"):
            self.id_type_id = self.existing_id_record_id.id_type_id
            self.id_value = self.existing_id_record_id.value
            self.expiry_date = self.existing_id_record_id.expiry_date
            self.description = self.existing_id_record_id.description

    @api.onchange("operation")
    def _onchange_operation(self):
        """Clear fields when operation changes."""
        if self.operation == "add":
            self.existing_id_record_id = False
