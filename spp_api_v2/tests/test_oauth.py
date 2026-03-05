# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for OAuth endpoints"""

import base64
import json
from urllib.parse import urlencode

from ..middleware.rate_limit import get_rate_limiter
from .common import ApiV2HttpTestCase


class TestOAuthEndpoint(ApiV2HttpTestCase):
    """Test OAuth token endpoint"""

    def setUp(self):
        super().setUp()
        # Clear rate limiter before each test since auth endpoint has strict limits
        # (5 per minute) and tests run quickly from same IP
        get_rate_limiter().clear()
        self.url = "/api/v2/spp/oauth/token"
        self.client = self.create_api_client(
            name="OAuth Test Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "group", "action": "search"},
            ],
        )

    def test_token_generation_success(self):
        """Valid credentials return access token"""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("access_token", data)
        self.assertIn("token_type", data)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertIn("expires_in", data)
        self.assertEqual(data["expires_in"], 86400)  # 24 hours (default)
        self.assertIn("scope", data)
        self.assertIn("individual:read", data["scope"])
        self.assertIn("group:search", data["scope"])

    def test_token_jwt_payload(self):
        """JWT token contains correct payload"""
        import jwt

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        data = json.loads(response.content)
        token = data["access_token"]

        # Decode token with audience validation
        secret = self.env["ir.config_parameter"].sudo().get_param("spp_api_v2.jwt_secret")
        decoded = jwt.decode(token, secret, algorithms=["HS256"], audience="openspp")

        self.assertEqual(decoded["iss"], "openspp-api-v2")
        self.assertEqual(decoded["sub"], self.client.client_id)
        self.assertEqual(decoded["aud"], "openspp")
        self.assertEqual(decoded["client_id"], self.client.client_id)
        # SECURITY: partner_id (database ID) should NOT be in JWT token
        # The auth middleware fetches the full api_client from DB using client_id
        self.assertNotIn("partner_id", decoded)
        self.assertIn("individual:read", decoded["scopes"])
        self.assertIn("group:search", decoded["scopes"])
        self.assertIn("exp", decoded)
        self.assertIn("iat", decoded)

    def test_invalid_grant_type(self):
        """Invalid grant_type returns 400"""
        payload = {
            "grant_type": "authorization_code",  # Not supported
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("detail", data)
        self.assertIn("client_credentials", data["detail"])

    def test_invalid_client_id(self):
        """Unknown client_id returns 401"""
        payload = {
            "grant_type": "client_credentials",
            "client_id": "unknown_client",
            "client_secret": "any-secret",
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertIn("detail", data)
        self.assertIn("Invalid", data["detail"])

    def test_invalid_client_secret(self):
        """Wrong client_secret returns 401"""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client.client_id,
            "client_secret": "wrong-secret",
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)

    def test_inactive_client_rejected(self):
        """Inactive client cannot get token"""
        self.client.active = False

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)

    def test_missing_jwt_secret_error(self):
        """Missing JWT secret returns 500"""
        # Remove JWT secret
        self.env["ir.config_parameter"].sudo().set_param("spp_api_v2.jwt_secret", "")

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 500)

    def test_client_request_count_incremented(self):
        """Successful authentication increments request count"""
        initial_count = self.client.request_count

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)

        # Refresh client record
        self.client.invalidate_recordset()
        self.assertGreater(self.client.request_count, initial_count)

    def test_client_last_used_date_updated(self):
        """Successful authentication updates last_used_date"""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)

        # Refresh client record
        self.client.invalidate_recordset()
        self.assertTrue(self.client.last_used_date)

    def test_token_generation_basic_auth(self):
        """HTTP Basic Auth header returns access token"""
        credentials = base64.b64encode(f"{self.client.client_id}:{self.client.client_secret}".encode()).decode("utf-8")

        response = self.url_open(
            self.url,
            data="",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {credentials}",
            },
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertIn("expires_in", data)
        self.assertIn("scope", data)

    def test_token_generation_form_encoded(self):
        """Form-encoded body (application/x-www-form-urlencoded) returns access token"""
        body = urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.client.client_id,
                "client_secret": self.client.client_secret,
            }
        )

        response = self.url_open(
            self.url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertIn("expires_in", data)
        self.assertIn("scope", data)
        self.assertIn("individual:read", data["scope"])
        self.assertIn("group:search", data["scope"])

    def test_token_no_scopes(self):
        """Client with no scopes still gets token but empty scope string"""
        # Create client without scopes
        no_scope_client = self.create_api_client(
            name="No Scope Client",
            scopes=[],
        )

        payload = {
            "grant_type": "client_credentials",
            "client_id": no_scope_client.client_id,
            "client_secret": no_scope_client.client_secret,
        }

        response = self.url_open(
            self.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["scope"], "")
