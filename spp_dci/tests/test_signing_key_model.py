"""Tests for spp.dci.signing.key model."""

from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestSigningKey(TransactionCase):
    """Test spp.dci.signing.key model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SigningKey = cls.env["spp.dci.signing.key"]

        # Set sender_id config parameter
        cls.env["ir.config_parameter"].sudo().set_param("dci.sender_id", "test-sender")

    def test_generate_ed25519_key(self):
        """Test generating Ed25519 keypair."""
        key = self.SigningKey.create(
            {
                "name": "Test Ed25519 Key",
                "key_id": "test-ed25519-1",
                "algorithm": "ed25519",
            }
        )

        # Initially, keys should be empty
        self.assertFalse(key.private_key)
        self.assertFalse(key.public_key)
        self.assertEqual(key.state, "draft")

        # Generate keypair
        key.action_generate_key()

        # Verify keys are populated
        self.assertTrue(key.private_key)
        self.assertTrue(key.public_key)
        self.assertIn("BEGIN PRIVATE KEY", key.private_key)
        self.assertIn("BEGIN PUBLIC KEY", key.public_key)

        # Verify still in draft state
        self.assertEqual(key.state, "draft")

    def test_generate_rsa_key(self):
        """Test generating RSA keypair."""
        key = self.SigningKey.create(
            {
                "name": "Test RSA Key",
                "key_id": "test-rsa-1",
                "algorithm": "rs256",
            }
        )

        # Generate keypair
        key.action_generate_key()

        # Verify keys are populated
        self.assertTrue(key.private_key)
        self.assertTrue(key.public_key)
        self.assertIn("BEGIN PRIVATE KEY", key.private_key)
        self.assertIn("BEGIN PUBLIC KEY", key.public_key)

    def test_activate_key(self):
        """Test activating a signing key."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-key-activate",
                "algorithm": "ed25519",
            }
        )

        # Generate keypair
        key.action_generate_key()

        # Initially in draft state
        self.assertEqual(key.state, "draft")
        self.assertFalse(key.activated_date)

        # Activate key
        key.action_activate()

        # Verify state and timestamp
        self.assertEqual(key.state, "active")
        self.assertTrue(key.activated_date)

    def test_revoke_key(self):
        """Test revoking a signing key."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-key-revoke",
                "algorithm": "ed25519",
            }
        )

        # Generate and activate key
        key.action_generate_key()
        key.action_activate()

        # Initially active
        self.assertEqual(key.state, "active")
        self.assertFalse(key.revoked_date)

        # Revoke key
        key.action_revoke()

        # Verify state and timestamp
        self.assertEqual(key.state, "revoked")
        self.assertTrue(key.revoked_date)

    def test_get_jwks_entry_ed25519(self):
        """Test JWKS entry generation for Ed25519 key."""
        key = self.SigningKey.create(
            {
                "name": "Test Ed25519 Key",
                "key_id": "test-jwks-ed25519",
                "algorithm": "ed25519",
            }
        )

        # Generate keypair
        key.action_generate_key()

        # Get JWKS entry
        jwks_entry = key.get_jwks_entry()

        # Verify JWKS format for Ed25519
        self.assertEqual(jwks_entry["kty"], "OKP")
        self.assertEqual(jwks_entry["use"], "sig")
        self.assertEqual(jwks_entry["alg"], "EdDSA")
        self.assertEqual(jwks_entry["crv"], "Ed25519")
        self.assertIn("kid", jwks_entry)
        self.assertIn("x", jwks_entry)

        # Verify kid format: {sender_id}|{key_id}|{algorithm}
        expected_kid = "test-sender|test-jwks-ed25519|ed25519"
        self.assertEqual(jwks_entry["kid"], expected_kid)

    def test_get_jwks_entry_rsa(self):
        """Test JWKS entry generation for RSA key."""
        key = self.SigningKey.create(
            {
                "name": "Test RSA Key",
                "key_id": "test-jwks-rsa",
                "algorithm": "rs256",
            }
        )

        # Generate keypair
        key.action_generate_key()

        # Get JWKS entry
        jwks_entry = key.get_jwks_entry()

        # Verify JWKS format for RSA
        self.assertEqual(jwks_entry["kty"], "RSA")
        self.assertEqual(jwks_entry["use"], "sig")
        self.assertEqual(jwks_entry["alg"], "RS256")
        self.assertIn("kid", jwks_entry)
        self.assertIn("n", jwks_entry)  # Modulus
        self.assertIn("e", jwks_entry)  # Exponent

        # Verify kid format
        expected_kid = "test-sender|test-jwks-rsa|rs256"
        self.assertEqual(jwks_entry["kid"], expected_kid)

    def test_get_signer(self):
        """Test getting DCISigner from active key."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-signer",
                "algorithm": "ed25519",
            }
        )

        # Generate and activate key
        key.action_generate_key()
        key.action_activate()

        # Get signer
        signer = key.get_signer()

        # Verify signer is configured correctly
        self.assertEqual(signer.sender_id, "test-sender")
        self.assertEqual(signer.key_id, "test-signer")
        self.assertEqual(signer.algorithm, "ed25519")

        # Test that signer can sign
        header = {"action": "search"}
        message = {"transaction_id": "test"}
        signature = signer.sign(header, message)
        self.assertIsInstance(signature, str)
        self.assertGreater(len(signature), 0)

    def test_cannot_sign_with_inactive_key(self):
        """Test that signing fails with non-active key."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-inactive",
                "algorithm": "ed25519",
            }
        )

        # Generate but don't activate
        key.action_generate_key()

        # Should raise error when trying to get signer
        with self.assertRaises(UserError):
            key.get_signer()

    def test_cannot_activate_without_keys(self):
        """Test that activation fails without generated keys."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-no-keys",
                "algorithm": "ed25519",
            }
        )

        # Try to activate without generating keys
        with self.assertRaises(UserError):
            key.action_activate()

    def test_cannot_generate_keys_twice(self):
        """Test that keys can only be generated once."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-duplicate",
                "algorithm": "ed25519",
            }
        )

        # Generate keys once
        key.action_generate_key()

        # Try to generate again
        with self.assertRaises(UserError):
            key.action_generate_key()

    def test_cannot_generate_keys_when_active(self):
        """Test that keys cannot be generated in active state."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-active-gen",
                "algorithm": "ed25519",
            }
        )

        # Generate and activate
        key.action_generate_key()
        key.action_activate()

        # Create new key and try to activate it first (won't work)
        # Instead, test by manually setting state
        key2 = self.SigningKey.create(
            {
                "name": "Test Key 2",
                "key_id": "test-active-gen-2",
                "algorithm": "ed25519",
            }
        )

        # Generate keys
        key2.action_generate_key()
        key2.action_activate()

        # Now key2 is active, try to generate keys again
        with self.assertRaises(UserError):
            key2.action_generate_key()

    def test_key_id_uniqueness(self):
        """Test that key_id must be unique."""
        self.SigningKey.create(
            {
                "name": "Test Key 1",
                "key_id": "duplicate-key-id",
                "algorithm": "ed25519",
            }
        )

        # Try to create another with same key_id
        # The model has a Python constraint that raises ValidationError before
        # the database constraint is triggered
        with self.assertRaises(ValidationError):
            self.SigningKey.create(
                {
                    "name": "Test Key 2",
                    "key_id": "duplicate-key-id",
                    "algorithm": "ed25519",
                }
            )

    def test_key_id_format_validation(self):
        """Test key_id format validation."""
        # Valid key IDs
        valid_key_ids = ["key1", "primary-2024", "test_key_123"]
        for key_id in valid_key_ids:
            key = self.SigningKey.create(
                {
                    "name": f"Test {key_id}",
                    "key_id": key_id,
                    "algorithm": "ed25519",
                }
            )
            # Should not raise
            self.assertEqual(key.key_id, key_id)

        # Invalid key IDs
        invalid_key_ids = ["key with spaces", "key@special", "key!invalid"]
        for key_id in invalid_key_ids:
            with self.assertRaises(ValidationError):
                self.SigningKey.create(
                    {
                        "name": f"Test {key_id}",
                        "key_id": key_id,
                        "algorithm": "ed25519",
                    }
                )

    def test_expiration_date_validation(self):
        """Test that expiration date must be in future."""
        # Valid expiration (future)
        future_date = datetime.now() + timedelta(days=30)
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-expiration-valid",
                "algorithm": "ed25519",
                "expires_at": future_date,
            }
        )
        self.assertEqual(key.expires_at, future_date)

        # Invalid expiration (past)
        past_date = datetime.now() - timedelta(days=30)
        with self.assertRaises(ValidationError):
            self.SigningKey.create(
                {
                    "name": "Test Key",
                    "key_id": "test-expiration-invalid",
                    "algorithm": "ed25519",
                    "expires_at": past_date,
                }
            )

    def test_get_active_key(self):
        """Test getting active key."""
        # Delete all existing signing keys to ensure complete test isolation
        self.SigningKey.search([]).unlink()

        # Create multiple keys
        key1 = self.SigningKey.create(
            {
                "name": "Key 1",
                "key_id": "active-key-1",
                "algorithm": "ed25519",
            }
        )
        key1.action_generate_key()
        key1.action_activate()

        # Create second key (different algorithm)
        key2 = self.SigningKey.create(
            {
                "name": "Key 2",
                "key_id": "active-key-2",
                "algorithm": "rs256",
            }
        )
        key2.action_generate_key()
        key2.action_activate()

        # Get active ed25519 key - should be key1 (only ed25519 key)
        active_ed25519 = self.SigningKey.get_active_key(algorithm="ed25519")
        self.assertEqual(active_ed25519.key_id, "active-key-1")

        # Get active rs256 key - should be key2 (only rs256 key)
        active_rs256 = self.SigningKey.get_active_key(algorithm="rs256")
        self.assertEqual(active_rs256.key_id, "active-key-2")

        # Get any active key (should return most recently activated/created)
        active_any = self.SigningKey.get_active_key()
        self.assertEqual(active_any.key_id, "active-key-2")  # key2 created last

    def test_cannot_activate_revoked_key(self):
        """Test that revoked key cannot be reactivated."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-revoke-reactivate",
                "algorithm": "ed25519",
            }
        )

        # Generate, activate, and revoke
        key.action_generate_key()
        key.action_activate()
        key.action_revoke()

        # Try to activate again
        with self.assertRaises(UserError):
            key.action_activate()

    def test_revoke_already_revoked_key(self):
        """Test that revoking already revoked key raises error."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-double-revoke",
                "algorithm": "ed25519",
            }
        )

        # Generate, activate, and revoke
        key.action_generate_key()
        key.action_activate()
        key.action_revoke()

        # Try to revoke again
        with self.assertRaises(UserError):
            key.action_revoke()

    def test_activate_already_active_key(self):
        """Test that activating already active key raises error."""
        key = self.SigningKey.create(
            {
                "name": "Test Key",
                "key_id": "test-double-activate",
                "algorithm": "ed25519",
            }
        )

        # Generate and activate
        key.action_generate_key()
        key.action_activate()

        # Try to activate again
        with self.assertRaises(UserError):
            key.action_activate()
