# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for data-source HTTP paths: OAuth2 token, headers, test_connection."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import httpx

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

HTTPX_CLIENT = "odoo.addons.spp_dci_client.models.data_source.httpx.Client"


def _client_cm(response):
    """Build a mock usable as `with httpx.Client(...) as client:` whose
    .post/.get return ``response``."""
    client = MagicMock()
    client.post.return_value = response
    client.get.return_value = response
    cm = MagicMock()
    cm.__enter__.return_value = client
    cm.__exit__.return_value = False
    return cm


@tagged("post_install", "-at_install")
class TestDataSourceOAuth(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]

    def _oauth_ds(self, **overrides):
        vals = {
            "name": "OAuth DS",
            "code": "oauth_ds",
            "base_url": "https://dci.example.org/api",
            "auth_type": "oauth2",
            "our_sender_id": "openspp.test",
            "oauth2_token_url": "https://auth.example.org/token",
            "oauth2_client_id": "cid",
            "oauth2_client_secret": "secret",
        }
        vals.update(overrides)
        return self.DataSource.create(vals)

    def test_get_token_rejects_non_oauth2(self):
        ds = self.DataSource.create(
            {
                "name": "None DS",
                "code": "none_ds",
                "base_url": "https://dci.example.org/api",
                "auth_type": "none",
            }
        )
        with self.assertRaises(UserError):
            ds.get_oauth2_token()

    def test_get_token_uses_valid_cache(self):
        ds = self._oauth_ds()
        ds.sudo().write(
            {
                "_oauth2_access_token": "cached-tok",
                "_oauth2_token_expires_at": fields.Datetime.now() + timedelta(hours=1),
            }
        )
        # No HTTP mock needed; cached token returned without a request.
        self.assertEqual(ds.get_oauth2_token(), "cached-tok")

    def test_get_token_fetches_new_via_body(self):
        ds = self._oauth_ds()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"access_token": "fresh-tok", "expires_in": 1800}
        with patch(HTTPX_CLIENT, return_value=_client_cm(resp)):
            token = ds.get_oauth2_token()
        self.assertEqual(token, "fresh-tok")
        self.assertEqual(ds.sudo()._oauth2_access_token, "fresh-tok")

    def test_get_token_query_credential_location(self):
        ds = self._oauth_ds(oauth2_credential_location="query", oauth2_scope="read")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"access_token": "q-tok"}
        cm = _client_cm(resp)
        with patch(HTTPX_CLIENT, return_value=cm):
            self.assertEqual(ds.get_oauth2_token(), "q-tok")
        # query mode posts with params=, not data=
        client = cm.__enter__.return_value
        _, kwargs = client.post.call_args
        self.assertIn("params", kwargs)

    def test_get_token_missing_access_token_raises(self):
        ds = self._oauth_ds()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"no_token": "here"}
        with patch(HTTPX_CLIENT, return_value=_client_cm(resp)):
            with self.assertRaises(UserError):
                ds.get_oauth2_token()

    def test_get_token_http_status_error(self):
        ds = self._oauth_ds()
        err_resp = MagicMock(status_code=401, text="unauthorized")
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("401", request=MagicMock(), response=err_resp)
        with patch(HTTPX_CLIENT, return_value=_client_cm(resp)):
            with self.assertRaises(UserError) as ctx:
                ds.get_oauth2_token()
        self.assertIn("Authentication failed", str(ctx.exception))

    def test_get_token_request_error_timeout(self):
        ds = self._oauth_ds()
        cm = MagicMock()
        cm.__enter__.return_value.post.side_effect = httpx.RequestError("Connection timed out")
        cm.__exit__.return_value = False
        with patch(HTTPX_CLIENT, return_value=cm):
            with self.assertRaises(UserError) as ctx:
                ds.get_oauth2_token()
        self.assertIn("timed out", str(ctx.exception).lower())

    # --- get_headers ---------------------------------------------------------

    def test_get_headers_oauth2(self):
        ds = self._oauth_ds()
        with patch.object(type(ds), "get_oauth2_token", return_value="abc"):
            headers = ds.get_headers()
        self.assertEqual(headers["Authorization"], "Bearer abc")

    def test_get_headers_bearer(self):
        ds = self.DataSource.create(
            {
                "name": "Bearer DS",
                "code": "bearer_ds",
                "base_url": "https://dci.example.org/api",
                "auth_type": "bearer",
                "our_sender_id": "openspp.test",
                "bearer_token": "btok",
            }
        )
        self.assertEqual(ds.get_headers()["Authorization"], "Bearer btok")

    # --- test_connection -----------------------------------------------------

    def test_connection_success_activates(self):
        ds = self.DataSource.create(
            {
                "name": "Conn DS",
                "code": "conn_ds",
                "base_url": "https://dci.example.org/api",
                "auth_type": "none",
            }
        )
        resp = MagicMock(status_code=200)
        with patch(HTTPX_CLIENT, return_value=_client_cm(resp)):
            result = ds.test_connection()
        self.assertEqual(result["params"]["type"], "success")
        self.assertEqual(ds.state, "active")
        self.assertTrue(ds.last_test_date)

    def test_connection_unauthorized_sets_error_state(self):
        """A 401 from the ping endpoint means the credentials were rejected;
        Test Connection must surface this as a failure, not a success."""
        ds = self.DataSource.create(
            {
                "name": "Conn Auth DS",
                "code": "conn_auth_ds",
                "base_url": "https://dci.example.org/api",
                "auth_type": "none",
            }
        )
        resp = MagicMock(status_code=401, text="unauthorized", request=MagicMock())
        with patch(HTTPX_CLIENT, return_value=_client_cm(resp)):
            result = ds.test_connection()
        self.assertEqual(result["params"]["type"], "danger")
        self.assertEqual(ds.state, "error")
        self.assertTrue(ds.last_error)

    def test_connection_no_ping_endpoint_warns_but_reachable(self):
        """A 404/405 means the server is reachable but has no ping endpoint, so
        credentials are unverified: reachable (active) with a warning."""
        ds = self.DataSource.create(
            {
                "name": "Conn NoPing DS",
                "code": "conn_noping_ds",
                "base_url": "https://dci.example.org/api",
                "auth_type": "none",
            }
        )
        resp = MagicMock(status_code=404)
        with patch(HTTPX_CLIENT, return_value=_client_cm(resp)):
            result = ds.test_connection()
        self.assertEqual(result["params"]["type"], "warning")
        self.assertEqual(ds.state, "active")

    def test_connection_http_error_sets_error_state(self):
        ds = self.DataSource.create(
            {
                "name": "Conn Err DS",
                "code": "conn_err_ds",
                "base_url": "https://dci.example.org/api",
                "auth_type": "none",
            }
        )
        resp = MagicMock(status_code=500, text="boom", request=MagicMock())
        with patch(HTTPX_CLIENT, return_value=_client_cm(resp)):
            result = ds.test_connection()
        self.assertEqual(result["params"]["type"], "danger")
        self.assertEqual(ds.state, "error")
        self.assertTrue(ds.last_error)

    def test_connection_request_error_sets_error_state(self):
        ds = self.DataSource.create(
            {
                "name": "Conn Net DS",
                "code": "conn_net_ds",
                "base_url": "https://dci.example.org/api",
                "auth_type": "none",
            }
        )
        cm = MagicMock()
        cm.__enter__.return_value.get.side_effect = httpx.RequestError("SSL certificate problem")
        cm.__exit__.return_value = False
        with patch(HTTPX_CLIENT, return_value=cm):
            result = ds.test_connection()
        self.assertEqual(ds.state, "error")
        self.assertEqual(result["params"]["type"], "danger")
