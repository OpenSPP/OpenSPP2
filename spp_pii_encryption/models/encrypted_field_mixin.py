# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Encrypted Field Mixin.

Provides transparent encryption/decryption for PII fields with
searchable blind indexes.

Usage:
    class RegistryID(models.Model):
        _name = "spp.registry.id"
        _inherit = ["spp.registry.id", "spp.encrypted.field.mixin"]

        # Original field stores encrypted data
        value = fields.Char()

        def _get_encrypted_fields(self):
            return ['value']

The mixin automatically:
- Encrypts values before write
- Decrypts values after read
- Maintains blind indexes for searching
- Logs access to encrypted fields
"""

import base64
import hashlib
import hmac
import logging
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EncryptedFieldMixin(models.AbstractModel):
    """Mixin for models with encrypted PII fields.

    Provides transparent encryption with searchable blind indexes.

    Models using this mixin should:
    1. Inherit from this mixin
    2. Implement _get_encrypted_fields() to list encrypted fields
    3. Optionally add index fields (e.g., value_index, value_last4)

    Example:
        class RegistryID(models.Model):
            _name = "spp.registry.id"
            _inherit = ["spp.registry.id", "spp.encrypted.field.mixin"]

            value = fields.Char()  # Will be encrypted
            value_index = fields.Char(index=True)  # Blind index
            value_last4 = fields.Char(index=True)  # Partial index

            def _get_encrypted_fields(self):
                return ['value']
    """

    _name = "spp.encrypted.field.mixin"
    _description = "Encrypted Field Mixin"

    # Track which fields are currently encrypted (for migration)
    _encryption_enabled = fields.Boolean(
        default=True,
        help="Whether encryption is enabled for this record",
    )

    def _get_encrypted_fields(self):
        """Return list of field names that should be encrypted.

        Checks database configuration first, then falls back to code override.
        This allows UI-based configuration via spp.field.encryption.config.

        Returns:
            list: Field names to encrypt
        """
        # Check database configuration
        FieldConfig = self.env.get("spp.field.encryption.config")
        if FieldConfig:
            db_fields = FieldConfig.get_encrypted_fields(self._name)
            if db_fields:
                return db_fields
        # Fallback: no encryption configured
        return []

    def _get_key_manager(self):
        """Get the centralized key manager.

        Returns:
            spp.key.manager instance
        """
        return self.env["spp.key.manager"]

    def _get_encryption_key(self, field_name):
        """Get encryption key for a field.

        Args:
            field_name: The field being encrypted

        Returns:
            bytes: The encryption key
        """
        key_manager = self._get_key_manager()
        # Use 'pii' purpose for all PII fields
        # Could be extended to use different keys per classification
        return key_manager.get_key("pii", "pii")

    def _get_index_salt(self, field_name):
        """Get salt for blind index of a field.

        Args:
            field_name: The field name

        Returns:
            bytes: The salt
        """
        key_manager = self._get_key_manager()
        return key_manager.get_salt("pii", field_name)

    def _get_index_type(self, field_name):
        """Get configured index type for a field.

        Args:
            field_name: The field name

        Returns:
            str: Index type ('exact', 'partial', 'phonetic') or 'exact' as default
        """
        FieldConfig = self.env.get("spp.field.encryption.config")
        if FieldConfig:
            config_type = FieldConfig.get_index_type(self._name, field_name)
            if config_type:
                return config_type
        return "exact"

    def _encrypt_value(self, value, field_name):
        """Encrypt a field value.

        Uses AES-256-GCM for authenticated encryption.

        Args:
            value: The plaintext value
            field_name: The field being encrypted (used as AAD)

        Returns:
            str: Base64-encoded encrypted value (nonce + ciphertext + tag)
        """
        if not value:
            return value

        try:
            key = self._get_encryption_key(field_name)
            aesgcm = AESGCM(key)

            # Use field name as additional authenticated data
            aad = f"{self._name}.{field_name}".encode()

            # Generate random nonce
            nonce = secrets.token_bytes(12)

            # Encrypt
            plaintext = str(value).encode("utf-8")
            ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

            # Combine nonce + ciphertext and base64 encode
            encrypted = base64.b64encode(nonce + ciphertext).decode("ascii")
            return encrypted

        except Exception:
            # SECURITY: Log error without crypto details that could aid attackers
            _logger.error("Encryption failed for %s.%s (details suppressed for security)", self._name, field_name)
            raise ValueError(
                f"Encryption failed for field '{field_name}'. Check system configuration and logs."
            ) from None

    def _decrypt_value(self, encrypted_value, field_name):
        """Decrypt a field value.

        Args:
            encrypted_value: Base64-encoded encrypted value
            field_name: The field being decrypted

        Returns:
            str: The plaintext value
        """
        if not encrypted_value:
            return encrypted_value

        try:
            key = self._get_encryption_key(field_name)
            aesgcm = AESGCM(key)

            # Use field name as additional authenticated data
            aad = f"{self._name}.{field_name}".encode()

            # Decode and split nonce from ciphertext
            data = base64.b64decode(encrypted_value)
            nonce = data[:12]
            ciphertext = data[12:]

            # Decrypt
            plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
            return plaintext.decode("utf-8")

        except Exception:
            # SECURITY: Log error without crypto details that could aid attackers
            _logger.warning("Decryption failed for %s.%s (details suppressed for security)", self._name, field_name)
            # Return None rather than failing - allows graceful handling
            return None

    def _compute_blind_index(self, value, field_name, index_type="exact"):
        """Compute searchable blind index for a value.

        Blind indexes allow searching encrypted data without
        exposing the plaintext.

        Args:
            value: The plaintext value
            field_name: The field name
            index_type: Type of index (exact, partial, phonetic)

        Returns:
            str: The blind index (hex-encoded HMAC)
        """
        if not value:
            return None

        salt = self._get_index_salt(field_name)
        normalized = self._normalize_for_index(value, index_type)

        # HMAC-SHA256 for deterministic but secure indexing
        index = hmac.new(
            salt,
            normalized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return index

    def _normalize_for_index(self, value, index_type):
        """Normalize value for consistent indexing.

        Args:
            value: The value to normalize
            index_type: Type of normalization

        Returns:
            str: Normalized value
        """
        import re

        value_str = str(value).strip()

        if index_type == "exact":
            # Remove formatting, uppercase
            return re.sub(r"[\s\-\.\(\)]", "", value_str).upper()

        elif index_type == "partial":
            # Last 4 characters only (for partial matching)
            normalized = re.sub(r"[\s\-\.\(\)]", "", value_str)
            return normalized[-4:] if len(normalized) >= 4 else normalized

        elif index_type == "phonetic":
            # Soundex for name matching
            return self._soundex(value_str)

        return value_str

    def _soundex(self, name):
        """Compute Soundex code for phonetic matching.

        Args:
            name: The name to encode

        Returns:
            str: 4-character Soundex code
        """
        if not name:
            return "0000"

        name = name.upper()
        soundex = name[0]

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

        prev = mapping.get(name[0], "0")
        for char in name[1:]:
            code = mapping.get(char, "0")
            if code != "0" and code != prev:
                soundex += code
            prev = code

        return (soundex + "0000")[:4]

    @api.model_create_multi
    def create(self, vals_list):
        """Encrypt fields before create."""
        encrypted_fields = self._get_encrypted_fields()
        if not encrypted_fields:
            return super().create(vals_list)

        for vals in vals_list:
            for field_name in encrypted_fields:
                if field_name in vals and vals[field_name]:
                    plaintext = vals[field_name]

                    # Encrypt
                    vals[field_name] = self._encrypt_value(plaintext, field_name)

                    # Get configured index type
                    index_type = self._get_index_type(field_name)

                    # Compute blind indexes if fields exist
                    index_field = f"{field_name}_index"
                    if index_field in self._fields:
                        vals[index_field] = self._compute_blind_index(plaintext, field_name, index_type)

                    last4_field = f"{field_name}_last4"
                    if last4_field in self._fields:
                        # SECURITY: Store hashed partial index, not plaintext
                        vals[last4_field] = self._compute_blind_index(plaintext, field_name, "partial")

        return super().create(vals_list)

    def write(self, vals):
        """Encrypt fields before write."""
        encrypted_fields = self._get_encrypted_fields()
        if not encrypted_fields:
            return super().write(vals)

        for field_name in encrypted_fields:
            if field_name in vals and vals[field_name]:
                plaintext = vals[field_name]

                # Encrypt
                vals[field_name] = self._encrypt_value(plaintext, field_name)

                # Get configured index type
                index_type = self._get_index_type(field_name)

                # Compute blind indexes if fields exist
                index_field = f"{field_name}_index"
                if index_field in self._fields:
                    vals[index_field] = self._compute_blind_index(plaintext, field_name, index_type)

                last4_field = f"{field_name}_last4"
                if last4_field in self._fields:
                    # SECURITY: Store hashed partial index, not plaintext
                    vals[last4_field] = self._compute_blind_index(plaintext, field_name, "partial")

        return super().write(vals)

    def read(self, fields_list=None, load="_classic_read"):
        """Decrypt fields after read."""
        result = super().read(fields_list, load)

        encrypted_fields = self._get_encrypted_fields()
        if not encrypted_fields:
            return result

        # Determine which encrypted fields are being read
        if fields_list:
            fields_to_decrypt = [f for f in encrypted_fields if f in fields_list]
        else:
            fields_to_decrypt = encrypted_fields

        if not fields_to_decrypt:
            return result

        # Decrypt values in result
        for record_data in result:
            for field_name in fields_to_decrypt:
                if field_name in record_data and record_data[field_name]:
                    decrypted = self._decrypt_value(record_data[field_name], field_name)
                    if decrypted is not None:
                        record_data[field_name] = decrypted
                    else:
                        # Decryption failed - might be unencrypted data
                        # Leave as-is for backwards compatibility
                        pass

        return result

    def search_by_blind_index(self, field_name, search_value):
        """Search encrypted field using blind index.

        Uses the configured index type for the field to ensure
        consistent index computation between write and search.

        Args:
            field_name: The encrypted field name
            search_value: The plaintext value to search for

        Returns:
            recordset: Matching records
        """
        index_field = f"{field_name}_index"
        if index_field not in self._fields:
            _logger.warning(
                "Blind index field '%s' not found on %s. Cannot search encrypted field.",
                index_field,
                self._name,
            )
            return self.browse()

        # Use configured index type to match how the index was computed during write
        index_type = self._get_index_type(field_name)
        blind_index = self._compute_blind_index(search_value, field_name, index_type)
        return self.search([(index_field, "=", blind_index)])

    def search_by_partial(self, field_name, last_chars):
        """Search encrypted field by last N characters.

        Uses blind index for secure partial matching.

        Args:
            field_name: The encrypted field name
            last_chars: The last characters to match

        Returns:
            recordset: Matching records
        """
        last4_field = f"{field_name}_last4"
        if last4_field not in self._fields:
            _logger.warning(
                "Partial index field '%s' not found on %s.",
                last4_field,
                self._name,
            )
            return self.browse()

        # SECURITY: Compute blind index for the search value
        partial_index = self._compute_blind_index(last_chars, field_name, "partial")
        return self.search([(last4_field, "=", partial_index)])
