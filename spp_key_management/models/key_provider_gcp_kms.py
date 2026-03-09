"""Google Cloud KMS Key Provider.

This provider integrates with Google Cloud Key Management Service for
enterprise-grade key management in GCP environments.

Configuration (odoo.conf):
    spp_gcp_project = my-project-id
    spp_gcp_location = global
    spp_gcp_keyring = spp-keyring
    spp_gcp_key = spp-encryption-key
    spp_gcp_credentials_file = /path/to/service-account.json

Environment variables (alternative):
    GOOGLE_CLOUD_PROJECT = my-project-id
    GOOGLE_APPLICATION_CREDENTIALS = /path/to/service-account.json
"""

import base64
import logging
import os

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import config

from ..utils.signature import der_to_raw_ecdsa, raw_to_der_ecdsa

_logger = logging.getLogger(__name__)

try:
    from google.api_core import exceptions as gcp_exceptions
    from google.cloud import kms

    GCP_KMS_AVAILABLE = True
except ImportError:
    GCP_KMS_AVAILABLE = False
    _logger.warning("google-cloud-kms library not installed. GCP KMS key provider will not work.")


class GCPKMSKeyProvider(models.AbstractModel):
    """Key provider using Google Cloud Key Management Service.

    Supports:
    - Envelope encryption
    - Symmetric and asymmetric keys
    - Automatic key rotation
    - IAM-based access control
    """

    _name = "spp.key.provider.gcp.kms"
    _inherit = "spp.key.provider"
    _description = "Google Cloud KMS Key Provider"

    def _get_kms_client(self):
        """Get a GCP KMS client.

        Returns:
            google.cloud.kms.KeyManagementServiceClient: KMS client

        Raises:
            UserError: If GCP is not configured
        """
        if not GCP_KMS_AVAILABLE:
            raise UserError(
                "GCP KMS integration requires the 'google-cloud-kms' library. "
                "Install it with: pip install google-cloud-kms"
            )

        # Check for credentials file
        creds_file = config.get("spp_gcp_credentials_file") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

        if creds_file and os.path.exists(creds_file):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file

        return kms.KeyManagementServiceClient()

    def _get_project(self):
        """Get the GCP project ID."""
        project = (
            config.get("spp_gcp_project") or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
        )
        if not project:
            raise UserError(
                "GCP project not configured. Set spp_gcp_project in odoo.conf "
                "or GOOGLE_CLOUD_PROJECT environment variable."
            )
        return project

    def _get_location(self):
        """Get the GCP location for the keyring."""
        return config.get("spp_gcp_location", "global")

    def _get_keyring(self):
        """Get the keyring name."""
        return config.get("spp_gcp_keyring", "spp-keyring")

    def _get_key_path(self, key_id):
        """Get the full resource path for a key.

        Args:
            key_id: The logical key identifier

        Returns:
            str: The full GCP resource path
        """
        client = self._get_kms_client()
        project = self._get_project()
        location = self._get_location()
        keyring = self._get_keyring()

        # Check for specific key name override
        key_name = config.get(f"spp_gcp_key_{key_id}")
        if not key_name:
            key_name = f"spp-{key_id}"

        return client.crypto_key_path(project, location, keyring, key_name)

    def _ensure_keyring_exists(self):
        """Ensure the keyring exists, create if not."""
        client = self._get_kms_client()
        project = self._get_project()
        location = self._get_location()
        keyring = self._get_keyring()

        keyring_path = client.key_ring_path(project, location, keyring)

        try:
            client.get_key_ring(name=keyring_path)
        except gcp_exceptions.NotFound:
            # Create the keyring
            location_path = client.location_path(project, location)
            client.create_key_ring(
                parent=location_path,
                key_ring_id=keyring,
                key_ring={},
            )
            _logger.info("Created GCP keyring: %s", keyring)

    def _ensure_key_exists(self, key_id):
        """Ensure a crypto key exists, create if not."""
        client = self._get_kms_client()
        key_path = self._get_key_path(key_id)

        try:
            client.get_crypto_key(name=key_path)
        except gcp_exceptions.NotFound:
            # Ensure keyring exists first
            self._ensure_keyring_exists()

            # Create the key
            project = self._get_project()
            location = self._get_location()
            keyring = self._get_keyring()
            keyring_path = client.key_ring_path(project, location, keyring)

            key_name = config.get(f"spp_gcp_key_{key_id}") or f"spp-{key_id}"

            client.create_crypto_key(
                parent=keyring_path,
                crypto_key_id=key_name,
                crypto_key={
                    "purpose": kms.CryptoKey.CryptoKeyPurpose.ENCRYPT_DECRYPT,
                    "version_template": {
                        "algorithm": kms.CryptoKeyVersion.CryptoKeyVersionAlgorithm.GOOGLE_SYMMETRIC_ENCRYPTION,
                    },
                    "rotation_period": {"seconds": 7776000},  # 90 days
                    "next_rotation_time": None,  # Start rotation immediately
                },
            )
            _logger.info("Created GCP crypto key: %s", key_name)

    def get_data_key(self, key_id, version=None):
        """Generate a data encryption key using GCP KMS.

        Uses envelope encryption pattern.

        Args:
            key_id: The key identifier
            version: Ignored (GCP manages versions)

        Returns:
            bytes: The plaintext data key
        """
        import secrets

        # Generate a random data key locally
        data_key = secrets.token_bytes(32)  # 256-bit key

        # Encrypt it with GCP KMS
        client = self._get_kms_client()
        self._ensure_key_exists(key_id)
        key_path = self._get_key_path(key_id)

        try:
            response = client.encrypt(
                name=key_path,
                plaintext=data_key,
            )
            encrypted_key = response.ciphertext
        except gcp_exceptions.GoogleAPICallError as e:
            raise UserError(f"GCP KMS encryption failed: {e}") from e

        # Cache the encrypted key
        self._cache_encrypted_key(key_id, encrypted_key)

        return data_key

    def _cache_encrypted_key(self, key_id, encrypted_key):
        """Cache the encrypted data key for later retrieval.

        Args:
            key_id: The logical key identifier
            encrypted_key: The encrypted data key (bytes)
        """
        EncryptionKey = self.env["spp.encryption.key"]

        encrypted_b64 = base64.b64encode(encrypted_key).decode()

        # Check if key already exists
        existing = EncryptionKey.search(
            [
                ("key_id", "=", key_id),
                ("is_current", "=", True),
            ],
            limit=1,
        )

        if existing:
            existing.write({"encrypted_key": encrypted_b64})
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
                    "encrypted_key": encrypted_b64,
                }
            )

    def get_index_salt(self, purpose):
        """Get a salt for blind index computation.

        Args:
            purpose: The purpose identifier for the salt

        Returns:
            bytes: The salt value
        """
        salt_key_id = f"index-salt-{purpose}"

        EncryptionKey = self.env["spp.encryption.key"]
        existing = EncryptionKey.search(
            [
                ("key_id", "=", salt_key_id),
                ("is_current", "=", True),
            ],
            limit=1,
        )

        if existing:
            # Decrypt the stored salt
            return self._decrypt_key(
                base64.b64decode(existing.encrypted_key),
                "index-salt",
            )

        # Generate new salt
        import secrets

        new_salt = secrets.token_bytes(32)

        # Encrypt and store
        client = self._get_kms_client()
        self._ensure_key_exists("index-salt")
        key_path = self._get_key_path("index-salt")

        try:
            response = client.encrypt(name=key_path, plaintext=new_salt)
            encrypted_salt = response.ciphertext
        except gcp_exceptions.GoogleAPICallError as e:
            raise UserError(_("Failed to encrypt salt with GCP KMS: %s") % str(e)) from e

        EncryptionKey.create(
            {
                "key_id": salt_key_id,
                "version": 1,
                "is_current": True,
                "encrypted_key": base64.b64encode(encrypted_salt).decode(),
            }
        )

        return new_salt

    def _decrypt_key(self, encrypted_key, key_id):
        """Decrypt a key using GCP KMS.

        Args:
            encrypted_key: The encrypted key (bytes)
            key_id: The key used for encryption

        Returns:
            bytes: The decrypted key
        """
        client = self._get_kms_client()
        key_path = self._get_key_path(key_id)

        try:
            response = client.decrypt(name=key_path, ciphertext=encrypted_key)
            return response.plaintext
        except gcp_exceptions.GoogleAPICallError as e:
            raise UserError(f"GCP KMS decryption failed: {e}") from e

    def rotate_key(self, key_id):
        """Rotate the crypto key in GCP KMS.

        Creates a new key version and sets it as primary.

        Args:
            key_id: The key to rotate

        Returns:
            int: The new key version
        """
        client = self._get_kms_client()
        key_path = self._get_key_path(key_id)

        try:
            # Create new version
            new_version = client.create_crypto_key_version(parent=key_path)

            # Wait for it to be enabled and set as primary
            version_name = new_version.name

            # Update primary version
            client.update_crypto_key_primary_version(
                name=key_path,
                crypto_key_version_id=version_name.split("/")[-1],
            )

            _logger.info("Rotated GCP KMS key: %s", key_id)

            # Generate new data key
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

        except gcp_exceptions.GoogleAPICallError as e:
            raise UserError(f"GCP KMS key rotation failed: {e}") from e

    # =========================================================================
    # Asymmetric Key Signing Operations (for HSM-backed signing)
    # =========================================================================

    def _get_signing_key_path(self, key_id):
        """Get the full resource path for an asymmetric signing key.

        Args:
            key_id: The logical key identifier

        Returns:
            str: The full GCP resource path for the signing key
        """
        client = self._get_kms_client()
        project = self._get_project()
        location = self._get_location()
        keyring = self._get_keyring()

        # Use a separate key name for signing keys
        key_name = config.get(f"spp_gcp_signing_key_{key_id}")
        if not key_name:
            key_name = f"spp-signing-{key_id}"

        return client.crypto_key_path(project, location, keyring, key_name)

    def create_signing_key(self, key_id, key_type="EC_SIGN_P256_SHA256"):
        """Create an asymmetric signing key in GCP KMS.

        Args:
            key_id: The key identifier
            key_type: GCP KMS algorithm - 'EC_SIGN_P256_SHA256', 'EC_SIGN_P384_SHA384',
                      'RSA_SIGN_PSS_2048_SHA256', etc.

        Returns:
            str: The key version resource name
        """
        # Explicitly reject Ed25519 - GCP KMS doesn't support it
        if key_type in ("ed25519", "EdDSA"):
            raise UserError(
                "GCP KMS does not support Ed25519 keys. "
                "Please use ECDSA (P-256 or P-384) keys with GCP KMS, "
                "or use HashiCorp Vault Transit which supports Ed25519."
            )

        client = self._get_kms_client()

        # Map key types to GCP algorithms
        algo_map = {
            "ecdsa-p256": kms.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_P256_SHA256,
            "ES256": kms.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_P256_SHA256,
            "ecdsa-p384": kms.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_P384_SHA384,
            "ES384": kms.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_P384_SHA384,
            "EC_SIGN_P256_SHA256": kms.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_P256_SHA256,
            "EC_SIGN_P384_SHA384": kms.CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_P384_SHA384,
            "RSA_SIGN_PSS_2048_SHA256": kms.CryptoKeyVersion.CryptoKeyVersionAlgorithm.RSA_SIGN_PSS_2048_SHA256,
            "RSA_SIGN_PKCS1_2048_SHA256": kms.CryptoKeyVersion.CryptoKeyVersionAlgorithm.RSA_SIGN_PKCS1_2048_SHA256,
        }

        gcp_algorithm = algo_map.get(key_type)
        if not gcp_algorithm:
            raise UserError(f"Unsupported key type for GCP KMS: {key_type}")

        # Ensure keyring exists
        self._ensure_keyring_exists()

        project = self._get_project()
        location = self._get_location()
        keyring = self._get_keyring()
        keyring_path = client.key_ring_path(project, location, keyring)

        key_name = config.get(f"spp_gcp_signing_key_{key_id}")
        if not key_name:
            key_name = f"spp-signing-{key_id}"

        key_path = client.crypto_key_path(project, location, keyring, key_name)

        # Check if key already exists
        try:
            existing_key = client.get_crypto_key(name=key_path)
            _logger.debug("GCP KMS signing key already exists: %s", key_name)
            # Return the primary version
            return existing_key.primary.name
        except gcp_exceptions.NotFound:
            pass

        try:
            # Create the asymmetric signing key
            crypto_key = client.create_crypto_key(
                parent=keyring_path,
                crypto_key_id=key_name,
                crypto_key={
                    "purpose": kms.CryptoKey.CryptoKeyPurpose.ASYMMETRIC_SIGN,
                    "version_template": {
                        "algorithm": gcp_algorithm,
                        "protection_level": kms.ProtectionLevel.HSM,  # Use HSM for security
                    },
                },
            )
            _logger.info("Created GCP KMS signing key: %s", key_name)
            return crypto_key.primary.name

        except gcp_exceptions.GoogleAPICallError as e:
            raise UserError(_("Failed to create GCP KMS signing key: %s") % str(e)) from e

    def sign_with_kms(self, key_id, data, algorithm="EC_SIGN_P256_SHA256"):
        """Sign data using GCP KMS.

        The private key never leaves GCP KMS - signing happens in the HSM.

        Args:
            key_id: The signing key identifier
            data: The data to sign (bytes)
            algorithm: Signing algorithm (used to select digest algorithm)

        Returns:
            bytes: The signature (in raw format for ECDSA: r || s)
        """
        import hashlib

        client = self._get_kms_client()
        key_path = self._get_signing_key_path(key_id)

        # Get the primary key version
        try:
            key = client.get_crypto_key(name=key_path)
            key_version_path = key.primary.name
        except gcp_exceptions.NotFound as e:
            raise UserError(f"GCP KMS signing key not found: {key_id}") from e

        # Determine digest algorithm based on key algorithm
        # GCP KMS requires pre-hashed data for asymmetric signing
        if "P384" in algorithm or "384" in str(algorithm):
            digest = hashlib.sha384(data).digest()
            digest_type = "sha384"
        else:
            digest = hashlib.sha256(data).digest()
            digest_type = "sha256"

        try:
            response = client.asymmetric_sign(
                name=key_version_path,
                digest={digest_type: digest},
            )

            signature = response.signature

            # For ECDSA, GCP returns DER-encoded signature
            # Convert to raw format (r || s) for compatibility with claim169
            if "EC_SIGN" in str(key.primary.algorithm):
                signature = der_to_raw_ecdsa(signature, algorithm)

            return signature

        except gcp_exceptions.GoogleAPICallError as e:
            raise UserError(f"GCP KMS signing failed: {e}") from e

    def verify_with_kms(self, key_id, data, signature, algorithm="EC_SIGN_P256_SHA256"):
        """Verify a signature using GCP KMS.

        Args:
            key_id: The signing key identifier
            data: The original data (bytes)
            signature: The signature to verify (bytes)
            algorithm: Signing algorithm

        Returns:
            bool: True if signature is valid
        """
        import hashlib

        client = self._get_kms_client()
        key_path = self._get_signing_key_path(key_id)

        try:
            key = client.get_crypto_key(name=key_path)
            key_version_path = key.primary.name
        except gcp_exceptions.NotFound:
            return False

        # Convert raw signature to DER if needed
        if "EC_SIGN" in str(key.primary.algorithm):
            signature = raw_to_der_ecdsa(signature, algorithm)

        # Pre-hash the data
        if "384" in str(algorithm):
            digest = hashlib.sha384(data).digest()
            digest_type = "sha384"
        else:
            digest = hashlib.sha256(data).digest()
            digest_type = "sha256"

        try:
            response = client.asymmetric_verify(
                name=key_version_path,
                digest={digest_type: digest},
                signature=signature,
            )
            return response.success
        except gcp_exceptions.GoogleAPICallError as e:
            _logger.warning("GCP KMS signature verification failed: %s", e)
            return False

    def get_public_key_from_kms(self, key_id):
        """Get the public key from a GCP KMS signing key.

        Args:
            key_id: The signing key identifier

        Returns:
            bytes: The public key in PEM format
        """
        client = self._get_kms_client()
        key_path = self._get_signing_key_path(key_id)

        try:
            key = client.get_crypto_key(name=key_path)
            key_version_path = key.primary.name

            response = client.get_public_key(name=key_version_path)
            return response.pem.encode()

        except gcp_exceptions.GoogleAPICallError as e:
            raise UserError(_("Failed to get public key from GCP KMS: %s") % str(e)) from e
