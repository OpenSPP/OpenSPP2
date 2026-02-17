import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SimulationEntitlementRule(models.Model):
    """Amount calculation rules for a simulation scenario."""

    _name = "spp.simulation.entitlement.rule"
    _description = "Simulation Entitlement Rule"
    _order = "sequence, id"

    scenario_id = fields.Many2one(
        comodel_name="spp.simulation.scenario",
        string="Scenario",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Rule Name")
    amount_mode = fields.Selection(
        selection=[
            ("fixed", "Fixed Amount"),
            ("multiplier", "Multiplier"),
            ("cel", "CEL Expression"),
        ],
        string="Amount Mode",
        required=True,
        default="fixed",
    )
    amount = fields.Float(
        string="Amount",
        help="Fixed amount per beneficiary (used when mode is 'Fixed Amount').",
    )
    multiplier_field = fields.Char(
        string="Multiplier Field",
        help="Field name to multiply by (e.g., 'household_size'). Used when mode is 'Multiplier'.",
    )
    max_multiplier = fields.Float(
        string="Maximum Multiplier",
        default=0,
        help="Maximum multiplier value. 0 means no limit.",
    )
    amount_cel_expression = fields.Text(
        string="Amount CEL Expression",
        help="CEL expression returning the amount per beneficiary. Used when mode is 'CEL Expression'.",
    )
    condition_cel_expression = fields.Text(
        string="Condition Expression (CEL)",
        help="Optional sub-filter within the targeted population. "
        "Only beneficiaries matching this condition receive this entitlement.",
    )

    @api.constrains("amount_mode", "amount")
    def _check_fixed_amount(self):
        for record in self:
            if record.amount_mode == "fixed" and record.amount < 0:
                raise ValidationError(_("Fixed amount cannot be negative."))

    @api.constrains("amount_mode", "multiplier_field")
    def _check_multiplier_field(self):
        for record in self:
            if record.amount_mode == "multiplier" and not record.multiplier_field:
                raise ValidationError(_("Multiplier field is required when amount mode is 'Multiplier'."))

    @api.constrains("amount_mode", "amount_cel_expression")
    def _check_cel_expression(self):
        for record in self:
            if record.amount_mode == "cel" and not record.amount_cel_expression:
                raise ValidationError(_("CEL expression is required when amount mode is 'CEL Expression'."))
