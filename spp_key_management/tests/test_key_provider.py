# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Key Provider implementations."""

import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tools import config


class TestConfigKeyProvider(TransactionCase):
    """Test the configuration file key provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["spp.key.provider.config"]

    def test_get_data_key_from_config(self):
        """Test retrieving data key from odoo.conf."""
        # Set a test key in config
        original_value = config.get("spp_encryption_key_pii")
        test_key = base64.b64encode(b"0" * 32).decode()  # 32 bytes for AES-256
        config["spp_encryption_key_pii"] = test_key

        try:
            key = self.provider.get_data_key("pii")
            self.assertEqual(len(key), 32)
            self.assertIsInstance(key, bytes)
        finally:
            # Restore original value
            if original_value:
                config["spp_encryption_key_pii"] = original_value
            else:
                config.options.pop("spp_encryption_key_pii", None)

    def test_get_data_key_missing_raises_error(self):
        """Test that missing key raises UserError."""
        # Ensure no key is configured
        original_value = config.get("spp_encryption_key_nonexistent")
        config.options.pop("spp_encryption_key_nonexistent", None)

        try:
            with self.assertRaises(UserError):
                self.provider.get_data_key("nonexistent")
        finally:
            if original_value:
                config["spp_encryption_key_nonexistent"] = original_value

    def test_get_index_salt_from_config(self):
        """Test retrieving index salt from config."""
        # Use correct config key: spp_index_salt_{purpose}
        original_value = config.get("spp_index_salt_email")
        test_salt = base64.b64encode(b"S" * 32).decode()
        config["spp_index_salt_email"] = test_salt

        try:
            salt = self.provider.get_index_salt("email")
            self.assertEqual(len(salt), 32)
            self.assertIsInstance(salt, bytes)
        finally:
            if original_value:
                config["spp_index_salt_email"] = original_value
            else:
                config.options.pop("spp_index_salt_email", None)

    def test_provider_info(self):
        """Test provider info returns expected structure."""
        info = self.provider.get_provider_info()

        self.assertIn("name", info)
        self.assertIn("type", info)
        self.assertIn("supports_rotation", info)
        self.assertFalse(info["supports_rotation"])  # Config provider doesn't support rotation


class TestDatabaseKeyProvider(TransactionCase):
    """Test the database key provider with envelope encryption."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["spp.key.provider.database"]

        # Configure master key for testing
        test_master_key = base64.b64encode(b"M" * 32).decode()
        cls.env["ir.config_parameter"].sudo().set_param("spp_key_management.master_key", test_master_key)

    def test_get_data_key_creates_if_missing(self):
        """Test that get_data_key creates a new key if none exists."""
        # Use unique key_id to avoid conflicts
        key_id = "test_new_key_" + str(self.env.uid)

        key = self.provider.get_data_key(key_id)

        self.assertIsNotNone(key)
        self.assertEqual(len(key), 32)
        self.assertIsInstance(key, bytes)

        # Verify key was stored
        stored = self.env["spp.encryption.key"].search([("key_id", "=", key_id)])
        self.assertTrue(stored)

    def test_get_data_key_returns_same_key(self):
        """Test that same key_id returns the same key."""
        key_id = "test_consistent_key_" + str(self.env.uid)

        key1 = self.provider.get_data_key(key_id)
        key2 = self.provider.get_data_key(key_id)

        self.assertEqual(key1, key2)

    def test_get_index_salt_deterministic(self):
        """Test that same purpose returns same salt."""
        salt1 = self.provider.get_index_salt("test_purpose")
        salt2 = self.provider.get_index_salt("test_purpose")

        self.assertEqual(salt1, salt2)
        self.assertEqual(len(salt1), 32)

    def test_key_versioning(self):
        """Test that key versions are tracked."""
        key_id = "test_versioned_key_" + str(self.env.uid)

        # Create initial key
        self.provider.get_data_key(key_id)

        stored = self.env["spp.encryption.key"].search(
            [
                ("key_id", "=", key_id),
                ("is_current", "=", True),
            ]
        )
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored.version, 1)

    def test_provider_info(self):
        """Test provider info for database provider."""
        info = self.provider.get_provider_info()

        self.assertIn("name", info)
        self.assertEqual(info["type"], "database")
        self.assertTrue(info.get("supports_rotation", False))


class TestKeyProviderRegistry(TransactionCase):
    """Test the key provider registry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Registry = cls.env["spp.key.provider.registry"]
        cls.Purpose = cls.env["spp.key.purpose"]

    def test_get_provider_for_purpose_default(self):
        """Test getting default provider when no specific one configured."""
        # Ensure a default provider exists
        default = self.Registry.search([("is_default", "=", True)], limit=1)
        if not default:
            default = self.Registry.create(
                {
                    "name": "Test Default Provider",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

        provider = self.Registry.get_provider_for_purpose("pii")
        self.assertIsNotNone(provider)

    def test_get_provider_for_specific_purpose(self):
        """Test getting a provider configured for specific purpose."""
        # Create a purpose
        purpose = self.Purpose.create(
            {
                "name": "Test Purpose",
                "code": "test_specific_" + str(self.env.uid),
            }
        )

        # Create registry entry for this purpose
        self.Registry.create(
            {
                "name": "Test Specific Provider",
                "provider_type": "config",
                "purpose_ids": [(6, 0, [purpose.id])],
            }
        )

        provider = self.Registry.get_provider_for_purpose(purpose.code)
        self.assertIsNotNone(provider)

    def test_only_one_default_provider(self):
        """Test that only one provider can be default."""
        # Check if a default provider already exists
        existing_default = self.Registry.search([("is_default", "=", True)], limit=1)
        if not existing_default:
            # Create a default provider only if none exists
            self.Registry.create(
                {
                    "name": "Default Provider 1",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

        # Verify at most one active default exists
        existing_defaults = self.Registry.search(
            [
                ("is_default", "=", True),
                ("active", "=", True),
            ]
        )

        # Should be exactly one active default
        self.assertEqual(len(existing_defaults), 1)

    def test_connection_test(self):
        """Test the connection test action."""
        registry = self.Registry.create(
            {
                "name": "Test Connection Provider",
                "provider_type": "database",
            }
        )

        # Should not raise
        result = registry.action_test_connection()
        self.assertIsNotNone(result)
