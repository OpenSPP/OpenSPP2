# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import uuid

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

    def test_exception_inherits_from_exception(self):
        """Test that OpenSPPOAuthJWTException is a proper Exception subclass."""
        exc = OpenSPPOAuthJWTException("something went wrong")
        self.assertIsInstance(exc, Exception)
        self.assertEqual(str(exc), "something went wrong")

    def test_verify_wrong_key_rejected(self):
        """Test that a token signed with a different private key is rejected."""
        import jwt as pyjwt
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.set_parameters()

        # Generate a different RSA key pair
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Sign a token with the wrong key
        wrong_token = pyjwt.encode(
            payload={"data": "forged"},
            key=other_pem,
            algorithm="RS256",
        )

        with self.assertRaises(OpenSPPOAuthJWTException):
            verify_and_decode_signature(env=self.env, access_token=wrong_token)

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
