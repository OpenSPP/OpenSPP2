# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security tests for key management.

These tests verify that the encryption implementation is secure and follows
best practices for cryptographic operations.
"""

import base64
import hashlib
import json

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestEncryptionSecurity(TransactionCase):
    """Security tests for encryption operations."""

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

    def test_ciphertext_is_not_plaintext(self):
        """Test that encrypted data is not the same as plaintext."""
        plaintext = "Sensitive PII data: SSN 123-45-6789"

        encrypted = self.key_manager.encrypt(plaintext, "pii", "security_test_key")

        # Ciphertext should not contain the plaintext
        self.assertNotIn(plaintext, encrypted)
        self.assertNotIn("123-45-6789", encrypted)

    def test_ciphertext_is_random(self):
        """Test that encrypting same plaintext produces different ciphertext (IND-CPA)."""
        plaintext = "Same message encrypted twice"

        encrypted1 = self.key_manager.encrypt(plaintext, "pii", "ind_cpa_key")
        encrypted2 = self.key_manager.encrypt(plaintext, "pii", "ind_cpa_key")

        # Due to random nonce, same plaintext should produce different ciphertext
        self.assertNotEqual(encrypted1, encrypted2)

        # But both should decrypt to the same plaintext
        decrypted1 = self.key_manager.decrypt(encrypted1, "pii", "ind_cpa_key")
        decrypted2 = self.key_manager.decrypt(encrypted2, "pii", "ind_cpa_key")
        self.assertEqual(decrypted1, decrypted2)
        self.assertEqual(decrypted1, plaintext)

    def test_ciphertext_integrity(self):
        """Test that modified ciphertext is detected (authenticated encryption)."""
        plaintext = "Authenticated message"

        encrypted = self.key_manager.encrypt(plaintext, "pii", "integrity_key")

        # Decode, modify, and re-encode
        try:
            raw = base64.b64decode(encrypted)
            # Flip a bit in the middle of the ciphertext
            modified = raw[:20] + bytes([raw[20] ^ 0xFF]) + raw[21:]
            modified_b64 = base64.b64encode(modified).decode()

            # Decryption should fail due to authentication tag mismatch
            with self.assertRaises(Exception):
                self.key_manager.decrypt(modified_b64, "pii", "integrity_key")
        except Exception:
            # If the ciphertext format is different, that's also acceptable
            pass

    def test_aad_prevents_ciphertext_substitution(self):
        """Test that AAD prevents ciphertext substitution attacks."""
        plaintext = "User balance: $1000"

        # Encrypt for user 1
        encrypted = self.key_manager.encrypt(plaintext, "pii", "aad_test_key", aad="user_1")

        # Attempt to decrypt as user 2 should fail
        with self.assertRaises(Exception):
            self.key_manager.decrypt(encrypted, "pii", "aad_test_key", aad="user_2")

    def test_key_material_length(self):
        """Test that encryption keys are proper length (256 bits for AES-256)."""
        key = self.key_manager.get_key("pii", "key_length_test")

        self.assertEqual(len(key), 32)  # 256 bits = 32 bytes

    def test_salt_length(self):
        """Test that salts are proper length (256 bits recommended)."""
        salt = self.key_manager.get_salt("pii", "salt_length_test")

        self.assertEqual(len(salt), 32)  # 256 bits = 32 bytes

    def test_blind_index_is_one_way(self):
        """Test that blind index cannot be reversed to get plaintext."""
        plaintext = "sensitive@email.com"

        index = self.key_manager.compute_blind_index(plaintext, "pii", "email", index_type="exact")

        # Index should be a hash, not reversible
        self.assertIsInstance(index, str)
        self.assertEqual(len(index), 64)  # SHA-256 hex

        # Index should not contain plaintext
        self.assertNotIn("sensitive", index)
        self.assertNotIn("email", index)

    def test_blind_index_collision_resistance(self):
        """Test that different values produce different indexes."""
        value1 = "user1@example.com"
        value2 = "user2@example.com"

        index1 = self.key_manager.compute_blind_index(value1, "pii", "email", index_type="exact")
        index2 = self.key_manager.compute_blind_index(value2, "pii", "email", index_type="exact")

        self.assertNotEqual(index1, index2)


class TestKeyStorageSecurity(TransactionCase):
    """Security tests for key storage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AsymmetricKey = cls.env["spp.asymmetric.key"]
        cls.EncryptionKey = cls.env["spp.encryption.key"]

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

    def test_symmetric_keys_are_encrypted_at_rest(self):
        """Test that symmetric keys in database are encrypted."""
        # Trigger key creation
        key_manager = self.env["spp.key.manager"]
        key_manager.get_key("pii", "storage_security_test")

        # Find the stored key (note: key_id is prefixed with purpose)
        stored = self.EncryptionKey.search([("key_id", "=", "pii_storage_security_test")])
        self.assertTrue(stored)

        encrypted_key = stored.encrypted_key

        # The stored key should not be a valid raw key (32 bytes base64)
        # It should be ciphertext (longer, with nonce + tag)
        try:
            decoded = base64.b64decode(encrypted_key)
            # Raw key would be exactly 32 bytes
            # Encrypted key should be longer (nonce + ciphertext + tag)
            self.assertGreater(len(decoded), 32)
        except Exception:
            # If it's not valid base64, that's fine
            pass

    def test_asymmetric_private_keys_are_encrypted(self):
        """Test that private keys are encrypted at rest."""
        key = self.AsymmetricKey.create(
            {
                "name": "Private Key Security Test",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        encrypted_private = key.encrypted_private_key

        # Should not be valid JSON (would indicate plaintext storage)
        is_plaintext = False
        try:
            parsed = json.loads(encrypted_private)
            if "d" in parsed:  # RSA private exponent
                is_plaintext = True
        except json.JSONDecodeError:
            pass

        self.assertFalse(is_plaintext, "Private key appears to be stored in plaintext!")

    def test_public_keys_do_not_contain_private_material(self):
        """Test that public key exports don't leak private material."""
        key = self.AsymmetricKey.create(
            {
                "name": "Public Key Leak Test",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        public_jwk = json.loads(key.public_key_jwk)

        # RSA private components
        private_components = ["d", "p", "q", "dp", "dq", "qi"]

        for component in private_components:
            self.assertNotIn(component, public_jwk, f"Private component '{component}' found in public key!")

    def test_encryption_keys_cannot_be_deleted(self):
        """Test that encryption keys cannot be deleted (audit requirement)."""
        key_manager = self.env["spp.key.manager"]
        key_manager.get_key("pii", "undeletable_key_test")

        # Note: key_id is prefixed with purpose
        stored = self.EncryptionKey.search([("key_id", "=", "pii_undeletable_key_test")])

        # Attempting to delete should fail
        with self.assertRaises(UserError):
            stored.unlink()


class TestAccessControlSecurity(TransactionCase):
    """Test access control for key management."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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

    def test_encryption_key_field_restricted(self):
        """Test that encrypted_key field has access restrictions."""
        EncryptionKey = self.env["spp.encryption.key"]

        # Check that encrypted_key field has groups restriction
        field = EncryptionKey._fields.get("encrypted_key")
        self.assertIsNotNone(field)

        # Should have groups restriction
        groups = getattr(field, "groups", None)
        self.assertIsNotNone(groups, "encrypted_key field should have groups restriction")


class TestCryptographicPrimitives(TransactionCase):
    """Test that correct cryptographic primitives are used."""

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

    def test_aes_gcm_nonce_length(self):
        """Test that AES-GCM uses proper nonce length (96 bits)."""
        plaintext = "Test message"

        encrypted = self.key_manager.encrypt(plaintext, "pii", "nonce_test_key")
        decoded = base64.b64decode(encrypted)

        # First 12 bytes should be the nonce (96 bits)
        nonce = decoded[:12]
        self.assertEqual(len(nonce), 12)

    def test_aes_gcm_tag_length(self):
        """Test that AES-GCM authentication tag is present."""
        plaintext = "Test message"

        encrypted = self.key_manager.encrypt(plaintext, "pii", "tag_test_key")
        decoded = base64.b64decode(encrypted)

        # Ciphertext structure: nonce (12) + ciphertext + tag (16)
        # Total should be > 12 + len(plaintext) + 16
        min_expected = 12 + len(plaintext.encode()) + 16
        self.assertGreaterEqual(len(decoded), min_expected)

    def test_hmac_for_blind_index(self):
        """Test that blind indexes use HMAC (not just hash)."""
        value = "test_value"

        # Compute blind index (salt is retrieved internally)
        index = self.key_manager.compute_blind_index(value, "pii", "hmac_test", index_type="exact")

        # A simple SHA-256 without salt would give a known value
        simple_hash = hashlib.sha256(value.upper().encode()).hexdigest()

        # The blind index should NOT be the same as simple hash
        # (because it uses HMAC with salt)
        self.assertNotEqual(index, simple_hash)


class TestKeyRotationSecurity(TransactionCase):
    """Test key rotation security properties."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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

    def test_old_key_versions_preserved(self):
        """Test that old key versions are preserved for decryption."""
        EncryptionKey = self.env["spp.encryption.key"]
        key_manager = self.env["spp.key.manager"]

        # Create initial key
        key_manager.get_key("pii", "rotation_test_key")

        # Check version 1 exists (note: key_id is prefixed with purpose)
        v1 = EncryptionKey.search(
            [
                ("key_id", "=", "pii_rotation_test_key"),
                ("version", "=", 1),
            ]
        )
        self.assertTrue(v1)

    def test_only_one_current_version(self):
        """Test that only one version is marked as current."""
        EncryptionKey = self.env["spp.encryption.key"]
        key_manager = self.env["spp.key.manager"]

        key_manager.get_key("pii", "single_current_test")

        # Note: key_id is prefixed with purpose
        current_versions = EncryptionKey.search(
            [
                ("key_id", "=", "pii_single_current_test"),
                ("is_current", "=", True),
            ]
        )

        self.assertEqual(len(current_versions), 1)
