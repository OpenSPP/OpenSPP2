# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Database Key Provider with Envelope Encryption.

Stores data encryption keys (DEKs) in the database, encrypted by
a master key (KEK) from configuration. Supports key rotation
and versioning.

Security model:
    - Master key (KEK) stored in config/environment (never in DB)
    - Data keys (DEKs) stored encrypted in database
    - Each key can have multiple versions for rotation
    - Old versions kept for decrypting existing data
"""

import base64
import hashlib
import logging
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import config

from ..exceptions import MasterKeyNotConfiguredError

# Salt for deriving master key from database UUID (constant, not secret)
# This provides domain separation for the derived key
_DERIVED_KEY_SALT = b"openspp-master-key-derivation-v1"

# Track whether we've warned about derived key usage
_derived_key_warning_shown = False

_logger = logging.getLogger(__name__)


class DatabaseKeyProvider(models.AbstractModel):
    """Database-stored key provider with envelope encryption.

    Data encryption keys are stored in the database, encrypted
    by a master key from configuration. This provides:

    - Key rotation support
    - Key versioning
    - Centralized key management
    - Audit trail of key operations
    """

    _name = "spp.key.provider.database"
    _inherit = "spp.key.provider"
    _description = "Database Key Provider"

    @api.model
    def _get_master_key(self):
        """Get master key from configuration or derive from database UUID.

        The master key encrypts all data keys stored in the database.

        Resolution order:
        1. SPP_MASTER_KEY environment variable (recommended for production)
        2. spp_master_key in odoo.conf
        3. Derived from database UUID (for demo/development only)

        Returns:
            bytes: The master key (32 bytes)

        Raises:
            UserError: If master key has invalid format
        """
        # Priority 1: Environment variable (recommended for production)
        master_b64 = os.environ.get("SPP_MASTER_KEY")

        # Priority 2: odoo.conf
        if not master_b64:
            master_b64 = config.get("spp_master_key")

        # If we have an explicit key, decode and validate it
        if master_b64:
            try:
                master = base64.b64decode(master_b64)
                if len(master) != 32:
                    raise UserError(_("Master key has invalid length. Expected 32 bytes."))
                return master
            except Exception as e:
                raise UserError(_("Failed to decode master key: %(error)s") % {"error": str(e)}) from e

        # Priority 3: Derive from database UUID (for demo/development)
        return self._derive_master_key_from_database()

    @api.model
    def _derive_master_key_from_database(self):
        """Derive a master key from the database UUID.

        This provides a zero-config experience for demo/development environments.
        The derived key is deterministic per database, so data can be decrypted
        across restarts.

        SECURITY NOTE: This is less secure than an explicit key because:
        - The key can be derived by anyone with database access
        - The database UUID might be predictable in some setups

        For production, always use SPP_MASTER_KEY environment variable.

        Returns:
            bytes: A 32-byte derived key
        """
        global _derived_key_warning_shown

        # Get database UUID (created on database initialization)
        db_uuid = self.env["ir.config_parameter"].sudo().get_param("database.uuid")
        if not db_uuid:
            raise MasterKeyNotConfiguredError(
                _(
                    "Cannot derive master key: database.uuid not set.\n\n"
                    "Please configure SPP_MASTER_KEY environment variable:\n"
                    'export SPP_MASTER_KEY=$(python -c "import secrets, base64; '
                    'print(base64.b64encode(secrets.token_bytes(32)).decode())")'
                )
            )

        # Derive key using HKDF-like construction (SHA-256 with salt)
        derived = hashlib.sha256(_DERIVED_KEY_SALT + db_uuid.encode()).digest()

        # Log warning (once per process) if not in demo mode
        is_demo = config.get("demo") or os.environ.get("ODOO_DEMO")
        if not _derived_key_warning_shown and not is_demo:
            _logger.warning(
                "Using derived master key from database UUID. "
                "This is acceptable for development but NOT recommended for production. "
                "For production, set SPP_MASTER_KEY environment variable."
            )
            _derived_key_warning_shown = True
        elif not _derived_key_warning_shown and is_demo:
            _logger.info("Demo mode: Using derived master key from database UUID.")
            _derived_key_warning_shown = True

        return derived

    @api.model
    def _encrypt_key(self, plaintext_key, key_id):
        """Encrypt a data key with the master key.

        Uses Additional Authenticated Data (AAD) to bind the encrypted
        key to its identifier, preventing key substitution attacks.

        Args:
            plaintext_key: The key to encrypt (bytes)
            key_id: The key identifier (used as AAD)

        Returns:
            bytes: Encrypted key (nonce + ciphertext)
        """
        master = self._get_master_key()
        aesgcm = AESGCM(master)
        nonce = secrets.token_bytes(12)
        # SECURITY: Use key_id as AAD to bind ciphertext to key identifier
        aad = f"spp.encryption.key:{key_id}".encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext_key, aad)
        return nonce + ciphertext

    @api.model
    def _decrypt_key(self, encrypted_key, key_id):
        """Decrypt a data key with the master key.

        Args:
            encrypted_key: The encrypted key (nonce + ciphertext)
            key_id: The key identifier (used as AAD, must match encryption)

        Returns:
            bytes: The plaintext key
        """
        master = self._get_master_key()
        aesgcm = AESGCM(master)
        nonce = encrypted_key[:12]
        ciphertext = encrypted_key[12:]
        # SECURITY: Verify AAD matches the key identifier
        aad = f"spp.encryption.key:{key_id}".encode()
        return aesgcm.decrypt(nonce, ciphertext, aad)

    @api.model
    def get_data_key(self, key_id, version=None):
        """Retrieve a data encryption key from the database.

        Args:
            key_id: Key identifier
            version: Optional specific version

        Returns:
            bytes: The raw key material
        """
        EncryptionKey = self.env["spp.encryption.key"].sudo()

        domain = [("key_id", "=", key_id)]
        if version:
            domain.append(("version", "=", version))
        else:
            domain.append(("is_current", "=", True))

        key_record = EncryptionKey.search(domain, limit=1)

        if not key_record:
            if version:
                raise UserError(
                    _("Encryption key '%(key_id)s' version %(version)s not found.")
                    % {"key_id": key_id, "version": version}
                )
            # Auto-create key if not exists
            _logger.info("Creating new encryption key: %s", key_id)
            key_record = self._create_key(key_id)

        return self._decrypt_key(base64.b64decode(key_record.encrypted_key), key_id)

    @api.model
    def _create_key(self, key_id, purpose=None):
        """Create a new encryption key.

        Args:
            key_id: Key identifier
            purpose: Optional purpose description

        Returns:
            The created key record
        """
        # Generate new key
        plaintext_key = secrets.token_bytes(32)
        encrypted_key = self._encrypt_key(plaintext_key, key_id)

        return (
            self.env["spp.encryption.key"]
            .sudo()
            .create(
                {
                    "key_id": key_id,
                    "version": 1,
                    "is_current": True,
                    "encrypted_key": base64.b64encode(encrypted_key).decode(),
                    "algorithm": "AES-256-GCM",
                    "purpose": purpose,
                }
            )
        )

    @api.model
    def get_index_salt(self, purpose):
        """Get salt for blind index computation.

        Uses a dedicated salt key or derives from PII key.

        Args:
            purpose: Salt purpose

        Returns:
            bytes: The salt value
        """
        try:
            return self.get_data_key(f"salt_{purpose}")
        except UserError:
            # Derive from PII key
            pii_key = self.get_data_key("pii")
            return hashlib.sha256(purpose.encode() + b":" + pii_key).digest()

    @api.model
    def rotate_key(self, key_id):
        """Create a new version of a key.

        Args:
            key_id: Key identifier

        Returns:
            int: The new version number
        """
        EncryptionKey = self.env["spp.encryption.key"].sudo()

        # Get current version
        current = EncryptionKey.search(
            [
                ("key_id", "=", key_id),
                ("is_current", "=", True),
            ],
            limit=1,
        )

        new_version = (current.version + 1) if current else 1

        # Mark old as not current
        if current:
            current.is_current = False

        # Create new version
        plaintext_key = secrets.token_bytes(32)
        encrypted_key = self._encrypt_key(plaintext_key, key_id)

        EncryptionKey.create(
            {
                "key_id": key_id,
                "version": new_version,
                "is_current": True,
                "encrypted_key": base64.b64encode(encrypted_key).decode(),
                "algorithm": "AES-256-GCM",
            }
        )

        _logger.info("Rotated key '%s' to version %d", key_id, new_version)
        return new_version

    @api.model
    def list_key_versions(self, key_id):
        """List all versions of a key.

        Args:
            key_id: Key identifier

        Returns:
            list: Version numbers, newest first
        """
        versions = (
            self.env["spp.encryption.key"]
            .sudo()
            .search(
                [
                    ("key_id", "=", key_id),
                ],
                order="version desc",
            )
        )
        return [v.version for v in versions]

    @api.model
    def get_provider_info(self):
        """Return provider info with rotation support enabled."""
        return {
            "name": self._description,
            "type": "database",
            "supports_rotation": True,
            "supports_versioning": True,
            "connection_status": "connected",
        }

    @api.model
    def get_key_metadata(self, key_id):
        """Get metadata about a database key."""
        key_record = (
            self.env["spp.encryption.key"]
            .sudo()
            .search(
                [
                    ("key_id", "=", key_id),
                    ("is_current", "=", True),
                ],
                limit=1,
            )
        )

        if not key_record:
            return None

        return {
            "key_id": key_id,
            "algorithm": key_record.algorithm,
            "provider": "database",
            "version": key_record.version,
            "created_date": key_record.create_date,
            "supports_rotation": True,
            "supports_versioning": True,
        }
