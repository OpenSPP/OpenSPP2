# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI client compliance trigger controller."""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged

COMPLIANCE_ENABLED_PARAM = "dci.client_compliance.enabled"
BEARER_TOKEN_PARAM = "dci.client_compliance.bearer_token"


@tagged("post_install", "-at_install")
class TestTriggerController(HttpCase):
    """End-to-end checks for the compliance trigger endpoints.

    Endpoints are intentionally gated: they must be explicitly enabled via
    ``dci.client_compliance.enabled`` and require a bearer token to be set
    via ``dci.client_compliance.bearer_token``. Tests run under
    ``test_enable`` so the gate is satisfied; the bearer token is set in
    setUp.
    """

    def setUp(self):
        super().setUp()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(COMPLIANCE_ENABLED_PARAM, "true")
        ICP.set_param(BEARER_TOKEN_PARAM, "test-bearer-token-from-config")

        # Pre-create the data source in this writable transaction so the
        # controller's HTTP request (which runs read-only under HttpCase)
        # finds it via search and does not need to INSERT.
        self.env["spp.dci.data.source"].sudo().create(
            {
                "name": "DCI Compliance Test",
                "code": "dci_compliance_test_setup",
                "base_url": "http://mock_registry:3335",
                "registry_type": "social",
                "our_sender_id": "spmis.compliance.test",
                "our_callback_uri": "http://openspp.dci.local:8069/dci/callback",
                "is_compliance_test": True,
                "state": "active",
                "auth_type": "bearer",
                "bearer_token": "test-bearer-token-from-config",
            }
        )

    def test_health_check_endpoint(self):
        """Test that health check endpoint responds."""
        response = self.url_open(
            "/dci/test/trigger/health",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("data_source", data)

    def test_trigger_endpoints_exist(self):
        """Test that trigger endpoints are registered."""
        endpoints = [
            "/dci/test/trigger/search",
            "/dci/test/trigger/subscribe",
            "/dci/test/trigger/unsubscribe",
            "/dci/test/trigger/txn_status",
        ]

        for endpoint in endpoints:
            response = self.url_open(
                endpoint,
                data="{}",
                headers={"Content-Type": "application/json"},
            )
            self.assertNotEqual(
                response.status_code,
                404,
                f"Endpoint {endpoint} should exist",
            )


@tagged("post_install", "-at_install")
class TestTriggerControllerSafeguards(TransactionCase):
    """Unit tests for the compliance-gating safeguards.

    These exercise the helpers directly because ``test_enable`` is always
    True under HttpCase, which would mask the production fail-closed
    behaviour.
    """

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_client_compliance.controllers.trigger import (
            DCIClientTriggerController,
        )

        self.controller = DCIClientTriggerController()
        self.ICP = self.env["ir.config_parameter"].sudo()

    def test_compliance_disabled_by_default(self):
        """Without test_enable and without the param, gate must return False."""
        self.ICP.set_param(COMPLIANCE_ENABLED_PARAM, "false")
        with patch(
            "odoo.addons.spp_dci_client_compliance.controllers.trigger.tools.config.get",
            return_value=False,
        ):
            self.assertFalse(self.controller._compliance_enabled(self.env))

    def test_compliance_enabled_via_param(self):
        """Param 'true' must enable the gate even without test_enable."""
        self.ICP.set_param(COMPLIANCE_ENABLED_PARAM, "true")
        with patch(
            "odoo.addons.spp_dci_client_compliance.controllers.trigger.tools.config.get",
            return_value=False,
        ):
            self.assertTrue(self.controller._compliance_enabled(self.env))

    def test_compliance_enabled_via_test_mode(self):
        """test_enable must enable the gate even when the param is false."""
        self.ICP.set_param(COMPLIANCE_ENABLED_PARAM, "false")
        with patch(
            "odoo.addons.spp_dci_client_compliance.controllers.trigger.tools.config.get",
            return_value=True,
        ):
            self.assertTrue(self.controller._compliance_enabled(self.env))

    def test_bearer_token_required(self):
        """Creating a test data source without a configured bearer token raises."""
        self.ICP.set_param(BEARER_TOKEN_PARAM, "")
        with self.assertRaises(UserError):
            self.controller._get_compliance_bearer_token(self.env)

    def test_bearer_token_returned_when_set(self):
        """Configured bearer token is returned verbatim."""
        self.ICP.set_param(BEARER_TOKEN_PARAM, "my-secret-token")
        token = self.controller._get_compliance_bearer_token(self.env)
        self.assertEqual(token, "my-secret-token")


DCICLIENT = "odoo.addons.spp_dci_client.services.client.DCIClient"


@tagged("post_install", "-at_install")
class TestTriggerControllerSuccessPaths(HttpCase):
    """Exercise the success bodies of each trigger endpoint with DCIClient
    mocked, so the routing/query-building/response logic is covered without
    a live mock registry."""

    def setUp(self):
        super().setUp()
        import json

        self.json = json
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(COMPLIANCE_ENABLED_PARAM, "true")
        ICP.set_param(BEARER_TOKEN_PARAM, "test-bearer-token-from-config")
        self.env["spp.dci.data.source"].sudo().create(
            {
                "name": "DCI Compliance Test",
                "code": "dci_compliance_test_setup",
                "base_url": "http://mock_registry:3335",
                "registry_type": "social",
                "our_sender_id": "spmis.compliance.test",
                "our_callback_uri": "http://openspp.dci.local:8069/dci/callback",
                "is_compliance_test": True,
                "state": "active",
                "auth_type": "bearer",
                "bearer_token": "test-bearer-token-from-config",
            }
        )

    def _post(self, path, payload):
        return self.url_open(
            path,
            data=self.json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_search_success_with_dict_query(self):
        with patch(f"{DCICLIENT}.search_async", return_value={"transaction_id": "T1"}) as m:
            resp = self._post(
                "/dci/test/trigger/search",
                {
                    "query_type": "idtype-value",
                    "query": {"type": "UIN", "value": "X-1"},
                    "record_type": "PERSON",
                },
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["result"], {"transaction_id": "T1"})
        # query_value must have been built as "UIN:X-1"
        _, kwargs = m.call_args
        self.assertEqual(kwargs["query_value"], "UIN:X-1")

    def test_search_success_with_string_query(self):
        """idtype-value with a non-dict query falls through to str(query)."""
        with patch(f"{DCICLIENT}.search_async", return_value={}) as m:
            resp = self._post(
                "/dci/test/trigger/search",
                {"query_type": "idtype-value", "query": "RAW-VALUE"},
            )
        self.assertEqual(resp.status_code, 200)
        _, kwargs = m.call_args
        self.assertEqual(kwargs["query_value"], "RAW-VALUE")

    def test_search_success_with_non_idtype_query(self):
        """A different query_type uses the query verbatim when it is a str."""
        with patch(f"{DCICLIENT}.search_async", return_value={}) as m:
            resp = self._post(
                "/dci/test/trigger/search",
                {"query_type": "predicate", "query": "age > 18"},
            )
        self.assertEqual(resp.status_code, 200)
        _, kwargs = m.call_args
        self.assertEqual(kwargs["query_value"], "age > 18")

    def test_subscribe_success(self):
        with patch(f"{DCICLIENT}.subscribe", return_value={"sub": "ok"}) as m:
            resp = self._post(
                "/dci/test/trigger/subscribe",
                {"event_type": "REGISTER", "filter": {"type": "UIN"}},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        _, kwargs = m.call_args
        self.assertEqual(kwargs["event_type"], "REGISTER")

    def test_unsubscribe_success_with_list(self):
        with patch(f"{DCICLIENT}.unsubscribe", return_value={"ok": True}) as m:
            resp = self._post(
                "/dci/test/trigger/unsubscribe",
                {"subscription_codes": ["S1", "S2"]},
            )
        self.assertEqual(resp.status_code, 200)
        _, kwargs = m.call_args
        self.assertEqual(kwargs["subscription_codes"], ["S1", "S2"])

    def test_unsubscribe_coerces_string_code_to_list(self):
        with patch(f"{DCICLIENT}.unsubscribe", return_value={}) as m:
            resp = self._post(
                "/dci/test/trigger/unsubscribe",
                {"subscription_codes": "S-ONLY"},
            )
        self.assertEqual(resp.status_code, 200)
        _, kwargs = m.call_args
        self.assertEqual(kwargs["subscription_codes"], ["S-ONLY"])

    def test_txn_status_success(self):
        with patch(f"{DCICLIENT}.txn_status", return_value={"state": "done"}) as m:
            resp = self._post(
                "/dci/test/trigger/txn_status",
                {"transaction_id": "TX-9", "attribute_type": "transaction_id"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        _, kwargs = m.call_args
        self.assertEqual(kwargs["attribute_value"], "TX-9")
        self.assertEqual(kwargs["attribute_type"], "transaction_id")

    def test_search_client_error_returns_500(self):
        with patch(f"{DCICLIENT}.search_async", side_effect=RuntimeError("boom")):
            resp = self._post("/dci/test/trigger/search", {"query": {"value": "x"}})
        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_type"], "RuntimeError")
