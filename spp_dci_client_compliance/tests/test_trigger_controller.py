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
