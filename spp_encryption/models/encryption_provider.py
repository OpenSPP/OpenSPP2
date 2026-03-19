import json
import logging

from jwcrypto import jwe, jwt
from jwcrypto.common import json_encode
from jwcrypto.jws import InvalidJWSSignature

from odoo import fields, models
from odoo.tools import misc

_logger = logging.getLogger(__name__)


class SPPEncryptionProvider(models.Model):
    _name = "spp.encryption.provider"
    _description = "SPP Encryption Provider"

    name = fields.Char(required=True)
    type = fields.Selection(selection=[])

    def encrypt_data(self, data: bytes, **kwargs) -> bytes:
        """
        Both input and output are NOT base64 encoded
        """
        try:
            encrypt_func = getattr(self, f"encrypt_data_{self.type}")
        except Exception as e:
            raise NotImplementedError() from e
        return encrypt_func(data, **kwargs)

    def decrypt_data(self, data: bytes, **kwargs) -> bytes:
        """
        Both input and output are NOT base64 encoded
        """
        try:
            decrypt_func = getattr(self, f"decrypt_data_{self.type}")
        except Exception as e:
            raise NotImplementedError() from e
        return decrypt_func(data, **kwargs)

    def jwt_sign(
        self,
        data,
        include_payload=True,
        include_certificate=False,
        include_cert_hash=False,
        **kwargs,
    ) -> str:
        try:
            jwt_func = getattr(self, f"jwt_sign_{self.type}")
        except Exception as e:
            raise NotImplementedError() from e
        return jwt_func(
            data,
            include_payload=include_payload,
            include_certificate=include_certificate,
            include_cert_hash=include_cert_hash,
            **kwargs,
        )

    def jwt_verify(self, data: str, **kwargs):
        try:
            jwt_func = getattr(self, f"jwt_verify_{self.type}")
        except Exception as e:
            raise NotImplementedError() from e
        return jwt_func(data, **kwargs)

    def get_jwks(self, **kwargs):
        try:
            jwk_func = getattr(self, f"get_jwks_{self.type}")
        except Exception as e:
            raise NotImplementedError() from e
        return jwk_func(**kwargs)

    def sign_credential_ld_proof(self, credential: dict) -> dict:
        """
        Sign a credential with Linked Data Proof (JSON-LD signature).

        Args:
            credential: Credential dictionary (JSON-LD format)

        Returns:
            dict: Credential with proof added
        """
        sign_func = getattr(self, f"sign_credential_ld_proof_{self.type}", None)
        if not callable(sign_func):
            # Fallback to default implementation
            return self._sign_credential_ld_proof_default(credential)
        return sign_func(credential)

    def _sign_credential_ld_proof_default(self, credential: dict) -> dict:
        """
        Default implementation using JSON-LD normalization and JWT signing.
        Based on the pattern from spp_openid_vci.
        """
        from datetime import datetime

        try:
            from pyld import jsonld
        except ImportError as err:
            raise NotImplementedError("pyld library required for LD-Proof signing") from err

        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")  # nosemgrep

        # Determine proof type based on key type
        proof_type = self._get_proof_type_from_key()

        # Build proof structure
        curr_datetime = f"{datetime.now().isoformat(timespec='milliseconds')}Z"
        ld_proof = {
            "@context": ["https://w3id.org/security/v2"],
            "type": proof_type,
            "created": curr_datetime,
            "verificationMethod": f"{base_url}/api/v1/security/.well-known/jwks.json",
            "proofPurpose": "assertionMethod",
        }

        # Normalize proof and credential
        # Handle remote context loading failures (e.g., in test environments)
        # Inline local contexts up-front to avoid outbound HTTP during tests
        ld_proof_local = self._inline_local_contexts(ld_proof)
        credential_local = self._inline_local_contexts(credential)

        try:
            normalized_proof_str = jsonld.normalize(
                ld_proof_local, {"algorithm": "URDNA2015", "format": "application/n-quads"}
            )
            normalized_credential_str = jsonld.normalize(
                credential_local, {"algorithm": "URDNA2015", "format": "application/n-quads"}
            )
        except Exception as e:
            allow_fallback = self._allow_jsonld_fallback()
            error_str = str(e).lower()

            # Try again with cached local contexts to keep canonical output
            remote_context_indicators = ("remote context", "w3id.org", "loading remote context")
            if any(indicator in error_str for indicator in remote_context_indicators):
                ld_proof_local = self._inline_local_contexts(ld_proof)
                credential_local = self._inline_local_contexts(credential)
                try:
                    normalized_proof_str = jsonld.normalize(
                        ld_proof_local, {"algorithm": "URDNA2015", "format": "application/n-quads"}
                    )
                    normalized_credential_str = jsonld.normalize(
                        credential_local, {"algorithm": "URDNA2015", "format": "application/n-quads"}
                    )
                except Exception as e2:
                    if not allow_fallback:
                        _logger.error("JSON-LD normalization failed and fallback disabled: %s", e2)
                        raise
                    _logger.warning(
                        "JSON-LD remote context load failed; using deterministic JSON fallback. Error: %s", e2
                    )
                    normalized_proof_str = json.dumps(ld_proof, sort_keys=True)
                    normalized_credential_str = json.dumps(credential, sort_keys=True)
            else:
                if not allow_fallback:
                    _logger.error("JSON-LD normalization failed and fallback disabled: %s", e)
                    raise
                _logger.warning("JSON-LD normalization failed; using deterministic JSON fallback. Error: %s", e)
                normalized_proof_str = json.dumps(ld_proof, sort_keys=True)
                normalized_credential_str = json.dumps(credential, sort_keys=True)

        # Create digest and sign
        # Note: jwt_sign expects a dict (claims) or bytes, depending on implementation
        # For LD-Proof, we sign the digest as bytes (following VCI issuer pattern)
        proof_digest = self._sha256_digest(normalized_proof_str.encode())
        credential_digest = self._sha256_digest(normalized_credential_str.encode())
        combined_digest = proof_digest + credential_digest

        # Sign the combined digest
        # When include_payload=False, jwt_sign should handle bytes directly
        # If the implementation expects dict, we'll need to wrap it
        try:
            signature = self.jwt_sign(
                combined_digest,
                include_payload=False,
                include_certificate=True,
                include_cert_hash=True,
            )
        except (TypeError, ValueError):
            # Fallback: wrap bytes in a dict if implementation expects claims dict
            signature = self.jwt_sign(
                {"digest": combined_digest.hex()},
                include_payload=False,
                include_certificate=True,
                include_cert_hash=True,
            )

        ld_proof["jws"] = signature
        ret = dict(credential)
        ret["proof"] = ld_proof
        return ret

    def _allow_jsonld_fallback(self) -> bool:
        ICP = self.env["ir.config_parameter"].sudo()  # nosemgrep
        param_val = ICP.get_param("spp.vc.allow_jsonld_fallback", "True")
        return str(param_val).lower() in ("1", "true", "yes", "y")

    def _load_local_context(self, url: str):
        if "w3id.org/security/v2" in url or "security-v2.jsonld" in url:
            with misc.file_open("spp_encryption/data/security_v2.jsonld", "r") as f:
                return json.load(f)
        if "www.w3.org/ns/credentials/v2" in url or "credentials/v2" in url:
            with misc.file_open("spp_encryption/data/credentials_v2.jsonld", "r") as f:
                return json.load(f)
        return None

    def _inline_local_contexts(self, obj: dict) -> dict:
        """Replace known remote context URLs with cached local copies."""
        if not isinstance(obj, dict):
            return obj
        ctx = obj.get("@context")
        if isinstance(ctx, list):
            new_ctx = []
            for entry in ctx:
                if isinstance(entry, str):
                    local = self._load_local_context(entry)
                    new_ctx.append(local or entry)
                else:
                    new_ctx.append(entry)
            obj["@context"] = new_ctx
        elif isinstance(ctx, str):
            local = self._load_local_context(ctx)
            if local:
                obj["@context"] = local
        return obj

    def _get_proof_type_from_key(self) -> str:
        """
        Determine the appropriate proof type based on the signing key's algorithm.

        Returns:
            str: Proof type (e.g., "RsaSignature2018", "EcdsaSecp256k1Signature2019", "Ed25519Signature2018")
        """
        try:
            jwks = self.get_jwks()
            if jwks and "keys" in jwks and len(jwks["keys"]) > 0:
                key = jwks["keys"][0]
                kty = key.get("kty", "")

                if kty == "RSA":
                    return "RsaSignature2018"
                elif kty == "EC":
                    # Could also check 'crv' field for specific curve
                    return "EcdsaSecp256k1Signature2019"
                elif kty == "OKP":
                    # Octet key pair (EdDSA)
                    return "Ed25519Signature2018"
        except Exception:
            # Fallback to RSA if unable to determine
            pass

        # Default to RSA signature
        return "RsaSignature2018"

    def _sha256_digest(self, data: bytes) -> bytes:
        """Calculate SHA-256 digest"""
        from cryptography.hazmat.primitives import hashes

        sha = hashes.Hash(hashes.SHA256())
        sha.update(data)
        return sha.finalize()


