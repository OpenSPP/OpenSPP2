# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for RS256 JWT authentication via the bridge module."""

from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from odoo.tests import tagged

from fastapi import HTTPException

from .common import JWT_AUDIENCE, JWT_ISSUER, OAuthBridgeTestCase


@tagged("post_install", "-at_install")
class TestRS256Authentication(OAuthBridgeTestCase):
    """Test RS256 token verification through the bridge auth function."""

    def test_rs256_valid_token(self):
        """RS256 token with valid signature and correct claims is accepted."""
        from ..middleware.auth_rs256 import _validate_rs256_token_with_issuer

        token = self.generate_rs256_token()
        payload, issuer_rec = _validate_rs256_token_with_issuer(self.env, token)

        self.assertEqual(payload["client_id"], self.api_client.client_id)
        self.assertEqual(payload["iss"], JWT_ISSUER)
        self.assertEqual(payload["aud"], JWT_AUDIENCE)
        self.assertFalse(issuer_rec, "internal path should return no issuer record")

    def test_rs256_wrong_audience(self):
        """RS256 token with wrong audience is rejected."""
        from ..middleware.auth_rs256 import _validate_rs256_token_with_issuer

        token = self.generate_rs256_token(payload_overrides={"aud": "wrong-audience"})

        with self.assertRaises(HTTPException) as ctx:
            _validate_rs256_token_with_issuer(self.env, token)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rs256_wrong_issuer(self):
        """RS256 token with wrong issuer is rejected."""
        from ..middleware.auth_rs256 import _validate_rs256_token_with_issuer

        token = self.generate_rs256_token(payload_overrides={"iss": "wrong-issuer"})

        with self.assertRaises(HTTPException) as ctx:
            _validate_rs256_token_with_issuer(self.env, token)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rs256_expired_token(self):
        """RS256 token that has expired is rejected."""
        from ..middleware.auth_rs256 import _validate_rs256_token_with_issuer

        expired_time = datetime.now(tz=UTC) - timedelta(hours=1)
        token = self.generate_rs256_token(
            payload_overrides={
                "exp": expired_time,
                "iat": expired_time - timedelta(hours=1),
            }
        )

        with self.assertRaises(HTTPException) as ctx:
            _validate_rs256_token_with_issuer(self.env, token)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_rs256_wrong_key(self):
        """RS256 token signed with a different private key is rejected."""
        from ..middleware.auth_rs256 import _validate_rs256_token_with_issuer

        # Generate a different RSA key pair
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        token = self.generate_rs256_token(private_key=other_pem)

        with self.assertRaises(HTTPException) as ctx:
            _validate_rs256_token_with_issuer(self.env, token)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rs256_keys_not_configured(self):
        """RS256 token is rejected (not 500) when RSA keys are not configured."""
        from ..middleware.auth_rs256 import _validate_rs256_token_with_issuer

        # Clear RSA public key
        self.env["ir.config_parameter"].sudo().set_param("spp_oauth.oauth_public_key", False)

        token = self.generate_rs256_token()

        with self.assertRaises(HTTPException) as ctx:
            _validate_rs256_token_with_issuer(self.env, token)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("not available", ctx.exception.detail.lower())

    def test_rs256_malformed_token(self):
        """Malformed token string is rejected."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        creds = self.make_credentials("not.a.valid.jwt")

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rs256_missing_client_id(self):
        """RS256 token without client_id claim is rejected."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        # Generate token without client_id
        payload = {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "exp": datetime.now(tz=UTC) + timedelta(hours=1),
            "iat": datetime.now(tz=UTC),
        }
        token = jwt.encode(payload, self.rsa_private_key_pem, algorithm="RS256")
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("client_id", ctx.exception.detail.lower())

    def test_rs256_inactive_client(self):
        """RS256 token for an inactive client is rejected."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        # Deactivate the client (restore on cleanup to avoid breaking other tests)
        self.api_client.active = False
        self.addCleanup(setattr, self.api_client, "active", True)

        token = self.generate_rs256_token()
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_missing_credentials(self):
        """Missing Authorization header returns 401."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(None, self.env)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Missing", ctx.exception.detail)

    def test_header_routing_rs256(self):
        """Token with alg=RS256 header is routed to RS256 verification."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self.generate_rs256_token()
        creds = self.make_credentials(token)

        client = get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(client.client_id, self.api_client.client_id)

    def test_unsupported_algorithm_rejected(self):
        """Token with unsupported algorithm (not RS256/HS256) is rejected."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        # Create a token with HS384 algorithm (unsupported by our bridge)
        payload = self._build_jwt_payload()
        secret = "a-secret-key-long-enough-for-hs384-testing-only!!"
        token = jwt.encode(payload, secret, algorithm="HS384")
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Unsupported token algorithm", ctx.exception.detail)

    def test_rs256_client_not_found(self):
        """RS256 token with valid signature but non-existent client_id is rejected."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self.generate_rs256_token(
            payload_overrides={"client_id": "non-existent-client-id", "sub": "non-existent-client-id"}
        )
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("not found", ctx.exception.detail.lower())

    def test_internal_rs256_cannot_resolve_issuer_linked_client(self):
        """An internal RS256 token cannot authenticate as a client linked
        to an external Trusted OAuth Issuer."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_pem = (
            key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )
        issuer_rec = self.env["spp.oauth.issuer"].create(
            {
                "name": "RS256 Regression Issuer",
                "issuer": "https://idp.example.com/realms/rs256-reg",
                "audience": "openspp-ext",
                "key_source": "public_key",
                "public_key": public_pem,
            }
        )
        linked_client = self._make_api_client(
            "RS256 Regression Linked Client",
            oauth_issuer_id=issuer_rec.id,
        )

        # Internal-issuer RS256 token claiming the linked client's id must be rejected.
        token = self.generate_rs256_token(
            payload_overrides={"client_id": linked_client.client_id, "sub": linked_client.client_id}
        )
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("not found", ctx.exception.detail.lower())
