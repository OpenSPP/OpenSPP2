# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import uuid
from unittest.mock import patch

from ..tools.oauth_exception import OpenSPPOAuthJWTException
from ..tools.rsa_encode_decode import (
    calculate_signature,
    get_private_key,
    get_public_key,
    verify_and_decode_signature,
)
from .common import Common


class TestOAuthErrors(Common):
    """Test error handling in OAuth JWT operations."""

    def test_get_private_key_not_configured(self):
        """Test that missing private key raises exception."""
        # Keys are cleared in setUpClass, so no set_parameters() call
        with self.assertRaises(OpenSPPOAuthJWTException):
            get_private_key(self.env)

    def test_get_public_key_not_configured(self):
        """Test that missing public key raises exception."""
        with self.assertRaises(OpenSPPOAuthJWTException):
            get_public_key(self.env)

    def test_verify_invalid_token(self):
        """Test that an invalid JWT token raises exception."""
        self.set_parameters()
        with self.assertRaises(OpenSPPOAuthJWTException):
            verify_and_decode_signature(
                env=self.env,
                access_token="invalid.jwt.token",
            )

    def test_verify_tampered_token(self):
        """Test that a tampered JWT token raises exception."""
        self.set_parameters()
        token = calculate_signature(
            env=self.env,
            header=None,
            payload={"data": "original"},
        )
        # Tamper with the token by modifying a character
        tampered = token[:-5] + "XXXXX"
        with self.assertRaises(OpenSPPOAuthJWTException):
            verify_and_decode_signature(
                env=self.env,
                access_token=tampered,
            )

    def test_exception_message(self):
        """Test that OpenSPPOAuthJWTException preserves message."""
        exc = OpenSPPOAuthJWTException("test error message")
        self.assertEqual(str(exc), "test error message")

    def test_exception_logs_error(self):
        """Test that OpenSPPOAuthJWTException logs the error message."""
        with patch("odoo.addons.spp_oauth.tools.oauth_exception._logger") as mock_logger:
            OpenSPPOAuthJWTException("something went wrong")
            mock_logger.error.assert_called_once_with("OAuth JWT error: %s", "something went wrong")

    def test_calculate_signature_with_header(self):
        """Test calculate_signature with explicit header dict."""
        self.set_parameters()
        token = calculate_signature(
            env=self.env,
            header={"alg": "RS256", "typ": "JWT"},
            payload={"test": str(uuid.uuid4())},
        )
        self.assertIsNotNone(token)
        decoded = verify_and_decode_signature(
            env=self.env,
            access_token=token,
        )
        self.assertIn("test", decoded)
