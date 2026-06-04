# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Edge-case and error-branch tests for the DCI client compliance trigger controller.

Covers branches not exercised by test_trigger_controller.py:
- _disabled_response path (endpoints return 404 when compliance is off)
- _get_test_data_source fallback paths (search-by-name, then create)
- _create_test_data_source (no pre-existing data source)
- except branches in trigger_subscribe, trigger_unsubscribe, trigger_txn_status, health_check
- trigger_search with non-string query and a non-idtype-value query_type
"""

from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, tagged

COMPLIANCE_ENABLED_PARAM = "dci.client_compliance.enabled"
BEARER_TOKEN_PARAM = "dci.client_compliance.bearer_token"
MOCK_URL_PARAM = "dci.client_compliance.mock_registry_url"
DCICLIENT = "odoo.addons.spp_dci_client.services.client.DCIClient"

# Patch target used to suppress the test_enable shortcut in _compliance_enabled,
# forcing the code to read the config parameter instead.
_TOOLS_CONFIG_GET = "odoo.addons.spp_dci_client_compliance.controllers.trigger.tools.config.get"


@tagged("post_install", "-at_install")
class TestTriggerDisabledResponse(HttpCase):
    """Verify all endpoints return 404 when the compliance gate is closed.

    HttpCase is required because the controller methods call request.make_response.
    We suppress test_enable via a patch so the config-parameter check runs.
    """

    def setUp(self):
        super().setUp()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(COMPLIANCE_ENABLED_PARAM, "false")

    def _assert_disabled(self, response):
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("disabled", data["error"].lower())

    def _post_disabled(self, path, payload=None):
        import json

        return self.url_open(
            path,
            data=json.dumps(payload or {}),
            headers={"Content-Type": "application/json"},
        )

    def test_search_disabled_returns_404(self):
        with patch(_TOOLS_CONFIG_GET, return_value=False):
            resp = self._post_disabled("/dci/test/trigger/search", {"query": {}})
        self._assert_disabled(resp)

    def test_subscribe_disabled_returns_404(self):
        with patch(_TOOLS_CONFIG_GET, return_value=False):
            resp = self._post_disabled("/dci/test/trigger/subscribe", {})
        self._assert_disabled(resp)

    def test_unsubscribe_disabled_returns_404(self):
        with patch(_TOOLS_CONFIG_GET, return_value=False):
            resp = self._post_disabled("/dci/test/trigger/unsubscribe", {})
        self._assert_disabled(resp)

    def test_txn_status_disabled_returns_404(self):
        with patch(_TOOLS_CONFIG_GET, return_value=False):
            resp = self._post_disabled("/dci/test/trigger/txn_status", {})
        self._assert_disabled(resp)

    def test_health_check_disabled_returns_404(self):
        with patch(_TOOLS_CONFIG_GET, return_value=False):
            resp = self.url_open(
                "/dci/test/trigger/health",
                headers={"Content-Type": "application/json"},
            )
        self._assert_disabled(resp)


@tagged("post_install", "-at_install")
class TestGetTestDataSourceFallbackByName(HttpCase):
    """Cover the by-name fallback path in _get_test_data_source.

    Exercised via the /dci/test/trigger/health endpoint, which calls
    _get_test_data_source() before returning data-source info.
    """

    def setUp(self):
        super().setUp()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(COMPLIANCE_ENABLED_PARAM, "true")
        ICP.set_param(BEARER_TOKEN_PARAM, "tok-edge-cases")
        ICP.set_param(MOCK_URL_PARAM, "http://mock_registry:3335")

    def test_fallback_search_by_name(self):
        """When no is_compliance_test record exists, the by-name search is used."""
        # Create a record with name but without is_compliance_test.
        self.env["spp.dci.data.source"].sudo().create(
            {
                "name": "DCI Compliance Test",
                "code": "dci_compliance_name_only_edge",
                "base_url": "http://mock_registry:3335",
                "registry_type": "social",
                "our_sender_id": "spmis.compliance.test",
                "our_callback_uri": "http://openspp.dci.local:8069/dci/callback",
                "is_compliance_test": False,
                "state": "active",
                "auth_type": "bearer",
                "bearer_token": "tok-edge-cases",
            }
        )
        resp = self.url_open(
            "/dci/test/trigger/health",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["data_source"]["name"], "DCI Compliance Test")


@tagged("post_install", "-at_install")
class TestTriggerErrorBranches(HttpCase):
    """Cover except/error branches in trigger_subscribe, trigger_unsubscribe,
    trigger_txn_status, and health_check."""

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
                "code": "dci_compliance_err_branch",
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

    def test_subscribe_client_error_returns_500(self):
        """trigger_subscribe except branch: client raises -> 500 with error info."""
        with patch(f"{DCICLIENT}.subscribe", side_effect=RuntimeError("sub-fail")):
            resp = self._post("/dci/test/trigger/subscribe", {"event_type": "REGISTER"})
        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_type"], "RuntimeError")
        self.assertIn("sub-fail", data["error"])

    def test_unsubscribe_client_error_returns_500(self):
        """trigger_unsubscribe except branch: client raises -> 500 with error info."""
        with patch(f"{DCICLIENT}.unsubscribe", side_effect=ValueError("unsub-fail")):
            resp = self._post("/dci/test/trigger/unsubscribe", {"subscription_codes": ["S1"]})
        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_type"], "ValueError")

    def test_txn_status_client_error_returns_500(self):
        """trigger_txn_status except branch: client raises -> 500 with error info."""
        with patch(f"{DCICLIENT}.txn_status", side_effect=ConnectionError("txn-fail")):
            resp = self._post(
                "/dci/test/trigger/txn_status",
                {"transaction_id": "TX-ERR", "attribute_type": "transaction_id"},
            )
        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_type"], "ConnectionError")

    def test_health_check_error_returns_500(self):
        """health_check except branch: data source lookup raises -> 500."""
        with patch(
            "odoo.addons.spp_dci_client_compliance.controllers.trigger."
            "DCIClientTriggerController._get_test_data_source",
            side_effect=RuntimeError("health-fail"),
        ):
            resp = self.url_open(
                "/dci/test/trigger/health",
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(resp.status_code, 500)
        data = resp.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("health-fail", data["error"])

    def test_search_non_idtype_with_dict_query_uses_str(self):
        """trigger_search: query_type != 'idtype-value' with a dict query falls through to str()."""
        with patch(f"{DCICLIENT}.search_async", return_value={}) as m:
            resp = self._post(
                "/dci/test/trigger/search",
                {"query_type": "predicate", "query": {"key": "val"}},
            )
        self.assertEqual(resp.status_code, 200)
        _, kwargs = m.call_args
        # A dict is converted via str() when query_type is not idtype-value.
        self.assertEqual(kwargs["query_value"], str({"key": "val"}))


@tagged("post_install", "-at_install")
class TestCreateTestDataSource(TransactionCase):
    """Unit-test _create_test_data_source by swapping the module-level request proxy.

    HttpCase HTTP requests run in a read-only transaction and cannot INSERT.
    Patching the Werkzeug LocalProxy via unittest.mock.patch also fails because
    the patch context manager tries to inspect the proxy (which is unbound outside
    a request context). We instead directly replace the module attribute for the
    duration of the test, which avoids both issues.
    """

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_client_compliance.controllers.trigger import (
            DCIClientTriggerController,
        )

        self.controller = DCIClientTriggerController()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(BEARER_TOKEN_PARAM, "tok-create-test")
        ICP.set_param(MOCK_URL_PARAM, "http://mock_registry:3335")

    def test_create_test_data_source_creates_record(self):
        """_create_test_data_source inserts and returns a new data source record."""
        import odoo.addons.spp_dci_client_compliance.controllers.trigger as mod

        class FakeRequest:
            env = self.env

        original = mod.__dict__["request"]
        mod.request = FakeRequest()
        try:
            result = self.controller._create_test_data_source()
        finally:
            mod.request = original

        self.assertTrue(result)
        self.assertEqual(result.name, "DCI Compliance Test")
        self.assertTrue(result.is_compliance_test)
        self.assertEqual(result.bearer_token, "tok-create-test")
        self.assertEqual(result.base_url, "http://mock_registry:3335")
