# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Key Manager - the unified encryption API."""

import base64

from odoo.tests.common import TransactionCase


class TestKeyManager(TransactionCase):
    """Test the key manager unified API."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.key_manager = cls.env["spp.key.manager"]

        # Configure master key for testing
        test_master_key = base64.b64encode(b"M" * 32).decode()
        cls.env["ir.config_parameter"].sudo().set_param("spp_key_management.master_key", test_master_key)

        # Set up default provider (only if none exists)
        existing_default = cls.env["spp.key.provider.registry"].search([("is_default", "=", True)])
        if not existing_default:
            cls.env["spp.key.provider.registry"].create(
                {
                    "name": "Test Default Provider",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

    def test_get_key(self):
        """Test retrieving an encryption key."""
        key = self.key_manager.get_key("pii", "test_key")

        self.assertIsNotNone(key)
        self.assertEqual(len(key), 32)  # 256 bits
        self.assertIsInstance(key, bytes)

    def test_get_key_consistent(self):
        """Test that same key_id returns same key."""
        key1 = self.key_manager.get_key("pii", "consistent_key")
        key2 = self.key_manager.get_key("pii", "consistent_key")

        self.assertEqual(key1, key2)

    def test_get_salt(self):
        """Test retrieving a salt for blind indexing."""
        salt = self.key_manager.get_salt("pii", "email_field")

        self.assertIsNotNone(salt)
        self.assertEqual(len(salt), 32)
        self.assertIsInstance(salt, bytes)

    def test_get_salt_consistent(self):
        """Test that same salt_id returns same salt."""
        salt1 = self.key_manager.get_salt("pii", "phone_field")
        salt2 = self.key_manager.get_salt("pii", "phone_field")

        self.assertEqual(salt1, salt2)


class TestKeyManagerEncryption(TransactionCase):
    """Test key manager encryption/decryption operations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.key_manager = cls.env["spp.key.manager"]

        # Configure master key for testing
        test_master_key = base64.b64encode(b"M" * 32).decode()
        cls.env["ir.config_parameter"].sudo().set_param("spp_key_management.master_key", test_master_key)

        # Set up default provider
        existing_default = cls.env["spp.key.provider.registry"].search([("is_default", "=", True)])
        if not existing_default:
            cls.env["spp.key.provider.registry"].create(
                {
                    "name": "Test Default Provider",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

    def test_encrypt_decrypt_roundtrip(self):
        """Test basic encryption and decryption."""
        plaintext = "This is sensitive PII data!"

        encrypted = self.key_manager.encrypt(plaintext, "pii", "test_encrypt_key")
        self.assertIsNotNone(encrypted)
        self.assertIsInstance(encrypted, str)  # Base64 encoded
        self.assertNotEqual(encrypted, plaintext)

        decrypted = self.key_manager.decrypt(encrypted, "pii", "test_encrypt_key")
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_with_aad(self):
        """Test encryption with additional authenticated data."""
        plaintext = "Secret message"
        aad = "res.partner.123"

        encrypted = self.key_manager.encrypt(plaintext, "pii", "test_aad_key", aad=aad)

        # Decrypt with correct AAD
        decrypted = self.key_manager.decrypt(encrypted, "pii", "test_aad_key", aad=aad)
        self.assertEqual(decrypted, plaintext)

        # Decrypt with wrong AAD should fail
        with self.assertRaises(Exception):
            self.key_manager.decrypt(encrypted, "pii", "test_aad_key", aad="wrong.aad")

    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        encrypted = self.key_manager.encrypt("", "pii", "empty_test_key")
        decrypted = self.key_manager.decrypt(encrypted, "pii", "empty_test_key")
        self.assertEqual(decrypted, "")

    def test_encrypt_unicode(self):
        """Test encrypting unicode characters."""
        plaintext = "Hello 世界! 🔐 Привет"

        encrypted = self.key_manager.encrypt(plaintext, "pii", "unicode_key")
        decrypted = self.key_manager.decrypt(encrypted, "pii", "unicode_key")

        self.assertEqual(decrypted, plaintext)

    def test_encrypt_large_data(self):
        """Test encrypting larger data."""
        plaintext = "X" * 10000  # 10KB of data

        encrypted = self.key_manager.encrypt(plaintext, "pii", "large_data_key")
        decrypted = self.key_manager.decrypt(encrypted, "pii", "large_data_key")

        self.assertEqual(decrypted, plaintext)

    def test_different_keys_different_ciphertext(self):
        """Test that different keys produce different ciphertext."""
        plaintext = "Same message"

        encrypted1 = self.key_manager.encrypt(plaintext, "pii", "key_alpha")
        encrypted2 = self.key_manager.encrypt(plaintext, "pii", "key_beta")

        # Different keys should produce different ciphertext
        self.assertNotEqual(encrypted1, encrypted2)

    def test_wrong_key_fails_decryption(self):
        """Test that decrypting with wrong key fails."""
        plaintext = "Secret data"

        encrypted = self.key_manager.encrypt(plaintext, "pii", "correct_key")

        # Attempt to decrypt with different key should fail
        with self.assertRaises(Exception):
            self.key_manager.decrypt(encrypted, "pii", "wrong_key")


class TestBlindIndex(TransactionCase):
    """Test blind index computation for searchable encryption."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.key_manager = cls.env["spp.key.manager"]

        # Configure master key for testing
        test_master_key = base64.b64encode(b"M" * 32).decode()
        cls.env["ir.config_parameter"].sudo().set_param("spp_key_management.master_key", test_master_key)

        # Set up default provider
        existing_default = cls.env["spp.key.provider.registry"].search([("is_default", "=", True)])
        if not existing_default:
            cls.env["spp.key.provider.registry"].create(
                {
                    "name": "Test Default Provider",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

    def test_compute_blind_index_exact(self):
        """Test exact match blind index."""
        value = "123-45-6789"

        index = self.key_manager.compute_blind_index(value, "pii", "ssn_field", index_type="exact")

        self.assertIsNotNone(index)
        self.assertIsInstance(index, str)
        self.assertEqual(len(index), 64)  # SHA-256 hex

    def test_blind_index_deterministic(self):
        """Test that same value produces same index."""
        value = "test@example.com"

        index1 = self.key_manager.compute_blind_index(value, "pii", "email_field", index_type="exact")
        index2 = self.key_manager.compute_blind_index(value, "pii", "email_field", index_type="exact")

        self.assertEqual(index1, index2)

    def test_blind_index_case_normalization(self):
        """Test that index normalizes case for exact match."""
        value_lower = "test@example.com"
        value_upper = "TEST@EXAMPLE.COM"

        index_lower = self.key_manager.compute_blind_index(value_lower, "pii", "email_field", index_type="exact")
        index_upper = self.key_manager.compute_blind_index(value_upper, "pii", "email_field", index_type="exact")

        # After normalization, should produce same index
        self.assertEqual(index_lower, index_upper)

    def test_blind_index_different_salts(self):
        """Test that different salt purposes produce different indexes."""
        value = "same_value"

        index1 = self.key_manager.compute_blind_index(value, "pii", "field_a", index_type="exact")
        index2 = self.key_manager.compute_blind_index(value, "pii", "field_b", index_type="exact")

        # Different salts should produce different indexes
        self.assertNotEqual(index1, index2)

    def test_blind_index_partial(self):
        """Test partial match index (last 4 characters)."""
        value = "123-45-6789"

        index = self.key_manager.compute_blind_index(value, "pii", "ssn_field", index_type="partial")

        self.assertIsNotNone(index)

    def test_blind_index_phonetic(self):
        """Test phonetic (soundex) index."""
        value = "Johnson"

        index = self.key_manager.compute_blind_index(value, "pii", "name_field", index_type="phonetic")

        self.assertIsNotNone(index)
        self.assertIsInstance(index, str)

    def test_blind_index_empty_value(self):
        """Test blind index with empty value."""
        index = self.key_manager.compute_blind_index("", "pii", "field", index_type="exact")

        # Empty value should return None or empty string
        self.assertIn(index, [None, ""])

    def test_blind_index_none_value(self):
        """Test blind index with None value."""
        index = self.key_manager.compute_blind_index(None, "pii", "field", index_type="exact")

        self.assertIsNone(index)
