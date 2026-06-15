# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""SR Sender Registry - Trusted Social Registry systems for DCI callbacks."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SRSender(models.Model):
    """Registry of trusted Social Registry senders.

    Stores information about external Social Registry systems that can
    send DCI callbacks to this OpenSPP instance (when deployed as MIS).
    Each sender must have a registered public key for signature verification.
    """

    _name = "spp.dci.sr.sender"
    _description = "DCI Social Registry Sender"
    _order = "name"

    name = fields.Char(
        string="Name",
        required=True,
        help="Human-readable name for this SR (e.g., 'National Social Registry')",
    )
    sender_id = fields.Char(
        string="Sender ID",
        required=True,
        index=True,
        help="Unique identifier used in DCI message headers (e.g., 'sr.example.gov')",
    )
    base_url = fields.Char(
        string="Base URL",
        help="Base URL of the SR API (e.g., 'https://sr.example.gov/api/v1')",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive senders will not be trusted for callbacks",
    )

    # Signature verification
    # Selection keys must match the lowercase identifiers expected by
    # DCIVerifier (spp_dci.services.signing) and by the other DCI sender
    # models (crvs/dr/ibr/server). ES256 is omitted because the verifier
    # does not implement it.
    algorithm = fields.Selection(
        selection=[
            ("ed25519", "Ed25519"),
            ("rs256", "RSA-256"),
        ],
        string="Algorithm",
        default="ed25519",
        required=True,
        help="Signature algorithm used by this SR",
    )
    public_key = fields.Text(
        string="Public Key",
        help="PEM-encoded public key for signature verification",
    )

    # Metadata
    description = fields.Text(
        string="Description",
        help="Additional notes about this SR",
    )
    country_id = fields.Many2one(
        comodel_name="res.country",
        string="Country",
        help="Country where this SR operates",
    )

    _sender_id_unique = models.Constraint(
        "UNIQUE(sender_id)",
        "Sender ID must be unique",
    )

    @api.constrains("public_key", "algorithm")
    def _check_public_key(self):
        """Validate public key format."""
        for rec in self:
            if rec.public_key:
                if not rec.public_key.strip().startswith("-----BEGIN"):
                    raise ValidationError(_("Public key must be in PEM format (starting with -----BEGIN)"))

    def get_verifier(self):
        """Get DCIVerifier instance for this sender.

        Returns:
            DCIVerifier: Configured verifier for signature validation

        Raises:
            ValidationError: If public key is not configured
        """
        self.ensure_one()

        if not self.public_key:
            raise ValidationError(_("Public key not configured for SR sender '%s'") % self.name)

        from odoo.addons.spp_dci.services.signing import DCIVerifier

        return DCIVerifier(
            algorithm=self.algorithm,
            public_key=self.public_key.encode("utf-8"),
        )

    def action_test_connection(self):
        """Test connection to the SR.

        Returns:
            dict: Action to show result notification
        """
        self.ensure_one()

        if not self.base_url:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Test"),
                    "message": _("Base URL not configured"),
                    "type": "warning",
                    "sticky": False,
                },
            }

        try:
            from odoo.addons.spp_dci_client_sr.services import SRService

            service = SRService(self.env, self.sender_id)
            # Try a simple health check or search (raises on failure)
            service.check_connection()

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Test"),
                    "message": _("Successfully connected to %s") % self.name,
                    "type": "success",
                    "sticky": False,
                },
            }

        except Exception as e:
            _logger.error("SR connection test failed: %s", str(e), exc_info=True)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Test Failed"),
                    "message": str(e),
                    "type": "danger",
                    "sticky": True,
                },
            }
