# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCIClient convenience search methods + _parse_query.

These wrap the core search/_make_request plumbing; _make_request is
mocked so we exercise the query/envelope construction without HTTP.
"""

from unittest.mock import MagicMock, patch

import httpx

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..services.client import DCIClient


@tagged("post_install", "-at_install")
class TestClientConvenience(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.ds = cls.DataSource.create(
            {
                "name": "Conv CRVS",
                "code": "conv_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "our_sender_id": "openspp.example.org",
                "our_callback_uri": "https://openspp.example.org/callback",
                "registry_type": "ns:org:RegistryType:Civil",
            }
        )

    def setUp(self):
        super().setUp()
        self.client = DCIClient(self.ds, self.env)

    # --- _parse_query --------------------------------------------------------

    def test_parse_query_idtype_value(self):
        result = self.client._parse_query("idtype-value", "UIN:12345")
        self.assertEqual(result, {"type": "UIN", "value": "12345"})

    def test_parse_query_idtype_value_missing_colon_raises(self):
        with self.assertRaises(ValidationError):
            self.client._parse_query("idtype-value", "no-colon-here")

    def test_parse_query_predicate_passthrough(self):
        self.assertEqual(self.client._parse_query("predicate", "r.age >= 18"), "r.age >= 18")

    def test_parse_query_other_passthrough(self):
        self.assertEqual(self.client._parse_query("graphql", "{ x }"), "{ x }")

    # --- convenience search methods (mock _make_request) ---------------------

    def test_search_by_id_sync(self):
        with patch.object(DCIClient, "_make_request", return_value={"ok": 1}) as m:
            self.client.search_by_id("UIN", "X-1")
        m.assert_called_once()

    def test_search_by_id_async_uses_async_endpoint(self):
        with patch.object(DCIClient, "_make_request", return_value={"ok": 1}) as m:
            self.client.search_by_id("UIN", "X-1", async_mode=True)
        endpoint = m.call_args[0][0]
        self.assertIn("search", endpoint)

    def test_search_by_id_opencrvs(self):
        with patch.object(DCIClient, "_make_request", return_value={"ok": 1}) as m:
            self.client.search_by_id_opencrvs("BRN", "B-1", event_type="birth")
        m.assert_called_once()

    def test_search_by_id_opencrvs_async(self):
        with patch.object(DCIClient, "_make_request", return_value={"ok": 1}) as m:
            self.client.search_by_id_opencrvs("BRN", "B-1", async_mode=True)
        m.assert_called_once()

    def test_search_by_predicate(self):
        with patch.object(DCIClient, "_make_request", return_value={"ok": 1}) as m:
            self.client.search_by_predicate("r.age >= 18")
        m.assert_called_once()

    def test_search_by_date_range_dci_format(self):
        with patch.object(DCIClient, "_make_request", return_value={"ok": 1}) as m:
            self.client.search_by_date_range("2024-01-01", "2024-12-31", event_type="BIRTH")
        m.assert_called_once()

    def test_search_by_date_range_async(self):
        with patch.object(DCIClient, "_make_request", return_value={"ok": 1}) as m:
            self.client.search_by_date_range("2024-01-01", "2024-12-31", async_mode=True)
        endpoint = m.call_args[0][0]
        self.assertIn("search", endpoint)

    def test_search_by_date_range_opencrvs_format(self):
        with patch.object(DCIClient, "_make_request", return_value={"ok": 1}) as m:
            self.client.search_by_date_range("2024-01-01", "2024-12-31", event_type="birth", use_opencrvs_format=True)
        m.assert_called_once()

    # --- receiver / registry-type resolution ---------------------------------

    def test_get_registry_type_from_data_source(self):
        self.assertEqual(self.client._get_registry_type(), "ns:org:RegistryType:Civil")

    def test_get_receiver_id_returns_a_value(self):
        # Should not raise and returns a string-ish receiver id.
        self.assertIsNotNone(self.client._get_receiver_id())


@tagged("post_install", "-at_install")
class TestClientSigningAndHelpers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.SigningKey = cls.env["spp.dci.signing.key"]
        cls.ds = cls.DataSource.create(
            {
                "name": "Sign CRVS",
                "code": "sign_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "our_sender_id": "openspp.example.org",
                "registry_type": "ns:org:RegistryType:Civil",
            }
        )

    def setUp(self):
        super().setUp()
        self.client = DCIClient(self.ds, self.env)

    # --- _sign_request -------------------------------------------------------

    def test_sign_request_unsigned_when_no_key(self):
        envelope = self.client._sign_request({"action": "search"}, {"q": 1})
        self.assertEqual(envelope["signature"], "")
        self.assertEqual(envelope["header"], {"action": "search"})
        self.assertEqual(envelope["message"], {"q": 1})

    def test_sign_request_with_active_key(self):
        key = self.SigningKey.create({"name": "Sign Key", "key_id": "sign-1", "algorithm": "ed25519"})
        key.action_generate_key()
        key.action_activate()
        self.ds.signing_key_id = key.id
        envelope = self.client._sign_request({"action": "search"}, {"q": 1})
        self.assertTrue(envelope["signature"])

    def test_sign_request_inactive_key_raises(self):
        key = self.SigningKey.create({"name": "Draft Key", "key_id": "draft-sign", "algorithm": "ed25519"})
        key.action_generate_key()  # left in draft
        self.ds.signing_key_id = key.id
        with self.assertRaises(UserError):
            self.client._sign_request({"action": "search"}, {"q": 1})

    # --- _copy_envelope_for_log ----------------------------------------------

    def test_copy_envelope_for_log_returns_copy(self):
        env_in = {"signature": "sig", "header": {}, "message": {}}
        out = self.client._copy_envelope_for_log(env_in)
        self.assertEqual(out, env_in)
        self.assertIsNot(out, env_in)

    def test_copy_envelope_for_log_none(self):
        self.assertIsNone(self.client._copy_envelope_for_log(None))

    # --- _get_receiver_id ----------------------------------------------------

    def test_get_receiver_id_falls_back_to_base_url(self):
        # No explicit receiver_id field value -> derives from base_url.
        self.assertTrue(self.client._get_receiver_id())


HTTPX = "odoo.addons.spp_dci_client.services.client.httpx.Client"


def _cm(response=None, post_side_effect=None):
    client = MagicMock()
    if post_side_effect is not None:
        client.post.side_effect = post_side_effect
    else:
        client.post.return_value = response
    cm = MagicMock()
    cm.__enter__.return_value = client
    cm.__exit__.return_value = False
    return cm


@tagged("post_install", "-at_install")
class TestClientMakeRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.ds = cls.DataSource.create(
            {
                "name": "MR CRVS",
                "code": "mr_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "our_sender_id": "openspp.example.org",
                "registry_type": "ns:org:RegistryType:Civil",
            }
        )

    def setUp(self):
        super().setUp()
        self.client = DCIClient(self.ds, self.env)
        self.envelope = {
            "signature": "",
            "header": {"action": "search", "message_id": "m-1"},
            "message": {"q": 1},
        }
        # Avoid auth HTTP in get_headers
        p = patch.object(type(self.ds), "_get_headers", return_value={"Content-Type": "application/json"})
        p.start()
        self.addCleanup(p.stop)

    def test_make_request_success(self):
        resp = MagicMock(status_code=200)
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"ok": True}
        with patch(HTTPX, return_value=_cm(resp)):
            result = self.client._make_request("/sync/search", self.envelope)
        self.assertEqual(result, {"ok": True})

    def test_make_request_http_status_error(self):
        err_resp = MagicMock(status_code=500, text="boom")
        err_resp.json.return_value = {"header": {"status_reason_message": "bad"}}
        resp = MagicMock(status_code=500)
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=MagicMock(), response=err_resp)
        with patch(HTTPX, return_value=_cm(resp)):
            with self.assertRaises(UserError):
                self.client._make_request("/sync/search", self.envelope)

    def test_make_request_connection_error(self):
        with patch(HTTPX, return_value=_cm(post_side_effect=httpx.RequestError("Connection timed out"))):
            with self.assertRaises(UserError) as ctx:
                self.client._make_request("/sync/search", self.envelope)
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_make_request_oauth_401_retry(self):
        """A 401 on an oauth2 source clears the token cache and retries once
        with _retry_auth=False; the retry's 401 then raises."""
        oauth_ds = self.DataSource.create(
            {
                "name": "MR OAuth",
                "code": "mr_oauth",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "oauth2",
                "our_sender_id": "openspp.example.org",
                "oauth2_token_url": "https://auth.example.org/token",
                "oauth2_client_id": "cid",
                "oauth2_client_secret": "secret",
            }
        )
        # get_headers is patched on the class in setUp, so no token HTTP.
        client = DCIClient(oauth_ds, self.env)
        resp = MagicMock(status_code=401)
        resp.json.return_value = {"error": "unauthorized"}
        # raise_for_status raises on the retry (status 401)
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock(status_code=401, text="unauthorized")
        )
        with patch(HTTPX, return_value=_cm(resp)), patch.object(type(oauth_ds), "clear_oauth2_token_cache") as clear:
            with self.assertRaises(UserError):
                client._make_request("/sync/search", self.envelope)
        clear.assert_called_once()
