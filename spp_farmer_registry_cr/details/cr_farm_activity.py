# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CR Detail: Manage Farm Activity.

Allows adding, updating, or removing crop, livestock, or aquaculture activities
through the change request approval workflow.

Follows the same pattern as Update ID Document in OpenSPP2, using an
'operation' field to distinguish between add, update, and remove actions.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SPPCRDetailManageFarmActivity(models.Model):
    """Detail model for Manage Farm Activity CR type."""

    _name = "spp.cr.detail.manage_farm_activity"
    _description = "CR Detail: Manage Farm Activity"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # OPERATION
    # ══════════════════════════════════════════════════════════════════════════

    operation = fields.Selection(
        [
            ("add", "Add Activity"),
            ("update", "Edit Activity"),
            ("remove", "Remove Activity"),
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

    allow_activity_add = fields.Boolean(
        related="change_request_id.request_type_id.allow_activity_add",
        readonly=True,
    )
    allow_activity_update = fields.Boolean(
        related="change_request_id.request_type_id.allow_activity_update",
        readonly=True,
    )
    allow_activity_remove = fields.Boolean(
        related="change_request_id.request_type_id.allow_activity_remove",
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
            if rec.operation == "update" and not cr_type.allow_activity_update:
                raise ValidationError(_("Edit Activity operation is not allowed for this change request type."))
            if rec.operation == "remove" and not cr_type.allow_activity_remove:
                raise ValidationError(_("Remove Activity operation is not allowed for this change request type."))

    # ══════════════════════════════════════════════════════════════════════════
    # EXISTING ACTIVITY REFERENCE (for update/remove)
    # ══════════════════════════════════════════════════════════════════════════

    activity_id = fields.Many2one(
        "spp.farm.activity",
        string="Activity",
        domain="[('farm_id', '=', registrant_id)]",
        tracking=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIVITY INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    activity_type = fields.Selection(
        [
            ("crop", "Crop Cultivation"),
            ("livestock", "Livestock Rearing"),
            ("aquaculture", "Aquaculture"),
        ],
        string="Activity Type",
        tracking=True,
    )

    species_namespace = fields.Char(
        compute="_compute_species_namespace",
        store=True,
    )

    species_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Species/Crop",
        domain="[('namespace_uri', '=', species_namespace)]",
        tracking=True,
    )

    purpose_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Purpose",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:activity-purpose')]",
        tracking=True,
    )

    cultivation_method_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Cultivation Method",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:cultivation-method')]",
        tracking=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # QUANTITIES
    # ══════════════════════════════════════════════════════════════════════════

    quantity = fields.Integer(string="Quantity", tracking=True)
    quantity_unit = fields.Char(string="Unit", tracking=True)
    area_planted = fields.Float(string="Area Planted (hectares)", tracking=True)
    expected_yield = fields.Float(string="Expected Yield", tracking=True)
    actual_yield = fields.Float(string="Actual Yield", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # SEASON & LOCATION
    # ══════════════════════════════════════════════════════════════════════════

    season_id = fields.Many2one(
        "spp.farm.season",
        string="Agricultural Season",
        domain="[('state', '=', 'active')]",
        tracking=True,
    )

    land_id = fields.Many2one(
        "spp.land.record",
        string="Land Parcel",
        tracking=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends("activity_type")
    def _compute_species_namespace(self):
        """Compute the vocabulary namespace based on activity type."""
        namespace_map = {
            "crop": "urn:fao:icc:1.1",
            "livestock": "urn:fao:livestock:2020",
            "aquaculture": "urn:fao:asfis:2024",
        }
        for record in self:
            record.species_namespace = namespace_map.get(record.activity_type, "")

    # ══════════════════════════════════════════════════════════════════════════
    # ONCHANGE HANDLERS
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange("operation")
    def _onchange_operation(self):
        """Clear fields when operation changes."""
        self.activity_id = False
        self.activity_type = False
        self.species_id = False
        self.purpose_id = False
        self.cultivation_method_id = False
        self.quantity = 0
        self.quantity_unit = False
        self.area_planted = 0
        self.expected_yield = 0
        self.actual_yield = 0

    @api.onchange("activity_id")
    def _onchange_activity_id(self):
        """Pre-fill current values from selected activity."""
        if self.activity_id:
            act = self.activity_id
            self.activity_type = act.activity_type
            self.species_id = act.species_id
            self.purpose_id = act.purpose_id
            self.cultivation_method_id = act.cultivation_method_id
            self.quantity = act.quantity
            self.quantity_unit = act.quantity_unit
            self.area_planted = act.area_planted
            self.expected_yield = act.expected_yield
            self.actual_yield = act.actual_yield
            self.season_id = act.season_id
            self.land_id = act.land_id

    @api.onchange("activity_type")
    def _onchange_activity_type(self):
        """Clear species when activity type changes."""
        if self.operation == "add":
            self.species_id = False

    @api.model
    def default_get(self, fields_list):
        """Set default season to most recent active season."""
        res = super().default_get(fields_list)
        if "season_id" in fields_list:
            active_season = self.env["spp.farm.season"].search(
                [("state", "=", "active")],
                order="date_start desc",
                limit=1,
            )
            if active_season:
                res["season_id"] = active_season.id
        return res

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
