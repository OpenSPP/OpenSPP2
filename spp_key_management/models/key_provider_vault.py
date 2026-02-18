"""HashiCorp Vault Key Provider.

This provider integrates with HashiCorp Vault for enterprise-grade key management.
Supports both KV secrets engine and Transit secrets engine.

Configuration (odoo.conf):
    spp_vault_url = https://vault.example.com:8200
    spp_vault_token = s.xxxxx  # Or use AppRole/Kubernetes auth
    spp_vault_namespace = admin  # Enterprise only
    spp_vault_mount_point = transit  # For transit engine
    spp_vault_kv_mount = secret  # For KV engine
    spp_vault_auth_method = token  # token, approle, kubernetes

Environment variables (alternative):
    VAULT_ADDR = https://vault.example.com:8200
    VAULT_TOKEN = s.xxxxx
    VAULT_NAMESPACE = admin
"""

import base64
import logging
import os

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)

try:
    import hvac

    HVAC_AVAILABLE = True
except ImportError:
    HVAC_AVAILABLE = False
    _logger.warning("hvac library not installed. Vault key provider will not work.")


class VaultKeyProvider(models.AbstractModel):
    """Key provider using HashiCorp Vault.

    Supports:
    - Transit secrets engine for encryption/decryption
    - KV secrets engine for key storage
    - Multiple authentication methods
    - Key rotation via Vault
    """

    _name = "spp.key.provider.vault"
    _inherit = "spp.key.provider"
    _description = "HashiCorp Vault Key Provider"

    def _get_vault_client(self):
        """Get an authenticated Vault client.

        Returns:
            hvac.Client: Authenticated Vault client

        Raises:
            UserError: If Vault is not configured or authentication fails
        """
        if not HVAC_AVAILABLE:
            raise UserError(
                "HashiCorp Vault integration requires the 'hvac' library. Install it with: pip install hvac"
            )

        # Get configuration from odoo.conf or environment
        vault_url = config.get("spp_vault_url") or os.environ.get("VAULT_ADDR")
        vault_namespace = config.get("spp_vault_namespace") or os.environ.get("VAULT_NAMESPACE")

        if not vault_url:
            raise UserError(
                "Vault URL not configured. Set spp_vault_url in odoo.conf or VAULT_ADDR environment variable."
            )

        client = hvac.Client(url=vault_url, namespace=vault_namespace)

        # Authenticate based on configured method
        auth_method = config.get("spp_vault_auth_method", "token")

        if (  # nosemgrep: odoo-timing-attack-password
            auth_method == "token"
        ):  # nosemgrep: odoo-timing-attack-password - Comparing auth method selector, not a secret token.
            self._auth_token(client)
        elif auth_method == "approle":
            self._auth_approle(client)
        elif auth_method == "kubernetes":
            self._auth_kubernetes(client)
        else:
            raise UserError(f"Unknown Vault auth method: {auth_method}")

        if not client.is_authenticated():
            raise UserError("Failed to authenticate with Vault")

        return client

    def _auth_token(self, client):
        """Authenticate using a static token."""
        token = config.get("spp_vault_token") or os.environ.get("VAULT_TOKEN")
        if not token:
            raise UserError(
                "Vault token not configured. Set spp_vault_token in odoo.conf or VAULT_TOKEN environment variable."
            )
        client.token = token

    def _auth_approle(self, client):
        """Authenticate using AppRole."""
        role_id = config.get("spp_vault_role_id") or os.environ.get("VAULT_ROLE_ID")
        secret_id = config.get("spp_vault_secret_id") or os.environ.get("VAULT_SECRET_ID")

        if not role_id or not secret_id:
            raise UserError(
                "Vault AppRole credentials not configured. Set spp_vault_role_id and spp_vault_secret_id in odoo.conf."
            )

        response = client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        client.token = response["auth"]["client_token"]

    def _auth_kubernetes(self, client):
        """Authenticate using Kubernetes service account."""
        role = config.get("spp_vault_k8s_role") or os.environ.get("VAULT_K8S_ROLE")

        if not role:
            raise UserError("Vault Kubernetes role not configured. Set spp_vault_k8s_role in odoo.conf.")

        # Read the service account token
        token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        try:
            with open(token_path) as f:
                jwt = f.read()
        except FileNotFoundError as err:
            raise UserError("Kubernetes service account token not found. Ensure running in a Kubernetes pod.") from err

        mount_point = config.get("spp_vault_k8s_mount", "kubernetes")
        response = client.auth.kubernetes.login(role=role, jwt=jwt, mount_point=mount_point)
        client.token = response["auth"]["client_token"]

    def get_data_key(self, key_id, version=None):
        """Get a data encryption key from Vault.

        Uses the Transit engine to generate or retrieve keys.

        Args:
            key_id: The key identifier
            version: Optional key version

        Returns:
            bytes: The encryption key
        """
        client = self._get_vault_client()
        mount_point = config.get("spp_vault_mount_point", "transit")

        try:
            # Use Transit engine to generate a data key
            # This returns a plaintext key and a ciphertext version
            response = client.secrets.transit.generate_data_key(
                name=key_id,
                key_type="plaintext",
                mount_point=mount_point,
            )

            plaintext_key = response["data"]["plaintext"]
            return base64.b64decode(plaintext_key)

        except hvac.exceptions.InvalidPath:
            # Key doesn't exist, create it first
            _logger.info("Creating new transit key: %s", key_id)
            client.secrets.transit.create_key(
                name=key_id,
                key_type="aes256-gcm96",
                mount_point=mount_point,
            )
            # Retry
            return self.get_data_key(key_id, version)

    def get_index_salt(self, purpose):
        """Get a salt for blind index computation from Vault.

        Args:
            purpose: The purpose identifier for the salt

        Returns:
            bytes: The salt value
        """
        client = self._get_vault_client()
        kv_mount = config.get("spp_vault_kv_mount", "secret")
        salt_path = f"spp/index-salts/{purpose}"

        try:
            # Try to read existing salt from KV
            response = client.secrets.kv.v2.read_secret_version(
                path=salt_path,
                mount_point=kv_mount,
            )
            salt_b64 = response["data"]["data"]["salt"]
            return base64.b64decode(salt_b64)

        except hvac.exceptions.InvalidPath:
            # Salt doesn't exist, generate and store it
            import secrets

            new_salt = secrets.token_bytes(32)
            salt_b64 = base64.b64encode(new_salt).decode()

            client.secrets.kv.v2.create_or_update_secret(
                path=salt_path,
                secret={"salt": salt_b64},
                mount_point=kv_mount,
            )

            _logger.info("Created new index salt for purpose: %s", purpose)
            return new_salt

    def rotate_key(self, key_id):
        """Rotate a key in Vault's Transit engine.

        Args:
            key_id: The key to rotate

        Returns:
            int: The new key version
        """
        client = self._get_vault_client()
        mount_point = config.get("spp_vault_mount_point", "transit")

        client.secrets.transit.rotate_key(name=key_id, mount_point=mount_point)

        # Get the new version
        response = client.secrets.transit.read_key(name=key_id, mount_point=mount_point)
        return response["data"]["latest_version"]

    def encrypt_with_transit(self, plaintext, key_id):
        """Encrypt data using Vault's Transit engine.

        This is an alternative to local encryption - Vault does the encryption.

        Args:
            plaintext: The data to encrypt (bytes)
            key_id: The key to use

        Returns:
            str: The ciphertext (Vault's format: vault:v1:...)
        """
        client = self._get_vault_client()
        mount_point = config.get("spp_vault_mount_point", "transit")

        plaintext_b64 = base64.b64encode(plaintext).decode()

        response = client.secrets.transit.encrypt_data(
            name=key_id,
            plaintext=plaintext_b64,
            mount_point=mount_point,
        )

        return response["data"]["ciphertext"]

    def decrypt_with_transit(self, ciphertext, key_id):
        """Decrypt data using Vault's Transit engine.

        Args:
            ciphertext: The ciphertext (Vault's format)
            key_id: The key to use

        Returns:
            bytes: The decrypted data
        """
        client = self._get_vault_client()
        mount_point = config.get("spp_vault_mount_point", "transit")

        response = client.secrets.transit.decrypt_data(
            name=key_id,
            ciphertext=ciphertext,
            mount_point=mount_point,
        )

        plaintext_b64 = response["data"]["plaintext"]
        return base64.b64decode(plaintext_b64)

    def rewrap_ciphertext(self, ciphertext, key_id):
        """Re-encrypt data with the latest key version.

        Useful after key rotation to update ciphertexts without
        exposing plaintext.

        Args:
            ciphertext: The old ciphertext
            key_id: The key used

        Returns:
            str: The new ciphertext encrypted with latest key version
        """
        client = self._get_vault_client()
        mount_point = config.get("spp_vault_mount_point", "transit")

        response = client.secrets.transit.rewrap_data(
            name=key_id,
            ciphertext=ciphertext,
            mount_point=mount_point,
        )

        return response["data"]["ciphertext"]

    # =========================================================================
    # Asymmetric Key Signing Operations (for HSM-backed signing)
    # =========================================================================

    def create_signing_key(self, key_id, key_type="ed25519"):
        """Create an asymmetric signing key in Vault Transit.

        Args:
            key_id: The key identifier
            key_type: Key type - 'ed25519', 'ecdsa-p256', 'rsa-2048', etc.

        Returns:
            dict: Key metadata
        """
        client = self._get_vault_client()
        mount_point = config.get("spp_vault_mount_point", "transit")

        # Map key types to Vault key types
        vault_key_types = {
            "ed25519": "ed25519",
            "ecdsa-p256": "ecdsa-p256",
            "ecdsa-p384": "ecdsa-p384",
            "rsa-2048": "rsa-2048",
            "rsa-3072": "rsa-3072",
            "rsa-4096": "rsa-4096",
        }

        vault_key_type = vault_key_types.get(key_type, "ed25519")

        try:
            client.secrets.transit.create_key(
                name=key_id,
                key_type=vault_key_type,
                exportable=False,  # HSM keys should not be exportable
                mount_point=mount_point,
            )
            _logger.info(
                "Created Vault Transit signing key: %s (type: %s)",
                key_id,
                vault_key_type,
            )
            return {"key_id": key_id, "key_type": vault_key_type}
        except hvac.exceptions.InvalidRequest as e:
            if "already exists" in str(e):
                _logger.debug("Vault Transit key already exists: %s", key_id)
                return {"key_id": key_id, "key_type": vault_key_type}
            raise UserError(f"Failed to create Vault signing key: {e}") from e

    def sign_with_transit(self, key_id, data, algorithm="ed25519"):
        """Sign data using Vault Transit engine.

        The private key never leaves Vault - signing happens inside the HSM.

        Args:
            key_id: The signing key identifier
            data: The data to sign (bytes)
            algorithm: Signing algorithm - 'ed25519', 'ecdsa-p256', etc.

        Returns:
            bytes: The signature
        """
        client = self._get_vault_client()
        mount_point = config.get("spp_vault_mount_point", "transit")

        # Base64 encode the data for Vault
        data_b64 = base64.b64encode(data).decode()

        # Map algorithm to Vault hash algorithm
        # For Ed25519, no hash is needed (it's built-in)
        # For ECDSA, use appropriate hash for the curve
        hash_algorithm = None
        if algorithm in ("ecdsa-p256", "ES256"):
            hash_algorithm = "sha2-256"
        elif algorithm in ("ecdsa-p384", "ES384"):
            hash_algorithm = "sha2-384"

        try:
            kwargs = {
                "name": key_id,
                "input": data_b64,
                "mount_point": mount_point,
                "prehashed": False,
            }
            if hash_algorithm:
                kwargs["hash_algorithm"] = hash_algorithm

            response = client.secrets.transit.sign_data(**kwargs)

            # Vault returns signature in format: vault:v1:base64signature
            signature_str = response["data"]["signature"]
            # Extract just the base64 signature part
            signature_parts = signature_str.split(":")
            signature_b64 = signature_parts[-1]

            return base64.b64decode(signature_b64)

        except hvac.exceptions.InvalidPath as e:
            raise UserError(f"Vault signing key not found: {key_id}") from e
        except hvac.exceptions.InvalidRequest as e:
            raise UserError(f"Vault signing failed: {e}") from e

    def verify_with_transit(self, key_id, data, signature, algorithm="ed25519"):
        """Verify a signature using Vault Transit engine.

        Args:
            key_id: The signing key identifier
            data: The original data (bytes)
            signature: The signature to verify (bytes)
            algorithm: Signing algorithm

        Returns:
            bool: True if signature is valid
        """
        client = self._get_vault_client()
        mount_point = config.get("spp_vault_mount_point", "transit")

        data_b64 = base64.b64encode(data).decode()
        signature_b64 = base64.b64encode(signature).decode()

        # Vault expects signature in format: vault:v1:base64signature
        signature_str = f"vault:v1:{signature_b64}"

        # Use appropriate hash for the curve
        hash_algorithm = None
        if algorithm in ("ecdsa-p256", "ES256"):
            hash_algorithm = "sha2-256"
        elif algorithm in ("ecdsa-p384", "ES384"):
            hash_algorithm = "sha2-384"

        try:
            kwargs = {
                "name": key_id,
                "input": data_b64,
                "signature": signature_str,
                "mount_point": mount_point,
                "prehashed": False,
            }
            if hash_algorithm:
                kwargs["hash_algorithm"] = hash_algorithm

            response = client.secrets.transit.verify_signed_data(**kwargs)

            return response["data"]["valid"]

        except hvac.exceptions.InvalidRequest as e:
            _logger.warning("Vault signature verification failed: %s", e)
            return False

    def get_public_key_from_transit(self, key_id):
        """Get the public key from a Vault Transit signing key.

        Args:
            key_id: The signing key identifier

        Returns:
            bytes: The public key in DER or raw format
        """
        client = self._get_vault_client()
        mount_point = config.get("spp_vault_mount_point", "transit")

        try:
            response = client.secrets.transit.read_key(
                name=key_id,
                mount_point=mount_point,
            )

            # Get the latest version's public key
            keys = response["data"]["keys"]
            latest_version = str(response["data"]["latest_version"])
            public_key_b64 = keys[latest_version].get("public_key")

            if not public_key_b64:
                raise UserError(f"No public key available for key: {key_id}")

            return base64.b64decode(public_key_b64)

        except hvac.exceptions.InvalidPath as e:
            raise UserError(f"Vault key not found: {key_id}") from e
