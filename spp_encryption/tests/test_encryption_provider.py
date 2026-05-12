# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Encryption Provider with spp_key_management integration."""

import base64
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.tools import config


class TestEncryptionProviderBase(TransactionCase):
    """Base test class with common setup."""

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

    @classmethod
    def tearDownClass(cls):
        # Restore original master key configuration
        if cls._original_master_key:
            config["spp_master_key"] = cls._original_master_key
        elif "spp_master_key" in config.options:
            del config.options["spp_master_key"]
        super().tearDownClass()


class TestEncryptionProvider(TestEncryptionProviderBase):
    """Test basic encryption provider functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider_no_type = cls.env["spp.encryption.provider"].create({"name": "Test Provider No Type"})

        cls.provider = cls.env["spp.encryption.provider"].create(
            {
                "name": "Test Provider with Type",
                "type": "jwcrypto",
            }
        )

        cls.provider_with_key = cls.env["spp.encryption.provider"].create(
            {
                "name": "Test Provider with Key",
                "type": "jwcrypto",
            }
        )
        cls.provider_with_key.generate_key()

    def test_provider_without_key_raises_error(self):
        """Test that provider without key raises ValueError."""
        self.assertFalse(self.provider.key_id)

        with self.assertRaises(ValueError):
            self.provider._get_jwk_key()

    def test_get_jwk_key_with_generated_key(self):
        """Test retrieving JWK key after generation."""
        self.assertTrue(self.provider_with_key.key_id)

        jwk_key = self.provider_with_key._get_jwk_key()

        # RSA key should have these components
        expected_keys = ["kty", "kid", "n", "e", "d", "p", "q", "dp", "dq", "qi"]
        self.assertTrue(all(elem in expected_keys for elem in jwk_key.keys()))

    def test_get_public_key(self):
        """Test retrieving public key."""
        self.assertTrue(self.provider_with_key.key_id)

        public_key = self.provider_with_key._get_public_key()

        self.assertIsNotNone(public_key)


class TestEncryptDataJWCrypto(TestEncryptionProviderBase):
    """Test data encryption with JWCrypto provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider_no_type = cls.env["spp.encryption.provider"].create({"name": "Provider No Type"})

        cls.provider = cls.env["spp.encryption.provider"].create(
            {
                "name": "Provider for Encryption",
                "type": "jwcrypto",
            }
        )

        cls.provider_with_key = cls.env["spp.encryption.provider"].create(
            {
                "name": "Provider with Key for Encryption",
                "type": "jwcrypto",
            }
        )
        cls.provider_with_key.generate_key()

    def test_encrypt_data_no_type_raises_error(self):
        """Test that encryption without type raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.provider_no_type.encrypt_data(b"test")

    def test_encrypt_data_calls_type_method(self):
        """Test that encrypt_data dispatches to type-specific method."""
        with patch.object(type(self.provider), "encrypt_data_jwcrypto", return_value=b"encrypted") as mock_encrypt:
            self.provider.encrypt_data(b"test")
            mock_encrypt.assert_called_once()

    def test_encrypt_data_with_key(self):
        """Test actual encryption with a key."""
        data = b"test data to encrypt"

        encrypted = self.provider_with_key.encrypt_data(data)

        self.assertIsNotNone(encrypted)
        self.assertIsInstance(encrypted, bytes)
        self.assertNotEqual(encrypted, data)


class TestDecryptDataJWCrypto(TestEncryptionProviderBase):
    """Test data decryption with JWCrypto provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider_no_type = cls.env["spp.encryption.provider"].create({"name": "Provider No Type"})

        cls.provider_with_key = cls.env["spp.encryption.provider"].create(
            {
                "name": "Provider with Key for Decryption",
                "type": "jwcrypto",
            }
        )
        cls.provider_with_key.generate_key()

    def test_decrypt_data_no_type_raises_error(self):
        """Test that decryption without type raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.provider_no_type.decrypt_data(b"test")

    def test_encrypt_decrypt_roundtrip(self):
        """Test that data can be encrypted and decrypted."""
        original_data = b"This is secret data!"

        encrypted = self.provider_with_key.encrypt_data(original_data)
        decrypted = self.provider_with_key.decrypt_data(encrypted)

        self.assertEqual(decrypted, original_data)

    def test_encrypt_decrypt_unicode(self):
        """Test encryption of unicode data."""
        original_data = "Hello 世界! 🔐".encode()

        encrypted = self.provider_with_key.encrypt_data(original_data)
        decrypted = self.provider_with_key.decrypt_data(encrypted)

        self.assertEqual(decrypted, original_data)


class TestJWTSigningJWCrypto(TestEncryptionProviderBase):
    """Test JWT signing with JWCrypto provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider_no_type = cls.env["spp.encryption.provider"].create({"name": "Provider No Type"})

        cls.provider_with_key = cls.env["spp.encryption.provider"].create(
            {
                "name": "Provider with Key for JWT",
                "type": "jwcrypto",
            }
        )
        cls.provider_with_key.generate_key()

    def test_jwt_sign_no_type_raises_error(self):
        """Test that JWT signing without type raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.provider_no_type.jwt_sign({})

    def test_jwt_sign_with_key(self):
        """Test JWT signing with a key."""
        claims = {"sub": "user123", "iss": "test"}

        token = self.provider_with_key.jwt_sign(claims)

        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)
        # JWT has 3 parts separated by dots
        self.assertEqual(len(token.split(".")), 3)


class TestJWTVerificationJWCrypto(TestEncryptionProviderBase):
    """Test JWT verification with JWCrypto provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider_no_type = cls.env["spp.encryption.provider"].create({"name": "Provider No Type"})

        cls.provider_with_key = cls.env["spp.encryption.provider"].create(
            {
                "name": "Provider with Key for Verification",
                "type": "jwcrypto",
            }
        )
        cls.provider_with_key.generate_key()

    def test_jwt_verify_no_type_raises_error(self):
        """Test that JWT verification without type raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.provider_no_type.jwt_verify("test")

    def test_jwt_sign_and_verify(self):
        """Test signing and verifying a JWT."""
        claims = {"sub": "user123", "data": "test"}

        token = self.provider_with_key.jwt_sign(claims)
        verified, received_jwt = self.provider_with_key.jwt_verify(token)

        self.assertTrue(verified)
        self.assertIsNotNone(received_jwt)

    def test_jwt_verify_invalid_signature(self):
        """Test that invalid JWT fails verification."""
        claims = {"sub": "user123"}
        token = self.provider_with_key.jwt_sign(claims)

        # Tamper with the token
        parts = token.split(".")
        parts[2] = "invalidsignature"
        tampered_token = ".".join(parts)

        verified, received_jwt = self.provider_with_key.jwt_verify(tampered_token)

        self.assertFalse(verified)
        self.assertIsNone(received_jwt)


class TestJWKSJWCrypto(TestEncryptionProviderBase):
    """Test JWKS export with JWCrypto provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider_no_type = cls.env["spp.encryption.provider"].create({"name": "Provider No Type"})

        cls.provider = cls.env["spp.encryption.provider"].create(
            {
                "name": "Provider for JWKS",
                "type": "jwcrypto",
            }
        )

        cls.provider_with_key = cls.env["spp.encryption.provider"].create(
            {
                "name": "Provider with Key for JWKS",
                "type": "jwcrypto",
            }
        )
        cls.provider_with_key.generate_key()

    def test_get_jwks_no_type_raises_error(self):
        """Test that JWKS export without type raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.provider_no_type.get_jwks()

    def test_get_jwks_no_key_returns_empty(self):
        """Test that JWKS without key returns empty keys array."""
        jwks = self.provider.get_jwks()

        self.assertIsNotNone(jwks)
        self.assertIn("keys", jwks)
        self.assertEqual(len(jwks["keys"]), 0)

    def test_get_jwks_with_key(self):
        """Test JWKS export with a key."""
        jwks = self.provider_with_key.get_jwks()

        self.assertIsNotNone(jwks)
        self.assertIn("keys", jwks)
        self.assertEqual(len(jwks["keys"]), 1)

        # Verify public key structure
        public_key = jwks["keys"][0]
        self.assertIn("kty", public_key)
        self.assertIn("kid", public_key)
        self.assertIn("n", public_key)  # RSA modulus
        self.assertIn("e", public_key)  # RSA exponent

    def test_jwks_does_not_contain_private_key(self):
        """Test that JWKS export doesn't contain private key components."""
        jwks = self.provider_with_key.get_jwks()
        public_key = jwks["keys"][0]

        # RSA private key components should NOT be present
        private_components = ["d", "p", "q", "dp", "dq", "qi"]
        for component in private_components:
            self.assertNotIn(component, public_key)


