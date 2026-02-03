# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Server Signing Key Management.

Manages the server's private signing keys for outbound DCI responses.
Only one key should be active at a time.
"""

import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class DCIServerKey(models.Model):
    """DCI Server Signing Key for outbound message signing.

    Stores Ed25519 keypairs for signing server responses, callbacks, and notifications.
    Enforces single active key policy for security.
    """

    _name = "spp.dci.server.key"
    _description = "DCI Server Signing Key"
    _order = "created_date desc, id desc"

    name = fields.Char(
        required=True,
        string="Key Name",
        help="Descriptive name for this signing key",
    )
    key_id = fields.Char(
        required=True,
        string="Key Identifier",
        help="Unique identifier for this key (e.g., 'server-2024-01')",
    )
    algorithm = fields.Selection(
        [
            ("ed25519", "Ed25519"),
        ],
        required=True,
        default="ed25519",
        string="Algorithm",
        help="Cryptographic signing algorithm (Ed25519 only for server keys)",
    )
    private_key = fields.Text(
        string="Private Key",
        help="PEM-encoded private key (access restricted)",
        groups="base.group_system",
    )
    public_key = fields.Text(
        string="Public Key",
        help="PEM-encoded public key",
    )
    active = fields.Boolean(
        default=False,
        string="Active",
        help="Only one key can be active at a time",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("revoked", "Revoked"),
        ],
        default="draft",
        required=True,
        string="State",
        tracking=True,
        help="Key lifecycle state",
    )
    created_date = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True,
        string="Created Date",
    )
    activated_date = fields.Datetime(
        readonly=True,
        string="Activated Date",
    )
    revoked_date = fields.Datetime(
        readonly=True,
        string="Revoked Date",
    )
    expires_at = fields.Datetime(
        string="Expiration Date",
        help="Optional expiration date for key rotation",
    )

    _key_id_uniq = models.Constraint(
        "UNIQUE(key_id)",
        "Key ID must be unique",
    )

    @api.constrains("key_id")
    def _check_key_id_format(self):
        """Validate key_id format - alphanumeric and hyphens only."""
        for record in self:
            if record.key_id and not all(c.isalnum() or c in "-_" for c in record.key_id):
                raise ValidationError(_("Key ID must contain only alphanumeric characters, hyphens, and underscores."))

    @api.constrains("state", "private_key", "public_key")
    def _check_keys_present(self):
        """Ensure keys are generated before activation."""
        for record in self:
            if record.state == "active" and (not record.private_key or not record.public_key):
                raise ValidationError(_("Cannot activate key without generating key pair. Please generate keys first."))

    @api.constrains("expires_at")
    def _check_expiration_date(self):
        """Ensure expiration date is in the future."""
        for record in self:
            if record.expires_at and record.expires_at <= fields.Datetime.now():
                raise ValidationError(_("Expiration date must be in the future."))

    @api.constrains("active")
    def _check_single_active_key(self):
        """Ensure only one key is active at a time."""
        for record in self:
            if record.active:
                other_active = self.search(
                    [
                        ("active", "=", True),
                        ("id", "!=", record.id),
                        ("state", "=", "active"),
                    ],
                    limit=1,
                )
                if other_active:
                    raise ValidationError(
                        _("Only one server key can be active at a time. " "Please deactivate key '%s' first.")
                        % other_active.name
                    )

    def action_generate_key(self):
        """Generate new Ed25519 keypair."""
        self.ensure_one()

        if self.state != "draft":
            raise UserError(_("Keys can only be generated in Draft state. Current state: %s") % self.state)

        if self.private_key or self.public_key:
            raise UserError(
                _("Keys already exist for this record. " "Please create a new key record to generate a new keypair.")
            )

        _logger.info("Generating Ed25519 keypair for server key_id: %s", self.key_id)

        try:
            private_key_pem, public_key_pem = self._generate_ed25519_keypair()

            self.write(
                {
                    "private_key": private_key_pem,
                    "public_key": public_key_pem,
                }
            )

            _logger.info("Successfully generated Ed25519 keypair for server key_id: %s", self.key_id)

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("Server keypair generated successfully for %s") % self.name,
                    "type": "success",
                    "sticky": False,
                },
            }

        except Exception as e:
            _logger.error("Failed to generate keypair for server key_id %s: %s", self.key_id, str(e))
            raise UserError(_("Failed to generate keypair: %s") % str(e)) from e

    def action_activate(self):
        """Activate the signing key for use.

        Deactivates all other keys to enforce single active key policy.
        """
        self.ensure_one()

        if self.state == "active":
            raise UserError(_("Key is already active."))

        if self.state == "revoked":
            raise UserError(_("Cannot activate a revoked key. Please create a new key."))

        if not self.private_key or not self.public_key:
            raise UserError(_("Cannot activate key without generating keypair. Please generate keys first."))

        _logger.info("Activating server signing key: %s (key_id: %s)", self.name, self.key_id)

        # Deactivate all other active keys
        other_active = self.search(
            [
                ("active", "=", True),
                ("id", "!=", self.id),
            ]
        )
        if other_active:
            other_active.write({"active": False})
            _logger.info("Deactivated %d other server keys", len(other_active))

        self.write(
            {
                "state": "active",
                "active": True,
                "activated_date": fields.Datetime.now(),
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Activated"),
                "message": _("Server signing key '%s' is now active") % self.name,
                "type": "success",
            },
        }

    def action_revoke(self):
        """Revoke the signing key."""
        self.ensure_one()

        if self.state == "revoked":
            raise UserError(_("Key is already revoked."))

        _logger.warning("Revoking server signing key: %s (key_id: %s)", self.name, self.key_id)

        self.write(
            {
                "state": "revoked",
                "active": False,
                "revoked_date": fields.Datetime.now(),
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Revoked"),
                "message": _("Server signing key '%s' has been revoked") % self.name,
                "type": "warning",
            },
        }

    def _generate_ed25519_keypair(self):
        """Generate Ed25519 keypair.

        Returns:
            tuple: (private_key_pem, public_key_pem)
        """
        _logger.debug("Generating Ed25519 keypair for server")

        # Generate private key
        private_key = Ed25519PrivateKey.generate()

        # Serialize private key to PEM
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Get public key and serialize to PEM
        public_key = private_key.public_key()
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        return private_key_pem, public_key_pem

    @api.model
    def get_active_key(self):
        """Get the active server signing key.

        Returns:
            spp.dci.server.key: Active key record or empty recordset

        Raises:
            UserError: If no active key is found
        """
        key = self.search(
            [
                ("state", "=", "active"),
                ("active", "=", True),
            ],
            order="activated_date desc",
            limit=1,
        )

        if not key:
            _logger.error("No active server signing key found")
            raise UserError(
                _(
                    "No active server signing key found. "
                    "Please generate and activate a server key in Settings > DCI > Server Keys"
                )
            )

        return key

    def get_signer(self):
        """Get a DCISigner instance configured with this key.

        Returns:
            DCISigner: Configured signer instance
        """
        self.ensure_one()

        if self.state != "active":
            raise UserError(_("Cannot use key in %s state for signing. Please activate it first.") % self.state)

        if not self.private_key:
            raise UserError(_("No private key available for signing."))

        from odoo.addons.spp_dci.services.signing import DCISigner

        sender_id = self.env["ir.config_parameter"].sudo().get_param("dci.sender_id", "openspp")

        return DCISigner(
            private_key=self.private_key.encode("utf-8"),
            sender_id=sender_id,
            key_id=self.key_id,
            algorithm=self.algorithm,
        )
