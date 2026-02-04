import base64
import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class DCISigningKey(models.Model):
    """DCI Signing Key Management.

    Manages cryptographic signing keys for DCI API message authentication.
    Supports Ed25519 and RSA-256 algorithms with state-based lifecycle management.
    """

    _name = "spp.dci.signing.key"
    _description = "DCI Signing Key"
    _order = "created_date desc, id desc"

    name = fields.Char(
        required=True,
        string="Key Name",
        help="Descriptive name for this signing key",
    )
    key_id = fields.Char(
        required=True,
        string="Key Identifier",
        help="Unique identifier for JWKS (e.g., 'key1', 'primary-2024')",
    )
    algorithm = fields.Selection(
        [
            ("ed25519", "Ed25519"),
            ("rs256", "RSA-256"),
        ],
        required=True,
        default="ed25519",
        string="Algorithm",
        help="Cryptographic signing algorithm",
    )
    private_key = fields.Text(
        string="Private Key",
        help="PEM-encoded private key (stored encrypted)",
        groups="base.group_system",
    )
    public_key = fields.Text(
        string="Public Key",
        help="PEM-encoded public key",
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
        help="Date when key was activated",
    )
    revoked_date = fields.Datetime(
        readonly=True,
        string="Revoked Date",
        help="Date when key was revoked",
    )
    expires_at = fields.Datetime(
        string="Expiration Date",
        help="Optional expiration date for key rotation",
    )

    @api.constrains("key_id")
    def _check_key_id_unique(self):
        """Ensure key_id is unique across all signing keys."""
        for record in self:
            if record.key_id:
                duplicate = self.search(
                    [("key_id", "=", record.key_id), ("id", "!=", record.id)],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(_("Key ID must be unique. Please choose a different identifier."))

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

    def action_generate_key(self):
        """Generate new cryptographic keypair based on selected algorithm."""
        self.ensure_one()

        if self.state != "draft":
            raise UserError(_("Keys can only be generated in Draft state. Current state: %s") % self.state)

        if self.private_key or self.public_key:
            raise UserError(
                _("Keys already exist for this record. Please create a new key record to generate a new keypair.")
            )

        _logger.info("Generating %s keypair for key_id: %s", self.algorithm, self.key_id)

        try:
            if self.algorithm == "ed25519":
                private_key_pem, public_key_pem = self._generate_ed25519_keypair()
            elif self.algorithm == "rs256":
                private_key_pem, public_key_pem = self._generate_rsa_keypair()
            else:
                raise UserError(_("Unsupported algorithm: %s") % self.algorithm)

            self.write(
                {
                    "private_key": private_key_pem,
                    "public_key": public_key_pem,
                }
            )

            _logger.info(
                "Successfully generated %s keypair for key_id: %s",
                self.algorithm,
                self.key_id,
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("Keypair generated successfully for %s") % self.name,
                    "type": "success",
                    "sticky": False,
                },
            }

        except Exception as e:
            _logger.error("Failed to generate keypair for key_id %s: %s", self.key_id, str(e))
            raise UserError(_("Failed to generate keypair: %s") % str(e)) from e

    def action_activate(self):
        """Activate the signing key for use."""
        self.ensure_one()

        if self.state == "active":
            raise UserError(_("Key is already active."))

        if self.state == "revoked":
            raise UserError(_("Cannot activate a revoked key. Please create a new key."))

        if not self.private_key or not self.public_key:
            raise UserError(_("Cannot activate key without generating keypair. Please generate keys first."))

        _logger.info("Activating signing key: %s (key_id: %s)", self.name, self.key_id)

        self.write(
            {
                "state": "active",
                "activated_date": fields.Datetime.now(),
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Activated"),
                "message": _("Signing key '%s' is now active") % self.name,
                "type": "success",
            },
        }

    def action_revoke(self):
        """Revoke the signing key."""
        self.ensure_one()

        if self.state == "revoked":
            raise UserError(_("Key is already revoked."))

        _logger.warning("Revoking signing key: %s (key_id: %s)", self.name, self.key_id)

        self.write(
            {
                "state": "revoked",
                "revoked_date": fields.Datetime.now(),
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Revoked"),
                "message": _("Signing key '%s' has been revoked") % self.name,
                "type": "warning",
            },
        }

    def get_jwks_entry(self):
        """Return JWKS (JSON Web Key Set) entry for this key.

        Returns:
            dict: JWKS entry for this key suitable for /.well-known/jwks.json endpoint
        """
        self.ensure_one()

        if not self.public_key:
            raise UserError(_("Cannot generate JWKS entry without public key."))

        _logger.debug("Generating JWKS entry for key_id: %s", self.key_id)

        try:
            sender_id = self.env["ir.config_parameter"].sudo().get_param("dci.sender_id", "openspp")

            # Load public key
            public_key_bytes = self.public_key.encode("utf-8")
            public_key_obj = serialization.load_pem_public_key(public_key_bytes)

            # Build kid (Key ID) in DCI format: {sender_id}|{key_id}|{algorithm}
            kid = f"{sender_id}|{self.key_id}|{self.algorithm}"

            if self.algorithm == "ed25519":
                # Ed25519 keys use OKP (Octet Key Pair) format
                # Extract raw public key bytes
                raw_public_key = public_key_obj.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
                # Base64url encode (no padding)
                x = base64.urlsafe_b64encode(raw_public_key).decode("ascii").rstrip("=")

                return {
                    "kty": "OKP",
                    "kid": kid,
                    "use": "sig",
                    "alg": "EdDSA",
                    "crv": "Ed25519",
                    "x": x,
                }

            elif self.algorithm == "rs256":
                # RSA keys use RSA format with modulus (n) and exponent (e)

                public_numbers = public_key_obj.public_numbers()

                # Convert modulus (n) and exponent (e) to base64url
                n_bytes = public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, byteorder="big")
                e_bytes = public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, byteorder="big")

                n = base64.urlsafe_b64encode(n_bytes).decode("ascii").rstrip("=")
                e = base64.urlsafe_b64encode(e_bytes).decode("ascii").rstrip("=")

                return {
                    "kty": "RSA",
                    "kid": kid,
                    "use": "sig",
                    "alg": "RS256",
                    "n": n,
                    "e": e,
                }

        except Exception as e:
            _logger.error("Failed to generate JWKS entry for key_id %s: %s", self.key_id, str(e))
            raise UserError(_("Failed to generate JWKS entry: %s") % str(e)) from e

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

        from ..services.signing import DCISigner

        sender_id = self.env["ir.config_parameter"].sudo().get_param("dci.sender_id", "openspp")

        return DCISigner(
            private_key=self.private_key.encode("utf-8"),
            sender_id=sender_id,
            key_id=self.key_id,
            algorithm=self.algorithm,
        )

    def _generate_ed25519_keypair(self):
        """Generate Ed25519 keypair.

        Returns:
            tuple: (private_key_pem, public_key_pem)
        """
        _logger.debug("Generating Ed25519 keypair")

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

    def _generate_rsa_keypair(self):
        """Generate RSA-256 keypair.

        Returns:
            tuple: (private_key_pem, public_key_pem)
        """
        _logger.debug("Generating RSA-256 keypair (2048 bits)")

        # Generate private key (2048 bits is standard for RS256)
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

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
    def get_active_key(self, algorithm=None):
        """Get the active signing key for the specified algorithm.

        Args:
            algorithm: Algorithm to filter by (ed25519 or rs256), None for any

        Returns:
            spp.dci.signing.key: Active key record or empty recordset
        """
        domain = [("state", "=", "active")]
        if algorithm:
            domain.append(("algorithm", "=", algorithm))

        # Get most recently activated key (id desc as tie-breaker for determinism)
        return self.search(domain, order="activated_date desc, id desc", limit=1)
