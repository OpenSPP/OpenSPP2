# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DrimsDonationLine(models.Model):
    _name = "spp.drims.donation.line"
    _description = "DRIMS Donation Line"
    _order = "sequence, id"

    donation_id = fields.Many2one(
        "spp.drims.donation",
        string="Donation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)

    # Product
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
    )

    # Quantities
    # OP#1076: no default — the pledged quantity must be entered explicitly
    # (enforced by _check_quantity_pledged) so it is never silently saved as 0.
    quantity_pledged = fields.Float(
        string="Quantity Pledged",
        required=True,
        help="Original quantity announced by donor",
    )
    quantity_received = fields.Float(
        string="Quantity Received",
        default=0.0,
        help="Actual quantity received at warehouse",
    )
    # Alias for compatibility
    quantity = fields.Float(
        string="Quantity",
        compute="_compute_quantity",
        store=True,
        help="Effective quantity (received if available, otherwise pledged)",
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        required=True,
    )

    # Valuation
    unit_value = fields.Float(
        string="Unit Value",
        help="Estimated value per unit",
    )
    value = fields.Float(
        string="Total Value",
        compute="_compute_value",
        store=True,
    )

    # Condition
    condition_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Condition",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:item-conditions')]",
    )
    disposition_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Disposition",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:item-dispositions')]",
    )

    # Tracking
    lot_number = fields.Char(string="Lot/Batch")
    expiry_date = fields.Date(string="Expiry Date")

    notes = fields.Text(string="Notes")

    # Variance (GAP-DON-003)
    receipt_variance = fields.Float(
        string="Variance",
        compute="_compute_receipt_variance",
        store=True,
        help="Difference between pledged and received quantities (negative if short)",
    )

    @api.depends("quantity_pledged", "quantity_received")
    def _compute_receipt_variance(self):
        """Calculate the variance between pledged and received quantities.

        Variance is always calculated as received - pledged:
        - Positive: received more than pledged
        - Negative: received less than pledged (shortfall)
        - Zero: received exactly as pledged
        """
        for line in self:
            line.receipt_variance = line.quantity_received - line.quantity_pledged

    @api.depends("quantity_pledged", "quantity_received")
    def _compute_quantity(self):
        """Use received quantity if available, otherwise pledged."""
        for line in self:
            line.quantity = line.quantity_received if line.quantity_received > 0 else line.quantity_pledged

    @api.depends("quantity", "unit_value")
    def _compute_value(self):
        for line in self:
            line.value = line.quantity * line.unit_value

    @api.constrains("quantity_pledged")
    def _check_quantity_pledged(self):
        """OP#1076: the pledged quantity must be a positive number."""
        for line in self:
            if line.quantity_pledged <= 0:
                raise ValidationError(_("Pledged quantity must be greater than zero."))

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.unit_value = self.product_id.standard_price

    @api.model_create_multi
    def create(self, vals_list):
        # Set uom_id from product if not provided
        for vals in vals_list:
            if not vals.get("uom_id") and vals.get("product_id"):
                product = self.env["product.product"].browse(vals["product_id"])
                vals["uom_id"] = product.uom_id.id
        records = super().create(vals_list)
        # OP#1055: items can only be added while the donation is in draft. The
        # inspection wizard creates split rows on a received donation and opts
        # out via the allow_donation_line_create context.
        if not self.env.context.get("allow_donation_line_create"):
            for line in records:
                if line.donation_id.state and line.donation_id.state != "draft":
                    raise ValidationError(_("Items can only be added while the donation is in draft."))
        # Invalidate KPI cache for affected incidents
        self._invalidate_incident_kpi_cache(records)
        return records

    def unlink(self):
        # OP#1055: items can only be removed while the donation is in draft.
        for line in self:
            if line.donation_id.state and line.donation_id.state != "draft":
                raise ValidationError(_("Items can only be removed while the donation is in draft."))
        return super().unlink()

    def write(self, vals):
        result = super().write(vals)
        # Invalidate KPI cache for affected incidents
        self._invalidate_incident_kpi_cache(self)
        return result

    def _invalidate_incident_kpi_cache(self, records):
        """Invalidate KPI cache for incidents related to these donation line records.

        This method is called after creating or updating donation lines to ensure
        that cached KPI values (like drims_donation_value) are refreshed to
        reflect the latest donation line data.

        Args:
            records: Recordset of spp.drims.donation.line records to process.
        """
        incident_ids = list(
            set(rec.donation_id.incident_id.id for rec in records if rec.donation_id and rec.donation_id.incident_id)
        )
        if incident_ids:
            DataValue = self.env["spp.data.value"]
            # Delete stale cache entries for donation KPI
            DataValue.search(
                [
                    ("variable_name", "=", "drims_donation_value"),
                    ("subject_model", "=", "spp.hazard.incident"),
                    ("subject_id", "in", incident_ids),
                ]
            ).unlink()