class TestKeyGeneration(TestEncryptionProviderBase):
    """Test key generation functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider = cls.env["spp.encryption.provider"].create(
            {
                "name": "Provider for Key Generation",
                "type": "jwcrypto",
            }
        )

    def test_generate_key_creates_asymmetric_key(self):
        """Test that generate_key creates an asymmetric key record."""
        self.assertFalse(self.provider.key_id)

        key_record = self.provider.generate_key()

        self.assertTrue(self.provider.key_id)
        self.assertEqual(self.provider.key_id, key_record)
        self.assertIsNotNone(key_record.kid)

    def test_generate_key_default_type_is_rsa(self):
        """Test that default key type is RSA."""
        provider = self.env["spp.encryption.provider"].create(
            {
                "name": "RSA Default Test",
                "type": "jwcrypto",
            }
        )

        provider.generate_key()

        self.assertEqual(provider.key_id.key_type, "rsa")

    def test_generate_ec_key(self):
        """Test generating an EC key."""
        provider = self.env["spp.encryption.provider"].create(
            {
                "name": "EC Key Test",
                "type": "jwcrypto",
            }
        )

        provider.generate_key(key_type="ec", curve="P-256")

        self.assertEqual(provider.key_id.key_type, "ec")
        self.assertEqual(provider.key_id.curve, "P-256")

    def test_generate_key_sets_proper_size(self):
        """Test that key size is set correctly."""
        provider = self.env["spp.encryption.provider"].create(
            {
                "name": "Key Size Test",
                "type": "jwcrypto",
            }
        )

        provider.generate_key(key_type="rsa", key_size=4096)

        self.assertEqual(provider.key_id.key_size, 4096)

    def test_action_generate_key_without_existing(self):
        """Test UI action to generate key when none exists."""
        provider = self.env["spp.encryption.provider"].create(
            {
                "name": "Action Generate Test",
                "type": "jwcrypto",
            }
        )

        result = provider.action_generate_key()

        # Should return notification
        self.assertEqual(result.get("type"), "ir.actions.client")
        self.assertTrue(provider.key_id)


class TestKeyStorageIntegration(TestEncryptionProviderBase):
    """Test integration with spp_key_management."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider_with_key = cls.env["spp.encryption.provider"].create(
            {
                "name": "Integration Test Provider",
                "type": "jwcrypto",
            }
        )
        cls.provider_with_key.generate_key()

    def test_key_stored_in_asymmetric_key_model(self):
        """Test that key is stored in spp.asymmetric.key model."""
        key_record = self.provider_with_key.key_id

        self.assertEqual(key_record._name, "spp.asymmetric.key")

    def test_private_key_is_encrypted(self):
        """Test that private key is stored encrypted."""
        key_record = self.provider_with_key.key_id

        # Private key should be encrypted (not valid JSON)
        import json

        try:
            parsed = json.loads(key_record.encrypted_private_key)
            if "d" in parsed:  # RSA private exponent
                self.fail("Private key stored in plaintext!")
        except json.JSONDecodeError:
            # Expected - encrypted data is not valid JSON
            pass

    def test_public_key_is_available(self):
        """Test that public key is readily available."""
        key_record = self.provider_with_key.key_id

        self.assertIsNotNone(key_record.public_key_jwk)

        import json

        public_key = json.loads(key_record.public_key_jwk)

        self.assertIn("kty", public_key)
        self.assertIn("kid", public_key)
