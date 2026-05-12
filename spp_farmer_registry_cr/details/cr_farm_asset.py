# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CR Detail: Manage Farm Assets.

Allows adding, updating, or removing farm assets and machinery
through the change request approval workflow.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SPPCRDetailManageFarmAsset(models.Model):
    """Detail model for Manage Farm Asset CR type."""

    _name = "spp.cr.detail.manage_farm_asset"
    _description = "CR Detail: Manage Farm Asset"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # OPERATION
    # ══════════════════════════════════════════════════════════════════════════

    operation = fields.Selection(
        [
            ("add", "Add Asset"),
            ("update", "Edit Asset"),
            ("remove", "Remove Asset"),
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
        help="Set to True when user proceeds to Documents or Review stage.",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # OPERATION AVAILABILITY (from CR type config)
    # ══════════════════════════════════════════════════════════════════════════

    allow_asset_add = fields.Boolean(
        related="change_request_id.request_type_id.allow_asset_add",
        readonly=True,
    )
    allow_asset_update = fields.Boolean(
        related="change_request_id.request_type_id.allow_asset_update",
        readonly=True,
    )
    allow_asset_remove = fields.Boolean(
        related="change_request_id.request_type_id.allow_asset_remove",
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
            if rec.operation == "update" and not cr_type.allow_asset_update:
                raise ValidationError(_("Edit Asset operation is not allowed for this change request type."))
            if rec.operation == "remove" and not cr_type.allow_asset_remove:
                raise ValidationError(_("Remove Asset operation is not allowed for this change request type."))

    # ══════════════════════════════════════════════════════════════════════════
    # ASSET CATEGORY (asset vs machinery)
    # ══════════════════════════════════════════════════════════════════════════

    asset_category = fields.Selection(
        [
            ("asset", "Asset"),
            ("machinery", "Machinery"),
        ],
        string="Asset Category",
        default="asset",
        tracking=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # EXISTING ASSET REFERENCE (for update/remove)
    # ══════════════════════════════════════════════════════════════════════════

    farm_asset_id = fields.Many2one(
        "spp.farm.asset",
        string="Asset Record",
        domain="[('asset_farm_id', '=', registrant_id)]",
        tracking=True,
    )
    farm_machinery_id = fields.Many2one(
        "spp.farm.asset",
        string="Machinery Record",
        domain="[('machinery_farm_id', '=', registrant_id)]",
        tracking=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ASSET FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    asset_type_id = fields.Many2one("spp.asset.type", string="Asset Type", tracking=True)
    technology_used = fields.Char(string="Technology Used", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # MACHINERY FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    machinery_type_id = fields.Many2one("spp.machinery.type", string="Machinery Type", tracking=True)
    machine_working_status = fields.Char(string="Working Status", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # COMMON FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    quantity = fields.Integer(string="Quantity", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ONCHANGE HANDLERS
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange("operation", "asset_category")
    def _onchange_operation_or_category(self):
        """Clear fields when operation or category changes."""
        self.farm_asset_id = False
        self.farm_machinery_id = False
        self.asset_type_id = False
        self.technology_used = False
        self.machinery_type_id = False
        self.machine_working_status = False
        self.quantity = 0

    @api.onchange("farm_asset_id")
    def _onchange_farm_asset_id(self):
        """Pre-fill from selected asset record."""
        if self.farm_asset_id:
            self.asset_type_id = self.farm_asset_id.asset_type_id
            self.technology_used = self.farm_asset_id.technology_used
            self.quantity = self.farm_asset_id.quantity

    @api.onchange("farm_machinery_id")
    def _onchange_farm_machinery_id(self):
        """Pre-fill from selected machinery record."""
        if self.farm_machinery_id:
            self.machinery_type_id = self.farm_machinery_id.machinery_type_id
            self.machine_working_status = self.farm_machinery_id.machine_working_status
            self.quantity = self.farm_machinery_id.quantity

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
