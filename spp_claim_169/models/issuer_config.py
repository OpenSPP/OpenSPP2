import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Claim169IssuerConfig(models.Model):
    """
    Configuration for Claim 169 credential issuers.

    Defines issuer identity, signing keys, and validity periods
    for generated credentials.
    """

    _name = "spp.claim169.issuer.config"
    _description = "Claim 169 Issuer Configuration"
    _order = "name"

    name = fields.Char(string="Issuer Name", required=True, help="Descriptive name for this issuer configuration")

    issuer_id = fields.Char(
        string="Issuer ID", required=True, help="DID or identifier for the 'iss' claim (e.g., 'did:example:issuer123')"
    )

    signing_key_id = fields.Many2one(
        comodel_name="spp.asymmetric.key",
        string="Signing Key",
        required=True,
        help="Asymmetric key used to sign credentials (Ed25519 or EC recommended)",
    )

    default_validity_days = fields.Integer(
        string="Default Validity (Days)",
        required=True,
        default=365,
        help="Default number of days credentials are valid for",
    )

    is_default = fields.Boolean(
        string="Default Issuer", default=False, help="Use this issuer by default when generating credentials"
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        help="Company this issuer belongs to",
    )

    credential_count = fields.Integer(
        string="Credentials Issued",
        compute="_compute_credential_count",
        help="Total number of credentials issued by this issuer",
    )

    active = fields.Boolean(string="Active", default=True, help="Inactive issuers cannot be used for new credentials")

    @api.depends("issuer_id")
    def _compute_credential_count(self):
        """Count credentials issued by this issuer."""
        for record in self:
            record.credential_count = self.env["spp.claim169.credential"].search_count(
                [("issuer_config_id", "=", record.id)]
            )

    @api.constrains("default_validity_days")
    def _check_validity_days(self):
        """Validate that validity days is positive."""
        for record in self:
            if record.default_validity_days < 1:
                raise ValidationError(_("Validity days must be at least 1 (got %s)") % record.default_validity_days)

    @api.constrains("is_default")
    def _check_unique_default(self):
        """Ensure only one default issuer per company."""
        default_records = self.filtered("is_default")
        if not default_records:
            return
        # Prefetch company_ids to avoid N+1 query
        company_map = {rec.id: rec.company_id.id for rec in default_records}
        for record in default_records:
            company_id = company_map.get(record.id, False)
            duplicate = self.search(
                [
                    ("id", "!=", record.id),
                    ("is_default", "=", True),
                    ("company_id", "=", company_id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("Only one default issuer allowed per company. " "'%s' is already set as default.")
                    % duplicate.name
                )

    def action_view_credentials(self):
        """Open list view of credentials issued by this issuer."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Credentials - %s") % self.name,
            "res_model": "spp.claim169.credential",
            "view_mode": "list,form",
            "domain": [("issuer_config_id", "=", self.id)],
            "context": {"default_issuer_config_id": self.id},
        }
