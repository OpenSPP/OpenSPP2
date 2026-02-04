# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""IBR Sender Registry for signature verification.

This model stores trusted IBR registry public keys for verifying
incoming callback notifications. Similar to spp.dci.crvs.sender
but specifically for Integrated Beneficiary Registry client-side verification.
"""

import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class IBRSenderRegistry(models.Model):
    """IBR Sender Registry.

    Stores public keys of trusted Integrated Beneficiary Registry systems for
    signature verification of incoming callback notifications.
    """

    _name = "spp.dci.ibr.sender"
    _description = "IBR Sender Registry"
    _order = "name"

    name = fields.Char(
        required=True,
        string="Name",
        help="Friendly name for this IBR registry",
    )
    sender_id = fields.Char(
        required=True,
        string="Sender ID",
        help="DCI sender identifier for the IBR registry (e.g., 'ibr.national.gov')",
        index=True,
    )
    public_key = fields.Text(
        string="Public Key",
        help="PEM-encoded public key for signature verification",
    )
    jwks_url = fields.Char(
        string="JWKS URL",
        help="URL to IBR registry's JWKS endpoint (/.well-known/jwks.json)",
    )
    algorithm = fields.Selection(
        [
            ("ed25519", "Ed25519"),
            ("rs256", "RSA-256"),
        ],
        string="Algorithm",
        help="Cryptographic signature algorithm",
    )
    last_key_fetch = fields.Datetime(
        readonly=True,
        string="Last Key Fetch",
        help="When we last fetched their JWKS",
    )
    active = fields.Boolean(
        default=True,
        string="Active",
        help="Inactive senders will not be used for signature verification",
    )
    notes = fields.Text(
        string="Notes",
        help="Additional notes about this IBR registry",
    )

    @api.constrains("sender_id")
    def _check_sender_id_unique(self):
        """Ensure sender_id is unique across all IBR sender entries."""
        for record in self:
            if record.sender_id:
                duplicate = self.search(
                    [("sender_id", "=", record.sender_id), ("id", "!=", record.id)],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(_("Sender ID must be unique. An IBR sender already exists with this ID."))

    @api.constrains("sender_id")
    def _check_sender_id_format(self):
        """Validate sender_id format - alphanumeric, dots, hyphens, and underscores only."""
        for record in self:
            if record.sender_id and not all(c.isalnum() or c in ".-_" for c in record.sender_id):
                raise ValidationError(
                    _("Sender ID must contain only alphanumeric characters, dots, hyphens, and underscores.")
                )

    @api.constrains("jwks_url")
    def _check_jwks_url_format(self):
        """Validate JWKS URL format."""
        for record in self:
            if record.jwks_url:
                if not record.jwks_url.startswith(("http://", "https://")):
                    raise ValidationError(_("JWKS URL must start with http:// or https://"))

    def action_fetch_public_key(self):
        """Fetch public key from IBR registry's JWKS endpoint (button action).

        Returns:
            dict: Notification action
        """
        self.ensure_one()

        try:
            self.fetch_public_key()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("Public key fetched successfully from %s") % self.jwks_url,
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as e:
            _logger.error(
                "Failed to fetch public key for IBR sender %s from %s: %s",
                self.sender_id,
                self.jwks_url,
                str(e),
                exc_info=True,
            )
            raise UserError(_("Failed to fetch public key: %s") % str(e)) from e

    def fetch_public_key(self):
        """Fetch public key from IBR registry's JWKS endpoint.

        Raises:
            UserError: If JWKS URL is not configured or fetch fails
        """
        self.ensure_one()

        if not self.jwks_url:
            raise UserError(_("JWKS URL not configured for IBR sender %s") % self.sender_id)

        _logger.info(
            "Fetching public key for IBR sender %s from %s",
            self.sender_id,
            self.jwks_url,
        )

        try:
            # Fetch JWKS from URL
            response = requests.get(self.jwks_url, timeout=10)
            response.raise_for_status()
            jwks_data = response.json()

            if "keys" not in jwks_data:
                raise UserError(_("Invalid JWKS response: 'keys' field not found"))

            # Find the first key matching our sender_id prefix
            matching_key = None
            for key in jwks_data["keys"]:
                kid = key.get("kid", "")
                # kid format: {sender_id}|{key_id}|{algorithm}
                if kid.startswith(f"{self.sender_id}|"):
                    matching_key = key
                    break

            if not matching_key:
                raise UserError(
                    _("No matching key found in JWKS for IBR sender %s. Expected kid to start with '%s|'")
                    % (self.sender_id, self.sender_id)
                )

            # Convert JWK to PEM format
            public_key_pem = self._jwk_to_pem(matching_key)

            # Extract algorithm from kid
            kid_parts = matching_key.get("kid", "").split("|")
            algorithm = kid_parts[2] if len(kid_parts) >= 3 else None

            # Update record
            self.write(
                {
                    "public_key": public_key_pem,
                    "algorithm": algorithm,
                    "last_key_fetch": fields.Datetime.now(),
                }
            )

            _logger.info(
                "Successfully fetched public key for IBR sender %s (algorithm: %s)",
                self.sender_id,
                algorithm,
            )

        except requests.RequestException as e:
            _logger.error(
                "HTTP error fetching JWKS for IBR sender %s from %s: %s",
                self.sender_id,
                self.jwks_url,
                str(e),
            )
            raise UserError(_("Failed to fetch JWKS from %s: %s") % (self.jwks_url, str(e))) from e

    def _jwk_to_pem(self, jwk):
        """Convert JWK (JSON Web Key) to PEM format.

        Args:
            jwk: JWK dictionary from JWKS endpoint

        Returns:
            str: PEM-encoded public key

        Raises:
            UserError: If JWK format is invalid or unsupported
        """
        import base64

        from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        kty = jwk.get("kty")

        try:
            if kty == "OKP" and jwk.get("crv") == "Ed25519":
                # Ed25519 key
                x = jwk.get("x")
                if not x:
                    raise UserError(_("Missing 'x' parameter in Ed25519 JWK"))

                # Decode base64url (add padding if needed)
                x_bytes = base64.urlsafe_b64decode(x + "=" * (4 - len(x) % 4))

                # Create Ed25519 public key
                public_key = ed25519.Ed25519PublicKey.from_public_bytes(x_bytes)

                # Serialize to PEM
                pem = public_key.public_bytes(
                    encoding=Encoding.PEM,
                    format=PublicFormat.SubjectPublicKeyInfo,
                )
                return pem.decode("utf-8")

            elif kty == "RSA":
                # RSA key
                n = jwk.get("n")
                e = jwk.get("e")
                if not n or not e:
                    raise UserError(_("Missing 'n' or 'e' parameter in RSA JWK"))

                # Decode base64url (add padding if needed)
                n_bytes = base64.urlsafe_b64decode(n + "=" * (4 - len(n) % 4))
                e_bytes = base64.urlsafe_b64decode(e + "=" * (4 - len(e) % 4))

                # Convert to integers
                n_int = int.from_bytes(n_bytes, byteorder="big")
                e_int = int.from_bytes(e_bytes, byteorder="big")

                # Create RSA public key
                public_numbers = rsa.RSAPublicNumbers(e_int, n_int)
                public_key = public_numbers.public_key()

                # Serialize to PEM
                pem = public_key.public_bytes(
                    encoding=Encoding.PEM,
                    format=PublicFormat.SubjectPublicKeyInfo,
                )
                return pem.decode("utf-8")

            else:
                raise UserError(_("Unsupported JWK key type: %s (curve: %s)") % (kty, jwk.get("crv", "N/A")))

        except Exception as e:
            _logger.error("Failed to convert JWK to PEM: %s", str(e), exc_info=True)
            raise UserError(_("Failed to convert JWK to PEM: %s") % str(e)) from e

    def get_verifier(self):
        """Return a DCIVerifier instance for this IBR sender.

        Returns:
            DCIVerifier: Configured verifier instance

        Raises:
            UserError: If public key is not available
        """
        self.ensure_one()

        if not self.public_key:
            raise UserError(
                _("No public key available for IBR sender %s. Please fetch the public key first.") % self.sender_id
            )

        if not self.algorithm:
            raise UserError(_("Algorithm not set for IBR sender %s") % self.sender_id)

        # Import DCIVerifier from spp_dci module
        try:
            from odoo.addons.spp_dci.services.signing import DCIVerifier
        except ImportError as e:
            _logger.error("Failed to import DCIVerifier from spp_dci module")
            raise UserError(
                _("DCI verification service not available. Please ensure spp_dci module is installed.")
            ) from e

        return DCIVerifier(
            public_key=self.public_key.encode("utf-8"),
            algorithm=self.algorithm,
        )

    @api.model
    def get_by_sender_id(self, sender_id):
        """Lookup IBR sender by sender_id.

        Args:
            sender_id: DCI sender identifier

        Returns:
            spp.dci.ibr.sender: Sender record or empty recordset
        """
        return self.search([("sender_id", "=", sender_id), ("active", "=", True)], limit=1)
