from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CELVariable(models.Model):
    _inherit = "spp.cel.variable"

    dci_attribute_path = fields.Char(
        string="DCI Attribute Path",
        help=(
            "Dotted path into the DCI response payload "
            "(e.g., 'has_disability', 'severity.code', "
            "'functional_scores.cognition'). Required when the variable's "
            "external provider is DCI-backed."
        ),
    )

    external_failure_policy = fields.Selection(
        selection=[
            ("null", "Return null (default)"),
            ("last_known", "Return last known value"),
            ("fail", "Propagate exception"),
        ],
        default="null",
        string="External Failure Policy",
        help=(
            "Behaviour when the external DCI fetch fails for a subject:\n"
            "- null: cache value as null; CEL evaluates against null.\n"
            "- last_known: return the most recent non-null cached value, "
            "regardless of expiry. Log a warning.\n"
            "- fail: propagate the exception. Use for compliance-critical "
            "rules."
        ),
    )

    @api.constrains("source_type", "external_provider_id", "dci_attribute_path")
    def _check_dci_attribute_path(self):
        for rec in self:
            if (
                rec.source_type == "external"
                and rec.external_provider_id
                and rec.external_provider_id.is_dci_backed
                and not rec.dci_attribute_path
            ):
                raise ValidationError(_("DCI-backed external variables must define a DCI Attribute Path."))
