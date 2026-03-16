# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests ensuring HS256 authentication still works through the bridge."""

from datetime import UTC, datetime, timedelta

import jwt

from odoo.tests import tagged

from fastapi import HTTPException

from .common import JWT_AUDIENCE, JWT_ISSUER, OAuthBridgeTestCase


@tagged("post_install", "-at_install")
class TestHS256Regression(OAuthBridgeTestCase):
    """Verify that the bridge module does not break HS256 authentication."""

    def test_hs256_token_still_works(self):
        """HS256 token is still accepted after bridge module is installed."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self.generate_hs256_token()
        creds = self.make_credentials(token)

        client = get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(client.client_id, self.api_client.client_id)

    def test_hs256_expired_token_rejected(self):
        """Expired HS256 token is still rejected through the bridge."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        expired_time = datetime.now(tz=UTC) - timedelta(hours=1)
        token = self.generate_hs256_token(
            payload_overrides={
                "exp": expired_time,
                "iat": expired_time - timedelta(hours=1),
            }
        )
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_hs256_invalid_secret_rejected(self):
        """HS256 token signed with wrong secret is rejected through the bridge."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        # Sign with a different secret
        payload = {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "exp": datetime.now(tz=UTC) + timedelta(hours=1),
            "iat": datetime.now(tz=UTC),
            "client_id": self.api_client.client_id,
        }
        wrong_secret = "wrong-secret-that-is-at-least-32-characters-long!!"
        token = jwt.encode(payload, wrong_secret, algorithm="HS256")
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_dependency_override_applied(self):
        """Verify the bridge override is set up in the endpoint model."""
        from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

        endpoint = self.env["fastapi.endpoint"].search([("app", "=", "api_v2")], limit=1)
        if endpoint:
            overrides = endpoint._get_app_dependencies_overrides()
            self.assertIn(
                get_authenticated_client,
                overrides,
                "get_authenticated_client should be in dependency overrides",
            )

            from ..middleware.auth_rs256 import get_authenticated_client_rs256

            self.assertEqual(
                overrides[get_authenticated_client],
                get_authenticated_client_rs256,
                "Override should point to the RS256 bridge function",
            )
