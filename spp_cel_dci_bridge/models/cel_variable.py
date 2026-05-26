from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CELVariable(models.Model):
    _inherit = "spp.cel.variable"

    # Related field so views can gate visibility/required on the provider's
    # is_dci_backed flag without writing a chained dotted-path expression
    # (which Odoo's view validator rejects).
    external_provider_is_dci_backed = fields.Boolean(
        related="external_provider_id.is_dci_backed",
        store=False,
        readonly=True,
    )

    dci_attribute_path = fields.Char(
        string="DCI Attribute Path",
        help=(
            "Dotted path into the DCI response payload "
            "(e.g., 'has_disability', 'severity.code', "
            "'functional_scores.cognition'). Required when the variable's "
            "external provider is DCI-backed."
        ),
    )

    # Per-variable operation hint for registries that expose multiple
    # endpoints. Today this only affects CRVS (which has separate search
    # paths for birth and death events). Other registries dispatch by
    # registry_type alone and ignore this field — keep 'auto' for them.
    dci_operation = fields.Selection(
        selection=[
            ("auto", "Auto (registry default)"),
            ("verify_birth", "CRVS: verify birth"),
            ("check_death", "CRVS: check death"),
        ],
        default="auto",
        string="DCI Operation",
        help=(
            "Which DCI operation the bridge should invoke when fetching this "
            "variable. 'auto' uses the registry's default (verify_birth for "
            "CRVS). 'check_death' calls CRVS's death-event endpoint instead — "
            "the resulting payload is a single key 'is_deceased' (bool), so "
            "set DCI Attribute Path = 'is_deceased' on the variable record."
        ),
    )

    external_failure_policy = fields.Selection(
        selection=[
            ("null", "Return null (default)"),
            ("last_known", "Return last known value"),
            ("fail", "Propagate exception"),
        ],
        default="null",
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
