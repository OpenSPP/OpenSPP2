# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the encrypted field mixin with spp_key_management integration."""

import base64

from odoo.tests.common import TransactionCase
from odoo.tools import config, mute_logger


class TestEncryptedFieldMixin(TransactionCase):
    """Tests for spp.encrypted.field.mixin."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Configure master key for key management
        # Set in odoo config (not ir.config_parameter) as required by key provider
        cls._original_master_key = config.get("spp_master_key")
        test_master_key = base64.b64encode(b"M" * 32).decode()
        config["spp_master_key"] = test_master_key

        # Set up default key provider
        existing_default = cls.env["spp.key.provider.registry"].search([("is_default", "=", True)])
        if not existing_default:
            cls.env["spp.key.provider.registry"].create(
                {
                    "name": "Test Default Provider",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

        cls.Mixin = cls.env["spp.encrypted.field.mixin"]

    @classmethod
    def tearDownClass(cls):
        # Restore original master key configuration
        if cls._original_master_key:
            config["spp_master_key"] = cls._original_master_key
        elif "spp_master_key" in config.options:
            del config.options["spp_master_key"]
        super().tearDownClass()

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption are reversible."""
        mixin = self.Mixin

        plaintext = "123-456-789"
        field_name = "test_field"

        # Encrypt
        encrypted = mixin._encrypt_value(plaintext, field_name)
        self.assertIsNotNone(encrypted)
        self.assertNotEqual(encrypted, plaintext)

        # Decrypt
        decrypted = mixin._decrypt_value(encrypted, field_name)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_empty_value(self):
        """Test that empty values are handled correctly."""
        mixin = self.Mixin

        result = mixin._encrypt_value(None, "test_field")
        self.assertIsNone(result)

        result = mixin._encrypt_value("", "test_field")
        self.assertEqual(result, "")

    def test_blind_index_consistency(self):
        """Test that blind indexes are deterministic."""
        mixin = self.Mixin

        value = "123-456-789"
        field_name = "national_id"

        index1 = mixin._compute_blind_index(value, field_name)
        index2 = mixin._compute_blind_index(value, field_name)

        self.assertEqual(index1, index2)

    def test_blind_index_normalization(self):
        """Test that normalized values produce same index."""
        mixin = self.Mixin

        # These should produce the same index (exact matching)
        index1 = mixin._compute_blind_index("123-456-789", "test", "exact")
        index2 = mixin._compute_blind_index("123 456 789", "test", "exact")
        index3 = mixin._compute_blind_index("123.456.789", "test", "exact")

        self.assertEqual(index1, index2)
        self.assertEqual(index2, index3)

    def test_partial_index(self):
        """Test partial index (last N chars)."""
        mixin = self.Mixin

        normalized = mixin._normalize_for_index("123-456-7890", "partial")
        self.assertEqual(normalized, "7890")

    def test_soundex(self):
        """Test Soundex phonetic encoding."""
        mixin = self.Mixin

        # Same pronunciation should have same Soundex
        self.assertEqual(mixin._soundex("Robert"), mixin._soundex("Rupert"))
        self.assertEqual(mixin._soundex("Smith"), mixin._soundex("Smythe"))

        # Different names should have different Soundex (usually)
        self.assertNotEqual(mixin._soundex("Robert"), mixin._soundex("Michael"))

    def test_different_fields_different_encryption(self):
        """Test that same value encrypted for different fields is different."""
        mixin = self.Mixin

        plaintext = "same-value"

        encrypted1 = mixin._encrypt_value(plaintext, "field_a")
        encrypted2 = mixin._encrypt_value(plaintext, "field_b")

        # Different AAD means different ciphertext
        # (Actually the nonce makes them different anyway)
        self.assertNotEqual(encrypted1, encrypted2)

        # But both should decrypt to same value
        self.assertEqual(mixin._decrypt_value(encrypted1, "field_a"), plaintext)
        self.assertEqual(mixin._decrypt_value(encrypted2, "field_b"), plaintext)

    def test_get_encrypted_fields_default_empty(self):
        """With no configuration, the mixin reports no encrypted fields."""
        self.assertEqual(self.Mixin._get_encrypted_fields(), [])

    def test_get_index_type_defaults_to_exact(self):
        """An unconfigured field defaults to the 'exact' index type."""
        self.assertEqual(self.Mixin._get_index_type("national_id"), "exact")

    def test_normalize_phonetic_and_passthrough(self):
        """Phonetic normalization uses Soundex; unknown index types pass through."""
        mixin = self.Mixin
        self.assertEqual(
            mixin._normalize_for_index("Smith", "phonetic"),
            mixin._soundex("Smith"),
        )
        # An unrecognized index type returns the stripped value unchanged.
        self.assertEqual(mixin._normalize_for_index("  abc  ", "unknown"), "abc")

    def test_decrypt_invalid_returns_none(self):
        """Decrypting non-decryptable data fails gracefully and returns None."""
        with mute_logger("odoo.addons.spp_pii_encryption.models.encrypted_field_mixin"):
            self.assertIsNone(self.Mixin._decrypt_value("not-valid-ciphertext", "national_id"))

    def test_search_helpers_without_index_field(self):
        """Search helpers return an empty recordset when the index column is absent."""
        with mute_logger("odoo.addons.spp_pii_encryption.models.encrypted_field_mixin"):
            self.assertFalse(self.Mixin.search_by_blind_index("national_id", "123"))
            self.assertFalse(self.Mixin.search_by_partial("national_id", "0123"))
