# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Asymmetric Key Storage."""

import base64
import json

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestAsymmetricKeyStorage(TransactionCase):
    """Test asymmetric key storage for RSA/EC keys."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AsymmetricKey = cls.env["spp.asymmetric.key"]

        # Configure master key for testing
        test_master_key = base64.b64encode(b"M" * 32).decode()
        cls.env["ir.config_parameter"].sudo().set_param("spp_key_management.master_key", test_master_key)

        # Set up default provider for key manager
        existing_default = cls.env["spp.key.provider.registry"].search([("is_default", "=", True)])
        if not existing_default:
            cls.env["spp.key.provider.registry"].create(
                {
                    "name": "Test Default Provider",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

    def test_create_rsa_key(self):
        """Test creating an RSA key pair."""
        key = self.AsymmetricKey.create(
            {
                "name": "Test RSA Key",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )

        key.generate_key_pair()

        self.assertIsNotNone(key.kid)
        self.assertIsNotNone(key.public_key_jwk)
        self.assertIsNotNone(key.encrypted_private_key)

    def test_create_ec_key(self):
        """Test creating an EC key pair."""
        key = self.AsymmetricKey.create(
            {
                "name": "Test EC Key",
                "key_type": "ec",
                "curve": "P-256",
                "storage_mode": "local",
            }
        )

        key.generate_key_pair()

        self.assertIsNotNone(key.kid)
        self.assertIsNotNone(key.public_key_jwk)

        # Verify curve in public key
        public_key = json.loads(key.public_key_jwk)
        self.assertEqual(public_key.get("kty"), "EC")
        self.assertEqual(public_key.get("crv"), "P-256")

    def test_create_ed25519_key(self):
        """Test creating an Ed25519 key pair."""
        key = self.AsymmetricKey.create(
            {
                "name": "Test Ed25519 Key",
                "key_type": "ed25519",
                "storage_mode": "local",
            }
        )

        key.generate_key_pair()

        self.assertIsNotNone(key.kid)
        self.assertIsNotNone(key.public_key_jwk)

        # Verify key type
        public_key = json.loads(key.public_key_jwk)
        self.assertEqual(public_key.get("kty"), "OKP")
        self.assertEqual(public_key.get("crv"), "Ed25519")

    def test_get_private_key_jwk(self):
        """Test retrieving the private key as JWK."""
        key = self.AsymmetricKey.create(
            {
                "name": "Test Key for Retrieval",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        private_key = key.get_private_key_jwk()

        self.assertIsNotNone(private_key)
        # Verify it has private key components
        self.assertTrue(hasattr(private_key, "has_private"))

    def test_get_public_key_jwk(self):
        """Test retrieving the public key as JWK."""
        key = self.AsymmetricKey.create(
            {
                "name": "Test Key Public",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        public_key = key.get_public_key_jwk()

        self.assertIsNotNone(public_key)

    def test_export_public_jwks(self):
        """Test exporting multiple keys as JWKS."""
        key1 = self.AsymmetricKey.create(
            {
                "name": "JWKS Key 1",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key1.generate_key_pair()

        key2 = self.AsymmetricKey.create(
            {
                "name": "JWKS Key 2",
                "key_type": "ec",
                "curve": "P-256",
                "storage_mode": "local",
            }
        )
        key2.generate_key_pair()

        keys = key1 | key2
        jwks = keys.export_public_jwks()

        self.assertIn("keys", jwks)
        self.assertEqual(len(jwks["keys"]), 2)

    def test_private_key_not_in_public_export(self):
        """Test that private key material is not in public export."""
        key = self.AsymmetricKey.create(
            {
                "name": "Private Key Security Test",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        public_key = json.loads(key.public_key_jwk)

        # RSA private key components should not be present
        private_components = ["d", "p", "q", "dp", "dq", "qi"]
        for component in private_components:
            self.assertNotIn(component, public_key)

    def test_private_key_is_encrypted(self):
        """Test that stored private key is encrypted."""
        key = self.AsymmetricKey.create(
            {
                "name": "Encrypted Private Key Test",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        # The encrypted_private_key should not be valid JSON (it's encrypted)
        encrypted = key.encrypted_private_key
        self.assertIsNotNone(encrypted)

        # It should be base64 encoded ciphertext, not raw JSON
        try:
            parsed = json.loads(encrypted)
            # If it parses as JSON and has "d" (private exponent), it's not encrypted!
            if "d" in parsed:
                self.fail("Private key appears to be stored in plaintext!")
        except json.JSONDecodeError:
            # Expected - encrypted data is not valid JSON
            pass

    def test_key_without_generation_raises_error(self):
        """Test that accessing key before generation raises error."""
        key = self.AsymmetricKey.create(
            {
                "name": "Ungenerated Key",
                "key_type": "rsa",
                "storage_mode": "local",
            }
        )

        with self.assertRaises(UserError):
            key.get_private_key_jwk()

    def test_kid_is_unique(self):
        """Test that key IDs are unique."""
        key1 = self.AsymmetricKey.create(
            {
                "name": "Unique Key 1",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key1.generate_key_pair()

        key2 = self.AsymmetricKey.create(
            {
                "name": "Unique Key 2",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key2.generate_key_pair()

        self.assertNotEqual(key1.kid, key2.kid)

    def test_action_generate_key(self):
        """Test the UI action for generating keys."""
        key = self.AsymmetricKey.create(
            {
                "name": "Action Test Key",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )

        result = key.action_generate_key()

        self.assertIsNotNone(result)
        self.assertIsNotNone(key.kid)

    def test_last_used_tracking(self):
        """Test that last_used timestamp is updated."""
        key = self.AsymmetricKey.create(
            {
                "name": "Last Used Test Key",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        # Initially no last_used
        self.assertFalse(key.last_used)

        # Access private key
        key.get_private_key_jwk()

        # Refresh and check last_used
        key.invalidate_recordset()
        self.assertTrue(key.last_used)


class TestAsymmetricKeyRSASizes(TransactionCase):
    """Test different RSA key sizes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AsymmetricKey = cls.env["spp.asymmetric.key"]

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

    def test_rsa_2048(self):
        """Test 2048-bit RSA key generation."""
        key = self.AsymmetricKey.create(
            {
                "name": "RSA 2048 Key",
                "key_type": "rsa",
                "key_size": 2048,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        self.assertIsNotNone(key.kid)

    def test_rsa_3072(self):
        """Test 3072-bit RSA key generation."""
        key = self.AsymmetricKey.create(
            {
                "name": "RSA 3072 Key",
                "key_type": "rsa",
                "key_size": 3072,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        self.assertIsNotNone(key.kid)

    def test_rsa_4096(self):
        """Test 4096-bit RSA key generation."""
        key = self.AsymmetricKey.create(
            {
                "name": "RSA 4096 Key",
                "key_type": "rsa",
                "key_size": 4096,
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        self.assertIsNotNone(key.kid)


class TestAsymmetricKeyECCurves(TransactionCase):
    """Test different EC curves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AsymmetricKey = cls.env["spp.asymmetric.key"]

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

    def test_ec_p256(self):
        """Test P-256 curve key generation."""
        key = self.AsymmetricKey.create(
            {
                "name": "EC P-256 Key",
                "key_type": "ec",
                "curve": "P-256",
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        public_key = json.loads(key.public_key_jwk)
        self.assertEqual(public_key.get("crv"), "P-256")

    def test_ec_p384(self):
        """Test P-384 curve key generation."""
        key = self.AsymmetricKey.create(
            {
                "name": "EC P-384 Key",
                "key_type": "ec",
                "curve": "P-384",
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        public_key = json.loads(key.public_key_jwk)
        self.assertEqual(public_key.get("crv"), "P-384")

    def test_ec_p521(self):
        """Test P-521 curve key generation."""
        key = self.AsymmetricKey.create(
            {
                "name": "EC P-521 Key",
                "key_type": "ec",
                "curve": "P-521",
                "storage_mode": "local",
            }
        )
        key.generate_key_pair()

        public_key = json.loads(key.public_key_jwk)
        self.assertEqual(public_key.get("crv"), "P-521")
