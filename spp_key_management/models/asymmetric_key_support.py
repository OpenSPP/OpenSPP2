"""Asymmetric Key Support for spp_encryption integration.

Extends key management to support asymmetric (RSA/EC) keys used by
spp_encryption for JWT signing and credential issuance.

This allows storing sensitive private keys in enterprise KMS backends
instead of plain database storage.
"""

import base64
import json
import logging

from cryptography.exceptions import InvalidSignature

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AsymmetricKeyStorage(models.Model):
    """Storage for asymmetric key pairs.

    Keys can be stored locally (encrypted) or delegated to KMS backends.
    This provides a more secure alternative to storing JWK JSON in plaintext.
    """

    _name = "spp.asymmetric.key"
    _description = "Asymmetric Key Storage"
    _order = "name"

    name = fields.Char(
        string="Name",
        required=True,
        index=True,
    )

    key_type = fields.Selection(
        selection=[
            ("rsa", "RSA"),
            ("ec", "EC (Elliptic Curve)"),
            ("ed25519", "Ed25519"),
        ],
        string="Key Type",
        required=True,
        default="rsa",
    )

    key_size = fields.Integer(
        string="Key Size (bits)",
        default=2048,
        help="For RSA: 2048, 3072, 4096. For EC: ignored (determined by curve)",
    )

    curve = fields.Selection(
        selection=[
            ("P-256", "P-256 (secp256r1)"),
            ("P-384", "P-384 (secp384r1)"),
            ("P-521", "P-521 (secp521r1)"),
            ("secp256k1", "secp256k1 (Bitcoin)"),
        ],
        string="Curve",
        help="Elliptic curve for EC keys",
    )

    # Key storage
    storage_mode = fields.Selection(
        selection=[
            ("local", "Local (Encrypted)"),
            ("kms", "Key Management System"),
        ],
        string="Storage Mode",
        default="local",
        required=True,
    )

    provider_registry_id = fields.Many2one(
        comodel_name="spp.key.provider.registry",
        string="KMS Provider",
        help="KMS provider to use for key storage (when mode is 'kms')",
    )

    # Local encrypted storage
    encrypted_private_key = fields.Char(
        string="Encrypted Private Key",
        help="Private key encrypted with master key (when mode is 'local')",
    )

    # Public key (always stored locally for easy access)
    public_key_jwk = fields.Text(
        string="Public Key (JWK)",
        readonly=True,
        help="Public key in JWK format",
    )

    kid = fields.Char(
        string="Key ID",
        readonly=True,
        index=True,
    )

    # KMS reference
    kms_key_id = fields.Char(
        string="KMS Key ID",
        help="Key identifier in the KMS backend",
    )

    # Metadata
    purpose_id = fields.Many2one(
        comodel_name="spp.key.purpose",
        string="Purpose",
    )

    active = fields.Boolean(
        default=True,
    )

    create_date = fields.Datetime(
        readonly=True,
    )

    last_used = fields.Datetime(
        string="Last Used",
        readonly=True,
    )

    def generate_key_pair(self):
        """Generate a new key pair."""
        self.ensure_one()

        try:
            from jwcrypto import jwk
        except ImportError as err:
            raise UserError("jwcrypto library required for key generation") from err

        import uuid

        if self.key_type == "rsa":
            key = jwk.JWK.generate(kty="RSA", size=self.key_size or 2048)
        elif self.key_type == "ec":
            curve = self.curve or "P-256"
            key = jwk.JWK.generate(kty="EC", crv=curve)
        elif self.key_type == "ed25519":
            key = jwk.JWK.generate(kty="OKP", crv="Ed25519")
        else:
            raise UserError(f"Unsupported key type: {self.key_type}")

        # Add key ID
        kid = str(uuid.uuid4())
        key_dict = json.loads(key.export())
        key_dict["kid"] = kid

        # Store public key
        public_key_dict = json.loads(key.export_public())
        public_key_dict["kid"] = kid

        self.write(
            {
                "kid": kid,
                "public_key_jwk": json.dumps(public_key_dict),
            }
        )

        # Store private key based on mode
        if self.storage_mode == "local":
            self._store_local_private_key(json.dumps(key_dict))
        elif self.storage_mode == "kms":
            self._store_kms_private_key(json.dumps(key_dict))

        return True

    def _store_local_private_key(self, private_key_json):
        """Store private key encrypted with master key."""
        KeyManager = self.env["spp.key.manager"]
        encrypted = KeyManager.encrypt(
            private_key_json,
            "credentials",
            f"asymmetric_{self.id}",
        )
        self.encrypted_private_key = encrypted

    def _store_kms_private_key(self, private_key_json):
        """Store private key in KMS backend."""
        if not self.provider_registry_id:
            raise UserError("KMS provider must be configured for KMS storage mode")

        provider = self.provider_registry_id.get_provider()

        # Use KMS to encrypt the private key
        if hasattr(provider, "encrypt_with_transit"):
            # Vault Transit
            encrypted = provider.encrypt_with_transit(
                private_key_json.encode(),
                f"asymmetric-{self.kid}",
            )
        elif hasattr(provider, "encrypt_with_kms"):
            # AWS KMS
            encrypted = provider.encrypt_with_kms(
                private_key_json.encode(),
                f"asymmetric-{self.kid}",
            )
        else:
            # Fallback: store encrypted locally but use KMS key
            KeyManager = self.env["spp.key.manager"]
            encrypted = KeyManager.encrypt(
                private_key_json,
                "credentials",
                f"asymmetric_{self.id}",
            )

        self.encrypted_private_key = encrypted
        self.kms_key_id = f"asymmetric-{self.kid}"

    def get_private_key_jwk(self):
        """Get the private key as a JWK object.

        Returns:
            jwk.JWK: The private key
        """
        self.ensure_one()

        try:
            from jwcrypto import jwk
        except ImportError as err:
            raise UserError("jwcrypto library required") from err

        if not self.encrypted_private_key:
            raise UserError("Private key not stored")

        # Decrypt based on storage mode
        if self.storage_mode == "local":
            KeyManager = self.env["spp.key.manager"]
            private_key_json = KeyManager.decrypt(
                self.encrypted_private_key,
                "credentials",
                f"asymmetric_{self.id}",
            )
        elif self.storage_mode == "kms":
            private_key_json = self._get_kms_private_key()
        else:
            raise UserError(f"Unknown storage mode: {self.storage_mode}")

        # Update last used timestamp with sudo() so key usage audit
        # is recorded even if the current user cannot write on the key.
        self.sudo().write(  # nosemgrep: odoo-sudo-without-context - System-level key usage audit update.
            {"last_used": fields.Datetime.now()}
        )

        return jwk.JWK.from_json(private_key_json)

    def _get_kms_private_key(self):
        """Decrypt private key from KMS."""
        if not self.provider_registry_id:
            # Fallback to local decryption
            KeyManager = self.env["spp.key.manager"]
            return KeyManager.decrypt(
                self.encrypted_private_key,
                "credentials",
                f"asymmetric_{self.id}",
            )

        provider = self.provider_registry_id.get_provider()

        if hasattr(provider, "decrypt_with_transit"):
            # Vault Transit
            decrypted = provider.decrypt_with_transit(
                self.encrypted_private_key,
                self.kms_key_id,
            )
            return decrypted.decode()
        elif hasattr(provider, "decrypt_with_kms"):
            # AWS KMS
            decrypted = provider.decrypt_with_kms(base64.b64decode(self.encrypted_private_key))
            return decrypted.decode()
        else:
            # Fallback
            KeyManager = self.env["spp.key.manager"]
            return KeyManager.decrypt(
                self.encrypted_private_key,
                "credentials",
                f"asymmetric_{self.id}",
            )

    def get_public_key_jwk(self):
        """Get the public key as a JWK object.

        Returns:
            jwk.JWK: The public key
        """
        self.ensure_one()

        try:
            from jwcrypto import jwk
        except ImportError as err:
            raise UserError("jwcrypto library required") from err

        if not self.public_key_jwk:
            raise UserError("Public key not available")

        return jwk.JWK.from_json(self.public_key_jwk)

    def export_public_jwks(self):
        """Export public keys as JWKS.

        Returns:
            dict: JWKS structure
        """
        keys = []
        for record in self.filtered(lambda r: r.public_key_jwk):
            keys.append(json.loads(record.public_key_jwk))

        return {"keys": keys}

    def action_generate_key(self):
        """UI action to generate key pair."""
        self.ensure_one()
        self.generate_key_pair()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Key Generated",
                "message": f"Key pair generated with ID: {self.kid}",
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    # =========================================================================
    # Signing Operations (HSM/KMS support)
    # =========================================================================

    def sign(self, data, algorithm=None):
        """Sign data using this key.

        For KMS-backed keys, the signing happens in the HSM and the private
        key never leaves the secure hardware.

        For local keys, the private key is decrypted and signing happens locally.

        Args:
            data: The data to sign (bytes)
            algorithm: Optional algorithm override. If not specified,
                       auto-detected from key type.

        Returns:
            bytes: The signature (raw format for ECDSA: r || s)
        """
        self.ensure_one()

        # Auto-detect algorithm from key type
        if not algorithm:
            algorithm = self._get_default_signing_algorithm()

        # Update last used timestamp
        self.sudo().write({"last_used": fields.Datetime.now()})

        # Route to appropriate signing method based on storage mode
        if self.storage_mode == "kms" and self.provider_registry_id:
            return self._sign_with_kms(data, algorithm)
        else:
            return self._sign_locally(data, algorithm)

    def _get_default_signing_algorithm(self):
        """Get the default signing algorithm based on key type."""
        if self.key_type == "ed25519":
            return "ed25519"
        elif self.key_type == "ec":
            curve = self.curve or "P-256"
            if curve == "P-384":
                return "ecdsa-p384"
            return "ecdsa-p256"
        elif self.key_type == "rsa":
            return "rsa-2048"
        else:
            return "ecdsa-p256"

    def _sign_with_kms(self, data, algorithm):
        """Sign data using KMS provider.

        The private key never leaves the HSM.

        Args:
            data: The data to sign (bytes)
            algorithm: The signing algorithm

        Returns:
            bytes: The signature
        """
        provider = self.provider_registry_id.get_provider()
        kms_key_id = self.kms_key_id or f"asymmetric-{self.kid}"

        # Try provider-specific signing methods
        if hasattr(provider, "sign_with_transit"):
            # HashiCorp Vault Transit
            return provider.sign_with_transit(kms_key_id, data, algorithm)
        elif hasattr(provider, "sign_with_kms"):
            # AWS KMS or GCP KMS
            return provider.sign_with_kms(kms_key_id, data, algorithm)
        elif hasattr(provider, "sign_with_keyvault"):
            # Azure Key Vault
            return provider.sign_with_keyvault(kms_key_id, data, algorithm)
        else:
            # Do NOT fallback to local signing - this would defeat HSM protection
            # The user configured KMS mode expecting HSM-level security
            raise UserError(
                f"KMS provider '{self.provider_registry_id.name}' does not support "
                "HSM signing operations. Please use a provider that supports signing "
                "(Vault Transit, AWS KMS, GCP KMS, Azure Key Vault) or configure "
                "the key with storage_mode='local' if local signing is acceptable."
            )

    def _sign_locally(self, data, algorithm):
        """Sign data locally using the decrypted private key.

        Args:
            data: The data to sign (bytes)
            algorithm: The signing algorithm

        Returns:
            bytes: The signature
        """
        private_key_jwk = self.get_private_key_jwk()
        key_dict = json.loads(private_key_jwk.export())

        if algorithm in ("ed25519", "EdDSA"):
            return self._sign_ed25519(key_dict, data)
        elif algorithm in ("ecdsa-p256", "ES256"):
            return self._sign_ecdsa_p256(key_dict, data)
        elif algorithm in ("ecdsa-p384", "ES384"):
            return self._sign_ecdsa_p384(key_dict, data)
        else:
            raise UserError(f"Unsupported signing algorithm: {algorithm}")

    def _sign_ed25519(self, key_dict, data):
        """Sign with Ed25519."""
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
        except ImportError as err:
            raise UserError("cryptography library required for Ed25519 signing") from err

        # Extract raw private key bytes from JWK
        d_bytes = base64.urlsafe_b64decode(key_dict["d"] + "==")
        private_key = Ed25519PrivateKey.from_private_bytes(d_bytes)
        return private_key.sign(data)

    def _sign_ecdsa_p256(self, key_dict, data):
        """Sign with ECDSA P-256."""
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.asymmetric.utils import (
                decode_dss_signature,
            )
        except ImportError as err:
            raise UserError("cryptography library required for ECDSA signing") from err

        d_bytes = base64.urlsafe_b64decode(key_dict["d"] + "==")
        private_key = ec.derive_private_key(int.from_bytes(d_bytes, "big"), ec.SECP256R1())
        der_signature = private_key.sign(data, ec.ECDSA(hashes.SHA256()))

        # Convert DER to raw format (r || s)
        r, s = decode_dss_signature(der_signature)
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")

    def _sign_ecdsa_p384(self, key_dict, data):
        """Sign with ECDSA P-384."""
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.asymmetric.utils import (
                decode_dss_signature,
            )
        except ImportError as err:
            raise UserError("cryptography library required for ECDSA signing") from err

        d_bytes = base64.urlsafe_b64decode(key_dict["d"] + "==")
        private_key = ec.derive_private_key(int.from_bytes(d_bytes, "big"), ec.SECP384R1())
        der_signature = private_key.sign(data, ec.ECDSA(hashes.SHA384()))

        # Convert DER to raw format (r || s)
        r, s = decode_dss_signature(der_signature)
        return r.to_bytes(48, "big") + s.to_bytes(48, "big")

    def verify(self, data, signature, algorithm=None):
        """Verify a signature.

        For verification, we always use the public key locally since
        public keys don't need HSM protection.

        Args:
            data: The original data (bytes)
            signature: The signature to verify (bytes)
            algorithm: Optional algorithm override

        Returns:
            bool: True if signature is valid
        """
        self.ensure_one()

        if not algorithm:
            algorithm = self._get_default_signing_algorithm()

        public_key_jwk = self.get_public_key_jwk()
        key_dict = json.loads(public_key_jwk.export())

        try:
            if algorithm in ("ed25519", "EdDSA"):
                return self._verify_ed25519(key_dict, data, signature)
            elif algorithm in ("ecdsa-p256", "ES256"):
                return self._verify_ecdsa_p256(key_dict, data, signature)
            elif algorithm in ("ecdsa-p384", "ES384"):
                return self._verify_ecdsa_p384(key_dict, data, signature)
            else:
                raise UserError(f"Unsupported verification algorithm: {algorithm}")
        except (ValueError, InvalidSignature) as e:
            _logger.warning("Signature verification failed: %s", e)
            return False

    def _verify_ed25519(self, key_dict, data, signature):
        """Verify Ed25519 signature."""
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )
        except ImportError as err:
            raise UserError("cryptography library required") from err

        # Validate signature length (Ed25519 signatures are always 64 bytes)
        if len(signature) != 64:
            raise ValueError(f"Invalid Ed25519 signature length: expected 64 bytes, got {len(signature)}")

        x_bytes = base64.urlsafe_b64decode(key_dict["x"] + "==")
        public_key = Ed25519PublicKey.from_public_bytes(x_bytes)
        public_key.verify(signature, data)
        return True

    def _verify_ecdsa_p256(self, key_dict, data, signature):
        """Verify ECDSA P-256 signature."""
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.asymmetric.utils import (
                encode_dss_signature,
            )
        except ImportError as err:
            raise UserError("cryptography library required") from err

        # Validate signature length (P-256: 32 bytes for r + 32 bytes for s)
        if len(signature) != 64:
            raise ValueError(f"Invalid P-256 signature length: expected 64 bytes, got {len(signature)}")

        x_bytes = base64.urlsafe_b64decode(key_dict["x"] + "==")
        y_bytes = base64.urlsafe_b64decode(key_dict["y"] + "==")
        x_int = int.from_bytes(x_bytes, "big")
        y_int = int.from_bytes(y_bytes, "big")
        public_numbers = ec.EllipticCurvePublicNumbers(x_int, y_int, ec.SECP256R1())
        public_key = public_numbers.public_key()

        # Convert raw signature to DER
        r = int.from_bytes(signature[:32], "big")
        s = int.from_bytes(signature[32:], "big")
        der_signature = encode_dss_signature(r, s)

        public_key.verify(der_signature, data, ec.ECDSA(hashes.SHA256()))
        return True

    def _verify_ecdsa_p384(self, key_dict, data, signature):
        """Verify ECDSA P-384 signature."""
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.asymmetric.utils import (
                encode_dss_signature,
            )
        except ImportError as err:
            raise UserError("cryptography library required") from err

        # Validate signature length (P-384: 48 bytes for r + 48 bytes for s)
        if len(signature) != 96:
            raise ValueError(f"Invalid P-384 signature length: expected 96 bytes, got {len(signature)}")

        x_bytes = base64.urlsafe_b64decode(key_dict["x"] + "==")
        y_bytes = base64.urlsafe_b64decode(key_dict["y"] + "==")
        x_int = int.from_bytes(x_bytes, "big")
        y_int = int.from_bytes(y_bytes, "big")
        public_numbers = ec.EllipticCurvePublicNumbers(x_int, y_int, ec.SECP384R1())
        public_key = public_numbers.public_key()

        # Convert raw signature to DER
        r = int.from_bytes(signature[:48], "big")
        s = int.from_bytes(signature[48:], "big")
        der_signature = encode_dss_signature(r, s)

        public_key.verify(der_signature, data, ec.ECDSA(hashes.SHA384()))
        return True
