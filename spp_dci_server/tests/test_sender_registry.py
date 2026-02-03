# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI Sender Registry model."""

import logging
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError

from .common import DCIServerCommon

_logger = logging.getLogger(__name__)


class TestSenderRegistry(DCIServerCommon):
    """Test cases for spp.dci.sender.registry model."""

    def test_create_sender(self):
        """Test creating a sender with required fields."""
        sender = self.SenderRegistry.create(
            {
                "name": "Test CRVS",
                "sender_id": "crvs.test.example",
                "public_key": self.test_public_key_pem,
                "algorithm": "ed25519",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
            }
        )

        self.assertTrue(sender.active, "Sender should be active by default")
        self.assertEqual(sender.name, "Test CRVS")
        self.assertEqual(sender.sender_id, "crvs.test.example")
        self.assertEqual(sender.algorithm, "ed25519")
        self.assertIn("BEGIN PUBLIC KEY", sender.public_key)

    def test_sender_id_unique(self):
        """Test that duplicate sender_id should fail due to unique constraint."""
        # Create first sender
        self.SenderRegistry.create(
            {
                "name": "First CRVS",
                "sender_id": "crvs.duplicate.test",
                "public_key": self.test_public_key_pem,
                "algorithm": "ed25519",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
            }
        )

        # Attempt to create second sender with same sender_id
        with self.assertRaises(Exception) as context:
            self.SenderRegistry.create(
                {
                    "name": "Second CRVS",
                    "sender_id": "crvs.duplicate.test",
                    "public_key": self.test_public_key_pem,
                    "algorithm": "ed25519",
                    "partner_id": self.test_partner.id,
                    "organization_type_id": self.org_type_government.id,
                }
            )

        # Check that the error message contains reference to uniqueness constraint
        error_msg = str(context.exception)
        self.assertTrue(
            "sender_id_unique" in error_msg or "unique" in error_msg.lower(),
            f"Expected uniqueness error, got: {error_msg}",
        )

    def test_sender_id_format_valid(self):
        """Test that valid sender_id formats are accepted."""
        valid_ids = [
            "crvs.test.gov",
            "crvs-test-gov",
            "crvs_test_gov",
            "CRVS123",
            "test.123-456_789",
        ]

        for sender_id in valid_ids:
            with self.subTest(sender_id=sender_id):
                sender = self.SenderRegistry.create(
                    {
                        "name": f"Test {sender_id}",
                        "sender_id": sender_id,
                        "public_key": self.test_public_key_pem,
                        "algorithm": "ed25519",
                        "partner_id": self.test_partner.id,
                        "organization_type_id": self.org_type_government.id,
                    }
                )
                self.assertEqual(sender.sender_id, sender_id)

    def test_sender_id_format_invalid(self):
        """Test that invalid sender_id formats are rejected."""
        invalid_ids = [
            "crvs@test",  # @ not allowed
            "crvs test",  # spaces not allowed
            "crvs/test",  # / not allowed
            "crvs\\test",  # \ not allowed
            "crvs:test",  # : not allowed
        ]

        for sender_id in invalid_ids:
            with self.subTest(sender_id=sender_id):
                with self.assertRaises(ValidationError) as context:
                    self.SenderRegistry.create(
                        {
                            "name": f"Test {sender_id}",
                            "sender_id": sender_id,
                            "public_key": self.test_public_key_pem,
                            "algorithm": "ed25519",
                            "partner_id": self.test_partner.id,
                            "organization_type_id": self.org_type_government.id,
                        }
                    )

                error_msg = str(context.exception)
                self.assertIn(
                    "alphanumeric",
                    error_msg.lower(),
                    f"Expected format validation error for '{sender_id}', got: {error_msg}",
                )

    def test_get_by_sender_id_active(self):
        """Test lookup of active sender by sender_id."""
        # Create active sender
        created_sender = self.create_test_sender(sender_id="crvs.lookup.test", active=True)

        # Lookup by sender_id
        found_sender = self.SenderRegistry.get_by_sender_id("crvs.lookup.test")

        self.assertEqual(len(found_sender), 1, "Should find exactly one sender")
        self.assertEqual(found_sender.id, created_sender.id)
        self.assertEqual(found_sender.sender_id, "crvs.lookup.test")

    def test_get_by_sender_id_inactive(self):
        """Test that inactive senders are not found by get_by_sender_id."""
        # Create inactive sender
        self.create_test_sender(sender_id="crvs.inactive.test", active=False)

        # Lookup should not find inactive sender
        found_sender = self.SenderRegistry.get_by_sender_id("crvs.inactive.test")

        self.assertEqual(len(found_sender), 0, "Should not find inactive sender")

    def test_get_by_sender_id_nonexistent(self):
        """Test lookup of non-existent sender returns empty recordset."""
        found_sender = self.SenderRegistry.get_by_sender_id("nonexistent.sender")

        self.assertEqual(len(found_sender), 0, "Should return empty recordset")
        self.assertFalse(found_sender, "Should be falsy")

    def test_get_verifier_success(self):
        """Test getting DCIVerifier from sender with public key."""
        sender = self.create_test_sender()

        verifier = sender.get_verifier()

        # Verify it's a DCIVerifier instance
        from odoo.addons.spp_dci.services.signing import DCIVerifier

        self.assertIsInstance(verifier, DCIVerifier)
        self.assertEqual(verifier.algorithm, "ed25519")

    def test_get_verifier_missing_public_key(self):
        """Test that get_verifier fails when public key is missing."""
        sender = self.SenderRegistry.create(
            {
                "name": "No Key Sender",
                "sender_id": "crvs.nokey.test",
                "algorithm": "ed25519",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
                # public_key intentionally not set
            }
        )

        with self.assertRaises(UserError) as context:
            sender.get_verifier()

        error_msg = str(context.exception)
        self.assertIn(
            "public key",
            error_msg.lower(),
            "Error should mention missing public key",
        )

    def test_get_verifier_missing_algorithm(self):
        """Test that get_verifier fails when algorithm is missing."""
        sender = self.SenderRegistry.create(
            {
                "name": "No Algorithm Sender",
                "sender_id": "crvs.noalgo.test",
                "public_key": self.test_public_key_pem,
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
                # algorithm intentionally not set
            }
        )

        with self.assertRaises(UserError) as context:
            sender.get_verifier()

        error_msg = str(context.exception)
        self.assertIn(
            "algorithm",
            error_msg.lower(),
            "Error should mention missing algorithm",
        )

    def test_jwks_url_format_valid(self):
        """Test that valid JWKS URLs are accepted."""
        valid_urls = [
            "https://crvs.test.gov/.well-known/jwks.json",
            "http://localhost:8000/jwks.json",
            "https://example.com/api/v1/jwks",
        ]

        for jwks_url in valid_urls:
            with self.subTest(jwks_url=jwks_url):
                sender = self.SenderRegistry.create(
                    {
                        "name": "Test JWKS URL",
                        "sender_id": f"test.{hash(jwks_url)}",
                        "jwks_url": jwks_url,
                        "algorithm": "ed25519",
                        "partner_id": self.test_partner.id,
                        "organization_type_id": self.org_type_government.id,
                    }
                )
                self.assertEqual(sender.jwks_url, jwks_url)

    def test_jwks_url_format_invalid(self):
        """Test that invalid JWKS URLs are rejected."""
        invalid_urls = [
            "ftp://crvs.test.gov/jwks.json",  # ftp not allowed
            "crvs.test.gov/jwks.json",  # missing protocol
            "//crvs.test.gov/jwks.json",  # missing protocol
        ]

        for jwks_url in invalid_urls:
            with self.subTest(jwks_url=jwks_url):
                with self.assertRaises(ValidationError) as context:
                    self.SenderRegistry.create(
                        {
                            "name": "Test Invalid JWKS URL",
                            "sender_id": f"test.invalid.{hash(jwks_url)}",
                            "jwks_url": jwks_url,
                            "algorithm": "ed25519",
                            "partner_id": self.test_partner.id,
                            "organization_type_id": self.org_type_government.id,
                        }
                    )

                error_msg = str(context.exception)
                self.assertIn(
                    "http",
                    error_msg.lower(),
                    f"Expected URL format error for '{jwks_url}', got: {error_msg}",
                )

    def test_fetch_public_key_success(self):
        """Test fetching public key from JWKS endpoint."""
        sender = self.SenderRegistry.create(
            {
                "name": "Test JWKS Fetch",
                "sender_id": "crvs.jwks.test",
                "jwks_url": "https://crvs.test.gov/.well-known/jwks.json",
                "algorithm": "ed25519",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
            }
        )

        # Mock the requests.get call
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [
                {
                    "kid": "crvs.jwks.test|key-001|ed25519",
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            sender.fetch_public_key()

        # Verify that public_key and algorithm were updated
        self.assertTrue(sender.public_key, "Public key should be set")
        self.assertIn("BEGIN PUBLIC KEY", sender.public_key)
        self.assertEqual(sender.algorithm, "ed25519")
        self.assertTrue(sender.last_key_fetch, "Last fetch timestamp should be set")

    def test_fetch_public_key_no_url(self):
        """Test that fetching public key fails when JWKS URL is not set."""
        sender = self.SenderRegistry.create(
            {
                "name": "No URL Sender",
                "sender_id": "crvs.nourl.test",
                "algorithm": "ed25519",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
                # jwks_url intentionally not set
            }
        )

        with self.assertRaises(UserError) as context:
            sender.fetch_public_key()

        error_msg = str(context.exception)
        self.assertIn(
            "jwks url",
            error_msg.lower(),
            "Error should mention missing JWKS URL",
        )

    def test_fetch_public_key_no_matching_key(self):
        """Test that fetching public key fails when no matching key found in JWKS."""
        sender = self.SenderRegistry.create(
            {
                "name": "No Match Sender",
                "sender_id": "crvs.nomatch.test",
                "jwks_url": "https://crvs.test.gov/.well-known/jwks.json",
                "algorithm": "ed25519",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
            }
        )

        # Mock the requests.get call with non-matching key
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [
                {
                    "kid": "different.sender|key-001|ed25519",  # Different sender_id
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            with self.assertRaises(UserError) as context:
                sender.fetch_public_key()

        error_msg = str(context.exception)
        self.assertIn(
            "no matching key",
            error_msg.lower(),
            "Error should mention no matching key",
        )

    def test_action_fetch_public_key_success(self):
        """Test the button action for fetching public key."""
        sender = self.SenderRegistry.create(
            {
                "name": "Test Button Action",
                "sender_id": "crvs.button.test",
                "jwks_url": "https://crvs.test.gov/.well-known/jwks.json",
                "algorithm": "ed25519",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
            }
        )

        # Mock the requests.get call
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [
                {
                    "kid": "crvs.button.test|key-001|ed25519",
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response):
            result = sender.action_fetch_public_key()

        # Verify notification action was returned
        self.assertEqual(result.get("type"), "ir.actions.client")
        self.assertEqual(result.get("tag"), "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    def test_action_fetch_public_key_failure(self):
        """Test that button action raises UserError on failure."""
        sender = self.SenderRegistry.create(
            {
                "name": "Test Button Failure",
                "sender_id": "crvs.failure.test",
                "jwks_url": "https://invalid.test.gov/jwks.json",
                "algorithm": "ed25519",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
            }
        )

        # Mock the requests.get call to raise exception
        with patch("requests.get", side_effect=Exception("Connection failed")):
            with self.assertRaises(UserError) as context:
                sender.action_fetch_public_key()

        error_msg = str(context.exception)
        self.assertIn(
            "failed",
            error_msg.lower(),
            "Error should mention failure",
        )

    def test_jwk_to_pem_ed25519(self):
        """Test converting Ed25519 JWK to PEM format."""
        sender = self.create_test_sender()

        jwk = {
            "kty": "OKP",
            "crv": "Ed25519",
            "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
        }

        pem = sender._jwk_to_pem(jwk)

        self.assertIsInstance(pem, str)
        self.assertIn("BEGIN PUBLIC KEY", pem)
        self.assertIn("END PUBLIC KEY", pem)

    def test_jwk_to_pem_rsa(self):
        """Test converting RSA JWK to PEM format."""
        sender = self.create_test_sender()

        jwk = {
            "kty": "RSA",
            "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAt",
            "e": "AQAB",
        }

        pem = sender._jwk_to_pem(jwk)

        self.assertIsInstance(pem, str)
        self.assertIn("BEGIN PUBLIC KEY", pem)
        self.assertIn("END PUBLIC KEY", pem)

    def test_jwk_to_pem_unsupported_type(self):
        """Test that unsupported JWK type raises error."""
        sender = self.create_test_sender()

        jwk = {
            "kty": "EC",  # Unsupported
            "crv": "P-256",
            "x": "WKn-ZIGevcwGIyyrzFoZNBdaq9_TsqzGl96oc0CWuis",
            "y": "y77t-RvAHRKTsSGdIYUfweuOvwrvDD-Q3Hv5J0fSKbE",
        }

        with self.assertRaises(UserError) as context:
            sender._jwk_to_pem(jwk)

        error_msg = str(context.exception)
        self.assertIn(
            "unsupported",
            error_msg.lower(),
            "Error should mention unsupported key type",
        )
