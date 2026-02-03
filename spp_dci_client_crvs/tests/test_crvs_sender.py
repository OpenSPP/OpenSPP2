# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for CRVS Sender Registry model."""

import logging
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import CRVSClientCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestCRVSSender(CRVSClientCommon):
    """Test cases for CRVS Sender Registry model."""

    def setUp(self):
        """Set up test fixtures for each test method."""
        super().setUp()

    def test_create_sender_with_public_key(self):
        """Test creating a CRVS sender with public key."""
        sender = self.create_test_crvs_sender(
            sender_id="crvs.test.gov",
            name="Test CRVS Registry",
        )

        self.assertTrue(sender.id, "Sender should be created")
        self.assertEqual(sender.sender_id, "crvs.test.gov")
        self.assertEqual(sender.name, "Test CRVS Registry")
        self.assertEqual(sender.algorithm, self.test_algorithm)
        self.assertTrue(sender.public_key, "Public key should be set")
        self.assertTrue(sender.active, "Sender should be active by default")

    def test_create_sender_minimal(self):
        """Test creating a CRVS sender with minimal required fields."""
        sender = self.CRVSSender.create(
            {
                "name": "Minimal CRVS",
                "sender_id": "crvs.minimal.gov",
            }
        )

        self.assertTrue(sender.id, "Sender should be created")
        self.assertEqual(sender.sender_id, "crvs.minimal.gov")
        self.assertFalse(sender.public_key, "Public key is optional")
        self.assertFalse(sender.algorithm, "Algorithm is optional")

    def test_get_by_sender_id_found(self):
        """Test lookup by sender_id returns correct sender."""
        sender = self.create_test_crvs_sender(sender_id="crvs.lookup.test")

        result = self.CRVSSender.get_by_sender_id("crvs.lookup.test")

        self.assertEqual(result.id, sender.id, "Should return the correct sender")
        self.assertEqual(result.sender_id, "crvs.lookup.test")

    def test_get_by_sender_id_not_found(self):
        """Test lookup by sender_id returns empty recordset when not found."""
        result = self.CRVSSender.get_by_sender_id("crvs.nonexistent.gov")

        self.assertFalse(result, "Should return empty recordset")
        self.assertEqual(len(result), 0)

    def test_get_by_sender_id_inactive_not_returned(self):
        """Test inactive sender not returned by get_by_sender_id."""
        self.create_test_crvs_sender(
            sender_id="crvs.inactive.test",
            active=False,
        )

        result = self.CRVSSender.get_by_sender_id("crvs.inactive.test")

        self.assertFalse(result, "Inactive sender should not be returned")

    def test_get_verifier_returns_dci_verifier(self):
        """Test get_verifier returns DCIVerifier instance."""
        sender = self.create_test_crvs_sender()

        verifier = sender.get_verifier()

        self.assertIsNotNone(verifier, "Verifier should not be None")
        # Check it's a DCIVerifier by verifying it has the verify method
        self.assertTrue(hasattr(verifier, "verify"), "Should have verify method")

    def test_get_verifier_without_public_key_raises_error(self):
        """Test get_verifier raises error when public key is missing."""
        sender = self.CRVSSender.create(
            {
                "name": "No Key Sender",
                "sender_id": "crvs.nokey.test",
                "algorithm": "ed25519",
                # public_key intentionally not set
            }
        )

        with self.assertRaises(UserError) as context:
            sender.get_verifier()

        self.assertIn("no public key", str(context.exception).lower())
        self.assertIn(sender.sender_id, str(context.exception))

    def test_get_verifier_without_algorithm_raises_error(self):
        """Test get_verifier raises error when algorithm is missing."""
        sender = self.CRVSSender.create(
            {
                "name": "No Algorithm Sender",
                "sender_id": "crvs.noalgo.test",
                "public_key": self.test_public_key_pem,
                # algorithm intentionally not set
            }
        )

        with self.assertRaises(UserError) as context:
            sender.get_verifier()

        self.assertIn("algorithm", str(context.exception).lower())
        self.assertIn(sender.sender_id, str(context.exception))

    def test_sender_id_uniqueness_constraint(self):
        """Test sender_id must be unique."""
        self.create_test_crvs_sender(sender_id="crvs.unique.test")

        # Try to create another sender with the same sender_id
        with self.assertRaises(ValidationError) as context:
            self.create_test_crvs_sender(sender_id="crvs.unique.test")

        self.assertIn("unique", str(context.exception).lower())

    def test_sender_id_format_validation(self):
        """Test sender_id format validation."""
        # Valid formats should work
        valid_ids = [
            "crvs.test.gov",
            "crvs-test-gov",
            "crvs_test_gov",
            "crvs123.test456",
            "CRVS.TEST.GOV",
        ]

        for sender_id in valid_ids:
            sender = self.CRVSSender.create(
                {
                    "name": f"Test {sender_id}",
                    "sender_id": sender_id,
                }
            )
            self.assertTrue(sender.id, f"Should accept valid sender_id: {sender_id}")

        # Invalid formats should fail
        invalid_ids = [
            "crvs test gov",  # space
            "crvs@test.gov",  # special char
            "crvs/test",  # slash
            "crvs#test",  # hash
        ]

        for sender_id in invalid_ids:
            with self.assertRaises(ValidationError, msg=f"Should reject invalid sender_id: {sender_id}"):
                self.CRVSSender.create(
                    {
                        "name": f"Test {sender_id}",
                        "sender_id": sender_id,
                    }
                )

    def test_jwks_url_format_validation(self):
        """Test JWKS URL format validation."""
        # Valid URLs should work
        sender = self.CRVSSender.create(
            {
                "name": "Test JWKS",
                "sender_id": "crvs.jwks.test",
                "jwks_url": "https://crvs.test.gov/.well-known/jwks.json",
            }
        )
        self.assertTrue(sender.id, "Should accept valid HTTPS URL")

        sender2 = self.CRVSSender.create(
            {
                "name": "Test JWKS HTTP",
                "sender_id": "crvs.jwks.test2",
                "jwks_url": "http://localhost:8000/jwks",
            }
        )
        self.assertTrue(sender2.id, "Should accept valid HTTP URL")

        # Invalid URL should fail
        with self.assertRaises(ValidationError):
            self.CRVSSender.create(
                {
                    "name": "Test Invalid JWKS",
                    "sender_id": "crvs.jwks.test3",
                    "jwks_url": "ftp://invalid.url",
                }
            )

    def test_fetch_public_key_without_url(self):
        """Test fetch_public_key raises error when JWKS URL not configured."""
        sender = self.create_test_crvs_sender(jwks_url=None)

        with self.assertRaises(UserError) as context:
            sender.fetch_public_key()

        self.assertIn("jwks url not configured", str(context.exception).lower())

    @patch("odoo.addons.spp_dci_client_crvs.models.crvs_sender.requests.get")
    def test_fetch_public_key_success(self, mock_get):
        """Test successful public key fetch from JWKS endpoint."""
        # Create sender with JWKS URL
        sender = self.CRVSSender.create(
            {
                "name": "Test Fetch",
                "sender_id": "crvs.fetch.test",
                "jwks_url": "https://crvs.fetch.test/.well-known/jwks.json",
            }
        )

        # Mock JWKS response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [
                {
                    "kid": "crvs.fetch.test|2024-key|ed25519",
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
                }
            ]
        }
        mock_get.return_value = mock_response

        # Fetch public key
        sender.fetch_public_key()

        # Verify request was made
        mock_get.assert_called_once_with(sender.jwks_url, timeout=10)

        # Verify sender was updated
        self.assertTrue(sender.public_key, "Public key should be set")
        self.assertEqual(sender.algorithm, "ed25519")
        self.assertTrue(sender.last_key_fetch, "Last fetch time should be set")

    @patch("odoo.addons.spp_dci_client_crvs.models.crvs_sender.requests.get")
    def test_fetch_public_key_http_error(self, mock_get):
        """Test fetch_public_key handles HTTP errors."""
        import requests

        sender = self.CRVSSender.create(
            {
                "name": "Test HTTP Error",
                "sender_id": "crvs.httperror.test",
                "jwks_url": "https://crvs.error.test/jwks",
            }
        )

        # Mock HTTP error
        mock_get.side_effect = requests.RequestException("Connection timeout")

        with self.assertRaises(UserError) as context:
            sender.fetch_public_key()

        self.assertIn("failed to fetch", str(context.exception).lower())

    @patch("odoo.addons.spp_dci_client_crvs.models.crvs_sender.requests.get")
    def test_fetch_public_key_invalid_jwks(self, mock_get):
        """Test fetch_public_key handles invalid JWKS response."""
        sender = self.CRVSSender.create(
            {
                "name": "Test Invalid JWKS",
                "sender_id": "crvs.invalid.test",
                "jwks_url": "https://crvs.invalid.test/jwks",
            }
        )

        # Mock invalid JWKS (missing 'keys' field)
        mock_response = MagicMock()
        mock_response.json.return_value = {"invalid": "data"}
        mock_get.return_value = mock_response

        with self.assertRaises(UserError) as context:
            sender.fetch_public_key()

        self.assertIn("invalid jwks", str(context.exception).lower())

    @patch("odoo.addons.spp_dci_client_crvs.models.crvs_sender.requests.get")
    def test_fetch_public_key_no_matching_key(self, mock_get):
        """Test fetch_public_key when no matching key found."""
        sender = self.CRVSSender.create(
            {
                "name": "Test No Match",
                "sender_id": "crvs.nomatch.test",
                "jwks_url": "https://crvs.nomatch.test/jwks",
            }
        )

        # Mock JWKS with non-matching kid
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [
                {
                    "kid": "other.sender|2024-key|ed25519",
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
                }
            ]
        }
        mock_get.return_value = mock_response

        with self.assertRaises(UserError) as context:
            sender.fetch_public_key()

        self.assertIn("no matching key", str(context.exception).lower())

    @patch("odoo.addons.spp_dci_client_crvs.models.crvs_sender.requests.get")
    def test_action_fetch_public_key_success(self, mock_get):
        """Test action_fetch_public_key button action returns notification."""
        sender = self.CRVSSender.create(
            {
                "name": "Test Action",
                "sender_id": "crvs.action.test",
                "jwks_url": "https://crvs.action.test/jwks",
            }
        )

        # Mock successful JWKS response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [
                {
                    "kid": "crvs.action.test|2024-key|ed25519",
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
                }
            ]
        }
        mock_get.return_value = mock_response

        # Call action
        result = sender.action_fetch_public_key()

        # Verify notification
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    @patch("odoo.addons.spp_dci_client_crvs.models.crvs_sender.requests.get")
    def test_action_fetch_public_key_error(self, mock_get):
        """Test action_fetch_public_key raises UserError on failure."""
        import requests

        sender = self.CRVSSender.create(
            {
                "name": "Test Action Error",
                "sender_id": "crvs.actionerror.test",
                "jwks_url": "https://crvs.actionerror.test/jwks",
            }
        )

        # Mock HTTP error
        mock_get.side_effect = requests.RequestException("Connection failed")

        with self.assertRaises(UserError):
            sender.action_fetch_public_key()

    def test_jwk_to_pem_ed25519(self):
        """Test JWK to PEM conversion for Ed25519 keys."""
        sender = self.create_test_crvs_sender()

        jwk = {
            "kty": "OKP",
            "crv": "Ed25519",
            "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
        }

        pem = sender._jwk_to_pem(jwk)

        self.assertTrue(pem.startswith("-----BEGIN PUBLIC KEY-----"))
        self.assertTrue(pem.endswith("-----END PUBLIC KEY-----\n"))

    def test_jwk_to_pem_rsa(self):
        """Test JWK to PEM conversion for RSA keys."""
        sender = self.create_test_crvs_sender()

        # Valid RSA JWK test vector from RFC 7517 Appendix A.1
        jwk = {
            "kty": "RSA",
            "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw",
            "e": "AQAB",
        }

        pem = sender._jwk_to_pem(jwk)

        self.assertTrue(pem.startswith("-----BEGIN PUBLIC KEY-----"))
        self.assertTrue(pem.endswith("-----END PUBLIC KEY-----\n"))

    def test_jwk_to_pem_unsupported_type(self):
        """Test JWK to PEM conversion rejects unsupported key types."""
        sender = self.create_test_crvs_sender()

        jwk = {
            "kty": "EC",  # Unsupported
            "crv": "P-256",
        }

        with self.assertRaises(UserError) as context:
            sender._jwk_to_pem(jwk)

        self.assertIn("unsupported", str(context.exception).lower())

    def test_jwk_to_pem_missing_required_field(self):
        """Test JWK to PEM conversion handles missing required fields."""
        sender = self.create_test_crvs_sender()

        # Ed25519 JWK missing 'x' parameter
        jwk = {
            "kty": "OKP",
            "crv": "Ed25519",
            # 'x' is missing
        }

        with self.assertRaises(UserError) as context:
            sender._jwk_to_pem(jwk)

        self.assertIn("missing", str(context.exception).lower())

    def test_multiple_senders_with_different_algorithms(self):
        """Test creating senders with different algorithms."""
        sender1 = self.CRVSSender.create(
            {
                "name": "Ed25519 Sender",
                "sender_id": "crvs.ed25519.test",
                "algorithm": "ed25519",
            }
        )

        sender2 = self.CRVSSender.create(
            {
                "name": "RS256 Sender",
                "sender_id": "crvs.rs256.test",
                "algorithm": "rs256",
            }
        )

        self.assertEqual(sender1.algorithm, "ed25519")
        self.assertEqual(sender2.algorithm, "rs256")

    def test_sender_notes_field(self):
        """Test that notes field can be set and retrieved."""
        sender = self.create_test_crvs_sender()
        test_notes = "This is a test CRVS registry for integration testing."

        sender.write({"notes": test_notes})

        self.assertEqual(sender.notes, test_notes)

    def test_sender_ordering(self):
        """Test that senders are ordered by name."""
        self.CRVSSender.create(
            {
                "name": "Zebra CRVS",
                "sender_id": "crvs.zebra.test",
            }
        )
        self.CRVSSender.create(
            {
                "name": "Alpha CRVS",
                "sender_id": "crvs.alpha.test",
            }
        )

        senders = self.CRVSSender.search([("sender_id", "like", "crvs.%.test")])

        self.assertEqual(senders[0].name, "Alpha CRVS", "Should be ordered by name")