class JWCryptoEncryptionProvider(models.Model):
    """JWCrypto-based encryption provider.

    Uses spp_key_management for secure key storage. Keys are stored
    encrypted in spp.asymmetric.key records.
    """

    _inherit = "spp.encryption.provider"

    type = fields.Selection(
        selection_add=[("jwcrypto", "JWCrypto")],
        ondelete={"jwcrypto": "cascade"},
    )

    # Link to secure key storage (spp_key_management)
    key_id = fields.Many2one(
        comodel_name="spp.asymmetric.key",
        string="Encryption Key",
        help="Asymmetric key used for encryption, signing, and verification. "
        "Keys are stored encrypted in Key Management.",
        ondelete="restrict",
        required=False,  # Not required at model level, checked in methods
    )

    def _get_jwk_key(self):
        """Get the JWK key for cryptographic operations.

        Returns:
            jwk.JWK: The key object

        Raises:
            ValueError: If no key is configured
        """
        self.ensure_one()

        if not self.key_id:
            raise ValueError(
                f"No encryption key configured for provider '{self.name}'. Please generate or select a key."
            )

        return self.key_id.get_private_key_jwk()

    def _get_public_key(self):
        """Get the public key for verification.

        Returns:
            jwk.JWK: The public key object
        """
        self.ensure_one()

        if not self.key_id:
            raise ValueError(f"No encryption key configured for provider '{self.name}'.")

        return self.key_id.get_public_key_jwk()

    def encrypt_data_jwcrypto(self, data: bytes, **kwargs) -> bytes:
        """Encrypt data using JWE (JSON Web Encryption)."""
        self.ensure_one()
        key = self._get_jwk_key()
        enc = jwe.JWE(data, json_encode({"alg": "RSA-OAEP", "enc": "A256GCM"}))
        enc.add_recipient(key)
        return enc.serialize(compact=True).encode("utf-8")

    def decrypt_data_jwcrypto(self, data: bytes, **kwargs) -> bytes:
        """Decrypt JWE-encrypted data."""
        self.ensure_one()
        key = self._get_jwk_key()
        enc = jwe.JWE()
        enc.deserialize(data.decode("utf-8"), key=key)
        return enc.payload

    def jwt_sign_jwcrypto(self, data, **kwargs) -> str:
        """Sign data and return a JWT."""
        self.ensure_one()
        key = self._get_jwk_key()
        token = jwt.JWT(header={"alg": "RS256"}, claims=data)
        token.make_signed_token(key)
        return token.serialize()

    def jwt_verify_jwcrypto(self, token: str, **kwargs):
        """Verify a JWT signature."""
        self.ensure_one()
        key = self._get_public_key()
        try:
            received_jwt = jwt.JWT(key=key, jwt=token)
            verified = True
        except InvalidJWSSignature:
            received_jwt = None
            verified = False
        return verified, received_jwt

    def get_jwks_jwcrypto(self, **kwargs):
        """Get the public key(s) in JWKS format.

        Returns:
            dict: JWKS structure with public keys
        """
        self.ensure_one()

        if not self.key_id or not self.key_id.public_key_jwk:
            return {"keys": []}

        public_key_data = json.loads(self.key_id.public_key_jwk)
        return {"keys": [public_key_data]}

    def generate_key(self, key_type="rsa", key_size=2048, curve=None):
        """Generate a new encryption key using spp_key_management.

        Creates an spp.asymmetric.key record with secure key storage.

        Args:
            key_type: Key type ('rsa', 'ec', 'ed25519')
            key_size: Key size for RSA (2048, 3072, 4096)
            curve: Curve for EC keys ('P-256', 'P-384', 'P-521', 'secp256k1')

        Returns:
            spp.asymmetric.key: The created key record
        """
        self.ensure_one()

        # Create asymmetric key record
        AsymmetricKey = self.env["spp.asymmetric.key"]

        key_vals = {
            "name": f"{self.name} Key",
            "key_type": key_type,
            "key_size": key_size if key_type == "rsa" else 0,
            "storage_mode": "local",
        }

        if key_type == "ec" and curve:
            key_vals["curve"] = curve

        key_record = AsymmetricKey.create(key_vals)

        # Generate the key pair
        key_record.generate_key_pair()

        # Link to this provider
        self.key_id = key_record

        _logger.info("Generated new %s key for provider '%s' (key ID: %s)", key_type.upper(), self.name, key_record.kid)

        return key_record

    def action_generate_key(self):
        """UI action to generate a new RSA key."""
        self.ensure_one()

        if self.key_id:
            # Confirm before replacing
            return {
                "type": "ir.actions.act_window",
                "name": "Confirm Key Generation",
                "res_model": "spp.encryption.key.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {"default_provider_id": self.id},
            }

        self.generate_key()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Key Generated",
                "message": f"New encryption key created: {self.key_id.kid}",
                "type": "success",
            },
        }
