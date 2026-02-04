"""Azure Key Vault Key Provider.

This provider integrates with Azure Key Vault for enterprise-grade
key management in Azure environments.

Configuration (odoo.conf):
    spp_azure_vault_url = https://my-vault.vault.azure.net/
    spp_azure_tenant_id = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    spp_azure_client_id = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    spp_azure_client_secret = xxxxx
    spp_azure_key_name = spp-encryption-key

Environment variables (alternative):
    AZURE_VAULT_URL = https://my-vault.vault.azure.net/
    AZURE_TENANT_ID = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    AZURE_CLIENT_ID = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    AZURE_CLIENT_SECRET = xxxxx
    # Or use managed identity (no credentials needed in Azure)
"""

import base64
import logging
import os

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)

try:
    from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
    from azure.identity import (
        ClientSecretCredential,
        DefaultAzureCredential,
    )
    from azure.keyvault.keys import KeyClient
    from azure.keyvault.keys.crypto import CryptographyClient, EncryptionAlgorithm
    from azure.keyvault.secrets import SecretClient

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    _logger.warning(
        "Azure SDK not installed. Azure Key Vault provider will not work. "
        "Install with: pip install azure-identity azure-keyvault-keys azure-keyvault-secrets"
    )


class AzureKeyVaultProvider(models.AbstractModel):
    """Key provider using Azure Key Vault.

    Supports:
    - RSA and EC key encryption
    - Secret storage for data keys
    - Managed Identity authentication
    - Key rotation with versioning
    """

    _name = "spp.key.provider.azure.keyvault"
    _inherit = "spp.key.provider"
    _description = "Azure Key Vault Key Provider"

    def _get_credential(self):
        """Get Azure credential for authentication.

        Returns:
            Azure credential object

        Raises:
            UserError: If authentication fails
        """
        if not AZURE_AVAILABLE:
            raise UserError(
                "Azure Key Vault integration requires the Azure SDK. "
                "Install with: pip install azure-identity azure-keyvault-keys azure-keyvault-secrets"
            )

        # Check for explicit service principal credentials
        tenant_id = config.get("spp_azure_tenant_id") or os.environ.get("AZURE_TENANT_ID")
        client_id = config.get("spp_azure_client_id") or os.environ.get("AZURE_CLIENT_ID")
        client_secret = config.get("spp_azure_client_secret") or os.environ.get("AZURE_CLIENT_SECRET")

        if tenant_id and client_id and client_secret:
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )

        # Use default credential chain (managed identity, Azure CLI, etc.)
        return DefaultAzureCredential()

    def _get_vault_url(self):
        """Get the Key Vault URL."""
        vault_url = config.get("spp_azure_vault_url") or os.environ.get("AZURE_VAULT_URL")
        if not vault_url:
            raise UserError(
                "Azure Key Vault URL not configured. "
                "Set spp_azure_vault_url in odoo.conf or AZURE_VAULT_URL environment variable."
            )
        return vault_url

    def _get_key_client(self):
        """Get Azure Key Vault key client."""
        credential = self._get_credential()
        vault_url = self._get_vault_url()
        return KeyClient(vault_url=vault_url, credential=credential)

    def _get_secret_client(self):
        """Get Azure Key Vault secret client."""
        credential = self._get_credential()
        vault_url = self._get_vault_url()
        return SecretClient(vault_url=vault_url, credential=credential)

    def _get_key_name(self, key_id):
        """Get the Azure Key Vault key name.

        Args:
            key_id: The logical key identifier

        Returns:
            str: The Azure key name
        """
        # Check for specific key name override
        key_name = config.get(f"spp_azure_key_{key_id}")
        if key_name:
            return key_name

        # Use default pattern
        prefix = config.get("spp_azure_key_prefix", "spp")
        return f"{prefix}-{key_id}"

    def _ensure_key_exists(self, key_id):
        """Ensure an encryption key exists in Key Vault.

        Args:
            key_id: The logical key identifier

        Returns:
            The key object
        """
        key_client = self._get_key_client()
        key_name = self._get_key_name(key_id)

        try:
            return key_client.get_key(key_name)
        except ResourceNotFoundError:
            # Create the key
            _logger.info("Creating Azure Key Vault key: %s", key_name)
            return key_client.create_rsa_key(
                key_name,
                size=2048,
                key_operations=["encrypt", "decrypt", "wrapKey", "unwrapKey"],
            )

    def get_data_key(self, key_id, version=None):
        """Generate a data encryption key wrapped by Azure Key Vault.

        Uses envelope encryption: generate a random data key locally
        and wrap it with the Key Vault key.

        Args:
            key_id: The key identifier
            version: Ignored (Azure manages versions)

        Returns:
            bytes: The plaintext data key
        """
        import secrets

        # Generate a random data key locally
        data_key = secrets.token_bytes(32)  # 256-bit key

        # Wrap it with Azure Key Vault
        key = self._ensure_key_exists(key_id)
        crypto_client = CryptographyClient(key, self._get_credential())

        try:
            result = crypto_client.wrap_key(
                algorithm=EncryptionAlgorithm.rsa_oaep_256,
                key=data_key,
            )
            wrapped_key = result.encrypted_key
        except HttpResponseError as e:
            raise UserError(f"Azure Key Vault wrap key failed: {e}") from e

        # Cache the wrapped key
        self._cache_wrapped_key(key_id, wrapped_key, key.id)

        return data_key

    def _cache_wrapped_key(self, key_id, wrapped_key, azure_key_id):
        """Cache the wrapped data key for later retrieval.

        Args:
            key_id: The logical key identifier
            wrapped_key: The wrapped data key (bytes)
            azure_key_id: The Azure key ID used
        """
        EncryptionKey = self.env["spp.encryption.key"]

        wrapped_b64 = base64.b64encode(wrapped_key).decode()

        # Check if key already exists
        existing = EncryptionKey.search(
            [
                ("key_id", "=", key_id),
                ("is_current", "=", True),
            ],
            limit=1,
        )

        if existing:
            existing.write({"encrypted_key": wrapped_b64})
        else:
            max_version = EncryptionKey.search(
                [
                    ("key_id", "=", key_id),
                ],
                order="version desc",
                limit=1,
            )

            new_version = (max_version.version if max_version else 0) + 1

            EncryptionKey.search(
                [
                    ("key_id", "=", key_id),
                    ("is_current", "=", True),
                ]
            ).write({"is_current": False})

            EncryptionKey.create(
                {
                    "key_id": key_id,
                    "version": new_version,
                    "is_current": True,
                    "encrypted_key": wrapped_b64,
                }
            )

    def get_index_salt(self, purpose):
        """Get a salt for blind index computation.

        Stores salt as a secret in Key Vault.

        Args:
            purpose: The purpose identifier for the salt

        Returns:
            bytes: The salt value
        """
        secret_client = self._get_secret_client()
        secret_name = f"spp-index-salt-{purpose}"

        try:
            secret = secret_client.get_secret(secret_name)
            return base64.b64decode(secret.value)
        except ResourceNotFoundError:
            # Generate new salt
            import secrets

            new_salt = secrets.token_bytes(32)

            # Store in Key Vault
            secret_client.set_secret(
                secret_name,
                base64.b64encode(new_salt).decode(),
            )
            _logger.info("Created index salt in Azure Key Vault: %s", secret_name)

            return new_salt

    def _unwrap_key(self, wrapped_key, key_id):
        """Unwrap a data key using Azure Key Vault.

        Args:
            wrapped_key: The wrapped key (bytes)
            key_id: The key used for wrapping

        Returns:
            bytes: The unwrapped key
        """
        key = self._ensure_key_exists(key_id)
        crypto_client = CryptographyClient(key, self._get_credential())

        try:
            result = crypto_client.unwrap_key(
                algorithm=EncryptionAlgorithm.rsa_oaep_256,
                encrypted_key=wrapped_key,
            )
            return result.key
        except HttpResponseError as e:
            raise UserError(f"Azure Key Vault unwrap key failed: {e}") from e

    def rotate_key(self, key_id):
        """Rotate the key in Azure Key Vault.

        Creates a new key version.

        Args:
            key_id: The key to rotate

        Returns:
            int: The new key version
        """
        key_client = self._get_key_client()
        key_name = self._get_key_name(key_id)

        try:
            # Rotate creates a new version of the key
            new_key = key_client.rotate_key(key_name)
            _logger.info(
                "Rotated Azure Key Vault key: %s (version: %s)",
                key_name,
                new_key.properties.version,
            )

            # Generate new data key with new version
            self.get_data_key(key_id)

            # Return version from our tracking
            EncryptionKey = self.env["spp.encryption.key"]
            current = EncryptionKey.search(
                [
                    ("key_id", "=", key_id),
                    ("is_current", "=", True),
                ],
                limit=1,
            )

            return current.version if current else 1

        except HttpResponseError as e:
            raise UserError(f"Azure Key Vault key rotation failed: {e}") from e

    def encrypt_with_keyvault(self, plaintext, key_id):
        """Encrypt data directly with Azure Key Vault.

        For small data only. For larger data, use envelope encryption.

        Args:
            plaintext: The data to encrypt (bytes)
            key_id: The key to use

        Returns:
            bytes: The ciphertext
        """
        key = self._ensure_key_exists(key_id)
        crypto_client = CryptographyClient(key, self._get_credential())

        try:
            result = crypto_client.encrypt(
                algorithm=EncryptionAlgorithm.rsa_oaep_256,
                plaintext=plaintext,
            )
            return result.ciphertext
        except HttpResponseError as e:
            raise UserError(f"Azure Key Vault encryption failed: {e}") from e

    def decrypt_with_keyvault(self, ciphertext, key_id):
        """Decrypt data directly with Azure Key Vault.

        Args:
            ciphertext: The ciphertext (bytes)
            key_id: The key used for encryption

        Returns:
            bytes: The decrypted data
        """
        key = self._ensure_key_exists(key_id)
        crypto_client = CryptographyClient(key, self._get_credential())

        try:
            result = crypto_client.decrypt(
                algorithm=EncryptionAlgorithm.rsa_oaep_256,
                ciphertext=ciphertext,
            )
            return result.plaintext
        except HttpResponseError as e:
            raise UserError(f"Azure Key Vault decryption failed: {e}") from e

    # =========================================================================
    # Asymmetric Key Signing Operations (for HSM-backed signing)
    # =========================================================================

    def _get_signing_key_name(self, key_id):
        """Get the Azure Key Vault key name for a signing key.

        Args:
            key_id: The logical key identifier

        Returns:
            str: The Azure key name
        """
        key_name = config.get(f"spp_azure_signing_key_{key_id}")
        if key_name:
            return key_name

        prefix = config.get("spp_azure_key_prefix", "spp")
        return f"{prefix}-signing-{key_id}"

    def _ensure_signing_key_exists(self, key_id, key_type="EC"):
        """Ensure an asymmetric signing key exists in Key Vault.

        Args:
            key_id: The logical key identifier
            key_type: Key type - 'EC' for ECDSA, 'RSA' for RSA

        Returns:
            The key object
        """
        key_client = self._get_key_client()
        key_name = self._get_signing_key_name(key_id)

        try:
            return key_client.get_key(key_name)
        except ResourceNotFoundError:
            _logger.info("Creating Azure Key Vault signing key: %s", key_name)
            if key_type == "EC":
                # Create EC P-256 key for signing
                return key_client.create_ec_key(
                    key_name,
                    curve="P-256",
                    key_operations=["sign", "verify"],
                )
            else:
                # Create RSA key for signing
                return key_client.create_rsa_key(
                    key_name,
                    size=2048,
                    key_operations=["sign", "verify"],
                )

    def create_signing_key(self, key_id, key_type="EC"):
        """Create an asymmetric signing key in Azure Key Vault.

        Args:
            key_id: The key identifier
            key_type: Key type - 'EC', 'RSA'

        Returns:
            str: The key version ID
        """
        # Explicitly reject Ed25519 - Azure Key Vault doesn't support it
        if key_type in ("ed25519", "EdDSA"):
            raise UserError(
                "Azure Key Vault does not support Ed25519 keys. "
                "Please use ECDSA (P-256 or P-384) keys with Azure Key Vault, "
                "or use HashiCorp Vault Transit which supports Ed25519."
            )

        # Map key types
        azure_key_type = "EC"
        if key_type in ("rsa", "RSA", "rsa-2048", "rsa-3072", "rsa-4096"):
            azure_key_type = "RSA"

        key = self._ensure_signing_key_exists(key_id, azure_key_type)
        _logger.info(
            "Azure Key Vault signing key ready: %s (version: %s)",
            key.name,
            key.properties.version,
        )
        return key.properties.version

    def sign_with_keyvault(self, key_id, data, algorithm="ES256"):
        """Sign data using Azure Key Vault.

        The private key never leaves Azure Key Vault - signing happens in the HSM.

        Args:
            key_id: The signing key identifier
            data: The data to sign (bytes)
            algorithm: Signing algorithm - 'ES256', 'ES384', 'RS256', 'PS256', etc.

        Returns:
            bytes: The signature (in raw format for ECDSA: r || s)
        """
        from azure.keyvault.keys.crypto import SignatureAlgorithm

        # Explicitly reject Ed25519 - Azure Key Vault doesn't support it
        if algorithm in ("ed25519", "EdDSA"):
            raise UserError(
                "Azure Key Vault does not support Ed25519 signing. "
                "Please use ECDSA (P-256 or P-384) keys with Azure Key Vault, "
                "or use HashiCorp Vault Transit which supports Ed25519."
            )

        key = self._ensure_signing_key_exists(key_id)
        crypto_client = CryptographyClient(key, self._get_credential())

        # Map algorithm names to Azure SignatureAlgorithm
        algo_map = {
            "ecdsa-p256": SignatureAlgorithm.es256,
            "ecdsa-p384": SignatureAlgorithm.es384,
            "ES256": SignatureAlgorithm.es256,
            "ES384": SignatureAlgorithm.es384,
            "ES512": SignatureAlgorithm.es512,
            "RS256": SignatureAlgorithm.rs256,
            "RS384": SignatureAlgorithm.rs384,
            "RS512": SignatureAlgorithm.rs512,
            "PS256": SignatureAlgorithm.ps256,
            "PS384": SignatureAlgorithm.ps384,
            "PS512": SignatureAlgorithm.ps512,
        }

        azure_algorithm = algo_map.get(algorithm)
        if not azure_algorithm:
            raise UserError(f"Unsupported signing algorithm for Azure Key Vault: {algorithm}")

        try:
            result = crypto_client.sign(azure_algorithm, data)
            signature = result.signature

            # Azure returns raw ECDSA signature (r || s) already
            # No conversion needed

            return signature

        except HttpResponseError as e:
            raise UserError(f"Azure Key Vault signing failed: {e}") from e

    def verify_with_keyvault(self, key_id, data, signature, algorithm="ES256"):
        """Verify a signature using Azure Key Vault.

        Args:
            key_id: The signing key identifier
            data: The original data (bytes)
            signature: The signature to verify (bytes)
            algorithm: Signing algorithm

        Returns:
            bool: True if signature is valid
        """
        from azure.keyvault.keys.crypto import SignatureAlgorithm

        # Explicitly reject Ed25519 - Azure Key Vault doesn't support it
        if algorithm in ("ed25519", "EdDSA"):
            raise UserError(
                "Azure Key Vault does not support Ed25519 verification. "
                "Please use ECDSA keys or HashiCorp Vault Transit."
            )

        try:
            key = self._ensure_signing_key_exists(key_id)
            crypto_client = CryptographyClient(key, self._get_credential())

            algo_map = {
                "ecdsa-p256": SignatureAlgorithm.es256,
                "ecdsa-p384": SignatureAlgorithm.es384,
                "ES256": SignatureAlgorithm.es256,
                "ES384": SignatureAlgorithm.es384,
            }

            azure_algorithm = algo_map.get(algorithm)
            if not azure_algorithm:
                raise UserError(f"Unsupported verification algorithm for Azure Key Vault: {algorithm}")

            result = crypto_client.verify(azure_algorithm, data, signature)
            return result.is_valid

        except HttpResponseError as e:
            _logger.warning("Azure Key Vault signature verification failed: %s", e)
            return False

    def get_public_key_from_keyvault(self, key_id):
        """Get the public key from an Azure Key Vault signing key.

        Args:
            key_id: The signing key identifier

        Returns:
            The Azure KeyVaultKey object containing the public key
        """
        key_client = self._get_key_client()
        key_name = self._get_signing_key_name(key_id)

        try:
            return key_client.get_key(key_name)
        except ResourceNotFoundError as e:
            raise UserError(f"Azure Key Vault signing key not found: {key_name}") from e
