# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI client compliance trigger controller."""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestTriggerController(HttpCase):
    """Test the compliance trigger controller endpoints."""

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
        # These should return 500 (no mock registry) not 404 (not found)
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
            # Should not be 404 - the endpoint exists
            self.assertNotEqual(
                response.status_code,
                404,
                f"Endpoint {endpoint} should exist",
            )
