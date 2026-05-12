# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CR Detail: Manage Land Parcels.

Allows adding, updating, or removing land parcels
through the change request approval workflow.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SPPCRDetailManageLandParcel(models.Model):
    """Detail model for Manage Land Parcel CR type."""

    _name = "spp.cr.detail.manage_land_parcel"
    _description = "CR Detail: Manage Land Parcel"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # OPERATION
    # ══════════════════════════════════════════════════════════════════════════

    operation = fields.Selection(
        [
            ("add", "Add Land Parcel"),
            ("update", "Edit Land Parcel"),
            ("remove", "Remove Land Parcel"),
        ],
        string="Operation",
        default="add",
        tracking=True,
    )

    operation_display = fields.Char(
        compute="_compute_operation_display",
    )

    is_operation_locked = fields.Boolean(
        default=False,
        help="Set to True when user proceeds to Documents or Review stage to prevent changes.",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # OPERATION AVAILABILITY (from CR type config)
    # ══════════════════════════════════════════════════════════════════════════

    allow_parcel_add = fields.Boolean(
        related="change_request_id.request_type_id.allow_parcel_add",
        readonly=True,
    )
    allow_parcel_update = fields.Boolean(
        related="change_request_id.request_type_id.allow_parcel_update",
        readonly=True,
    )
    allow_parcel_remove = fields.Boolean(
        related="change_request_id.request_type_id.allow_parcel_remove",
        readonly=True,
    )

    @api.depends("operation")
    def _compute_operation_display(self):
        """Compute display label for locked operation."""
        labels = dict(self._fields["operation"].selection)
        for record in self:
            record.operation_display = labels.get(record.operation, "")

    @api.constrains("operation")
    def _check_operation_allowed(self):
        """Validate that the chosen operation is allowed by the CR type config."""
        for rec in self:
            if not rec.change_request_id or not rec.change_request_id.request_type_id:
                continue
            cr_type = rec.change_request_id.request_type_id
            if rec.operation == "update" and not cr_type.allow_parcel_update:
                raise ValidationError(_("Edit Land Parcel operation is not allowed for this change request type."))
            if rec.operation == "remove" and not cr_type.allow_parcel_remove:
                raise ValidationError(_("Remove Land Parcel operation is not allowed for this change request type."))

    # ══════════════════════════════════════════════════════════════════════════
    # EXISTING LAND PARCEL REFERENCE (for update/remove)
    # ══════════════════════════════════════════════════════════════════════════

    land_record_id = fields.Many2one(
        "spp.land.record",
        string="Land Parcel",
        domain="[('land_farm_id', '=', registrant_id)]",
        tracking=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # LAND PARCEL INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    land_name = fields.Char(string="Parcel Name/ID", tracking=True)
    land_acreage = fields.Float(string="Acreage", tracking=True)
    land_use_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Land Use",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:land-use')]",
        tracking=True,
    )
    owner_id = fields.Many2one("res.partner", string="Owner", tracking=True)
    lessee_id = fields.Many2one("res.partner", string="Lessee", tracking=True)
    lease_start = fields.Date(string="Lease Start", tracking=True)
    lease_end = fields.Date(string="Lease End", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ONCHANGE HANDLERS
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange("operation")
    def _onchange_operation(self):
        """Clear fields when operation changes."""
        self.land_record_id = False
        self.land_name = False
        self.land_acreage = 0
        self.land_use_id = False
        self.owner_id = False
        self.lessee_id = False
        self.lease_start = False
        self.lease_end = False

    @api.onchange("land_record_id")
    def _onchange_land_record_id(self):
        """Pre-fill current values from selected land parcel."""
        if self.land_record_id:
            rec = self.land_record_id
            self.land_name = rec.land_name
            self.land_acreage = rec.land_acreage
            self.land_use_id = rec.land_use_id
            self.owner_id = rec.owner_id
            self.lessee_id = rec.lessee_id
            self.lease_start = rec.lease_start
            self.lease_end = rec.lease_end

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE NAVIGATION (lock operation)
    # ══════════════════════════════════════════════════════════════════════════

    def action_next_documents(self):
        """Lock operation before proceeding to documents stage."""
        self.write({"is_operation_locked": True})
        return super().action_next_documents()

    def action_skip_to_review(self):
        """Lock operation before skipping to review stage."""
        self.write({"is_operation_locked": True})
        return super().action_skip_to_review()
