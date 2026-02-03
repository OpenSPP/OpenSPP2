"""Centralized Key Manager.

Provides a unified interface for all cryptographic key operations.
This is the main entry point that other modules should use for key management.

Usage:
    key_manager = self.env["spp.key.manager"]

    # Get a data key
    key = key_manager.get_key("pii", "national_id")

    # Get salt for blind indexes
    salt = key_manager.get_salt("pii", "email")

    # Rotate a key
    new_version = key_manager.rotate_key("pii", "national_id")
"""

import base64
import hashlib
import hmac
import logging
import os

from odoo import api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.cache import ormcache

_logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    _logger.warning("cryptography library not installed")


class KeyManager(models.AbstractModel):
    """Centralized key management service.

    Provides a unified interface for:
    - Retrieving encryption keys
    - Getting salts for blind indexes
    - Key rotation
    - Encryption/decryption operations
    """

    _name = "spp.key.manager"
    _description = "Key Management Service"

    # Security: Keys are cached using @ormcache which is registry-scoped
    # This prevents cache isolation issues in multi-tenant environments

    @api.model
    def _check_key_access(self, operation="read"):
        """Check if current user has access to key operations.

        Args:
            operation: The operation type ('read', 'rotate', 'admin')

        Raises:
            AccessError: If access is denied
        """
        # System operations (no user) are allowed
        if not self.env.user or self.env.su:
            return

        user = self.env.user

        # Admin has full access
        if user.has_group("base.group_system"):
            return

        # Key admin can perform all operations
        if user.has_group("spp_key_management.group_key_admin"):
            return

        # Key operator can read keys
        if operation == "read":
            if user.has_group("spp_key_management.group_key_operator_officer"):
                return

        raise AccessError(
            f"Access denied: User {user.login} lacks permission for "
            f"key operation '{operation}'. Required groups: "
            "Key Operator (read) or Key Admin (all operations)."
        )

    @api.model
    @ormcache("purpose", "key_id", "version")
    def _get_key_cached(self, purpose, key_id, version):
        """Internal cached key retrieval (registry-scoped).

        Using @ormcache ensures proper isolation per database registry.
        Note: version="current" is used as a cache key, converted to None
        for get_data_key which uses is_current=True for current keys.
        """
        provider = self._get_provider(purpose)
        full_key_id = f"{purpose}_{key_id}" if purpose else key_id
        # Convert "current" sentinel back to None for actual key lookup
        actual_version = None if version == "current" else version
        return provider.get_data_key(full_key_id, actual_version)

    @api.model
    def get_key(self, purpose, key_id, version=None):
        """Get an encryption key.

        Args:
            purpose: The key purpose (e.g., 'pii', 'financial', 'api')
            key_id: Unique identifier for the key
            version: Optional specific version

        Returns:
            bytes: The encryption key (256 bits)

        Raises:
            AccessError: If user lacks permission
        """
        self._check_key_access("read")
        self._audit_key_access(purpose, key_id, "get_key")
        return self._get_key_cached(purpose, key_id, version or "current")

    @api.model
    @ormcache("purpose", "salt_id")
    def _get_salt_cached(self, purpose, salt_id):
        """Internal cached salt retrieval (registry-scoped)."""
        provider = self._get_provider(purpose)
        full_salt_id = f"{purpose}_{salt_id}" if purpose else salt_id
        return provider.get_index_salt(full_salt_id)

    @api.model
    def get_salt(self, purpose, salt_id):
        """Get a salt for blind index computation.

        Args:
            purpose: The key purpose
            salt_id: Identifier for the salt (e.g., field name)

        Returns:
            bytes: The salt (256 bits)

        Raises:
            AccessError: If user lacks permission
        """
        self._check_key_access("read")
        return self._get_salt_cached(purpose, salt_id)

    @api.model
    def rotate_key(self, purpose, key_id):
        """Rotate a key to a new version.

        Args:
            purpose: The key purpose
            key_id: The key to rotate

        Returns:
            int: The new key version

        Raises:
            AccessError: If user lacks permission
        """
        self._check_key_access("rotate")
        self._audit_key_access(purpose, key_id, "rotate_key")

        provider = self._get_provider(purpose)
        full_key_id = f"{purpose}_{key_id}" if purpose else key_id
        new_version = provider.rotate_key(full_key_id)

        # Clear cache for this key using ormcache invalidation
        self._clear_key_cache()

        _logger.info(
            "Key rotated: purpose=%s, key_id=%s, new_version=%d, user=%s",
            purpose,
            key_id,
            new_version,
            self.env.user.login,
        )

        return new_version

    @api.model
    def _get_provider(self, purpose):
        """Get the appropriate key provider for a purpose.

        Args:
            purpose: The key purpose code

        Returns:
            KeyProvider: The provider to use
        """
        Registry = self.env["spp.key.provider.registry"]
        return Registry.get_provider_for_purpose(purpose)

    @api.model
    def _clear_key_cache(self):
        """Clear all key caches using ormcache invalidation.

        This properly clears registry-scoped caches without
        affecting other tenants.
        """
        self.clear_caches()

    @api.model
    def _audit_key_access(self, purpose, key_id, operation):
        """Log key access for audit trail.

        Args:
            purpose: Key purpose
            key_id: Key identifier
            operation: Operation performed
        """
        user = self.env.user
        _logger.info(
            "KEY_ACCESS: operation=%s, purpose=%s, key_id=%s, user=%s, uid=%s",
            operation,
            purpose,
            key_id,
            user.login if user else "system",
            user.id if user else 0,
        )

    # Convenience encryption methods

    @api.model
    def encrypt(self, plaintext, purpose, key_id, aad=None):
        """Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt (str or bytes)
            purpose: Key purpose
            key_id: Key identifier
            aad: Optional additional authenticated data

        Returns:
            str: Base64-encoded ciphertext (nonce + ciphertext + tag)
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise UserError("cryptography library required for encryption")

        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        if aad and isinstance(aad, str):
            aad = aad.encode("utf-8")

        key = self.get_key(purpose, key_id)
        aesgcm = AESGCM(key)

        # Generate random nonce (96 bits for GCM)
        nonce = os.urandom(12)

        # Encrypt
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

        # Return nonce + ciphertext (tag is appended by cryptography)
        encrypted = nonce + ciphertext
        return base64.b64encode(encrypted).decode("ascii")

    @api.model
    def decrypt(self, ciphertext_b64, purpose, key_id, aad=None):
        """Decrypt data using AES-256-GCM.

        Args:
            ciphertext_b64: Base64-encoded ciphertext
            purpose: Key purpose
            key_id: Key identifier
            aad: Optional additional authenticated data (must match encryption)

        Returns:
            str: Decrypted plaintext
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise UserError("cryptography library required for decryption")

        if aad and isinstance(aad, str):
            aad = aad.encode("utf-8")

        encrypted = base64.b64decode(ciphertext_b64)

        # Extract nonce (first 12 bytes)
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]

        key = self.get_key(purpose, key_id)
        aesgcm = AESGCM(key)

        # Decrypt
        plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
        return plaintext.decode("utf-8")

    @api.model
    def compute_blind_index(self, value, purpose, salt_id, index_type="exact"):
        """Compute a blind index for searchable encryption.

        Args:
            value: The value to index
            purpose: Key purpose
            salt_id: Salt identifier (usually field name)
            index_type: Type of index:
                - "exact": Full value HMAC
                - "partial": Last N characters
                - "phonetic": Soundex/metaphone

        Returns:
            str: The blind index value (hex string)
        """
        if not value:
            return None

        if isinstance(value, str):
            # Normalize case for case-insensitive matching
            value = value.lower().encode("utf-8")

        salt = self.get_salt(purpose, salt_id)

        if index_type == "exact":
            # Full HMAC-SHA256
            h = hmac.new(salt, value, hashlib.sha256)
            return h.hexdigest()

        elif index_type == "partial":
            # HMAC of last 4 characters
            partial = value[-4:] if len(value) >= 4 else value
            h = hmac.new(salt, partial, hashlib.sha256)
            return h.hexdigest()[:16]  # Truncate for partial

        elif index_type == "phonetic":
            # Soundex-based indexing
            soundex = self._compute_soundex(value.decode("utf-8"))
            h = hmac.new(salt, soundex.encode("utf-8"), hashlib.sha256)
            return h.hexdigest()[:16]

        else:
            raise UserError(f"Unknown index type: {index_type}")

    def _compute_soundex(self, value):
        """Compute Soundex code for phonetic matching.

        Args:
            value: String to compute soundex for

        Returns:
            str: Soundex code (4 characters)
        """
        if not value:
            return ""

        value = value.upper()

        # Keep first letter
        soundex = value[0]

        # Soundex mapping
        mapping = {
            "B": "1",
            "F": "1",
            "P": "1",
            "V": "1",
            "C": "2",
            "G": "2",
            "J": "2",
            "K": "2",
            "Q": "2",
            "S": "2",
            "X": "2",
            "Z": "2",
            "D": "3",
            "T": "3",
            "L": "4",
            "M": "5",
            "N": "5",
            "R": "6",
        }

        prev_code = mapping.get(value[0], "")

        for char in value[1:]:
            code = mapping.get(char, "")
            if code and code != prev_code:
                soundex += code
                if len(soundex) >= 4:
                    break
            prev_code = code

        # Pad with zeros
        return soundex.ljust(4, "0")[:4]

    @api.model
    def get_provider_status(self):
        """Get status of all configured providers.

        Returns:
            list: Status information for each provider
        """
        Registry = self.env["spp.key.provider.registry"]
        providers = Registry.search([("active", "=", True)])

        return [
            {
                "name": p.name,
                "type": p.provider_type,
                "is_default": p.is_default,
                "status": p.connection_status,
                "last_test": p.last_test_date,
                "purposes": p.purpose_ids.mapped("name"),
            }
            for p in providers
        ]
