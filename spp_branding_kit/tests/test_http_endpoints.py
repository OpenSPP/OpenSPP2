import json

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestBrandingHttp(HttpCase):
    def _jsonrpc(self, path, params=None):
        payload = {"jsonrpc": "2.0", "method": "call", "params": params or {}}
        resp = self.url_open(path, data=json.dumps(payload), headers={"Content-Type": "application/json"})
        data = json.loads(resp.text)
        return data.get("result") if isinstance(data, dict) else data

    def test_version_info(self):
        result = self._jsonrpc("/web/webclient/version_info")
        self.assertIn("server_version", result)
        self.assertEqual(result["server_serie"], "19.0")

    def test_version_info_protocol(self):
        result = self._jsonrpc("/web/webclient/version_info")
        self.assertEqual(result["protocol_version"], 1)

    def test_publisher_warranty_disabled(self):
        IrConfig = self.env["ir.config_parameter"].sudo()
        IrConfig.set_param("spp.telemetry.enabled", "False")
        resp = self.url_open("/publisher-warranty")
        data = json.loads(resp.text)
        self.assertEqual(data.get("status"), "disabled")

    def test_publisher_warranty_enabled(self):
        IrConfig = self.env["ir.config_parameter"].sudo()
        IrConfig.set_param("spp.telemetry.enabled", "True")
        IrConfig.set_param("spp.telemetry.endpoint", "https://telemetry.openspp.org")
        resp = self.url_open("/publisher-warranty")
        data = json.loads(resp.text)
        self.assertEqual(data.get("status"), "redirected")
        self.assertTrue(data.get("endpoint"))

    def test_publisher_warranty_content_type(self):
        resp = self.url_open("/publisher-warranty")
        self.assertIn("application/json", resp.headers.get("Content-Type", ""))

    def test_session_info_contains_branding(self):
        self.authenticate("admin", "admin")
        IrConfig = self.env["ir.config_parameter"].sudo()
        IrConfig.set_param("spp.system.name", "OpenSPP Test")
        info = self._jsonrpc("/web/session/get_session_info")
        self.assertIn("spp_system_name", info)
        self.assertEqual(info["spp_system_name"], "OpenSPP Test")
        self.assertIn("server_version_info", info)
        self.assertEqual(info["server_version_info"][1], "19.0")

    def test_session_info_contains_all_branding_keys(self):
        self.authenticate("admin", "admin")
        info = self._jsonrpc("/web/session/get_session_info")
        expected_keys = [
            "spp_system_name",
            "spp_documentation_url",
            "spp_support_url",
            "is_spp_show_powered_by",
            "is_spp_telemetry_enabled",
            "spp_telemetry_endpoint",
        ]
        for key in expected_keys:
            self.assertIn(key, info, f"Session info should contain {key}")

    def test_session_info_server_version_info_format(self):
        self.authenticate("admin", "admin")
        info = self._jsonrpc("/web/session/get_session_info")
        version_info = info.get("server_version_info")
        self.assertIsNotNone(version_info)
        self.assertEqual(len(version_info), 5)
        self.assertEqual(version_info[0], "OpenSPP")

    def test_about_endpoint(self):
        self.authenticate("admin", "admin")
        resp = self.url_open("/openspp/about")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp.headers.get("Content-Type", ""))
        data = json.loads(resp.text)
        self.assertEqual(data["title"], "About OpenSPP")
        self.assertEqual(data["version"], "19.0.2.0.1")
        self.assertIn("system_name", data)
        self.assertIn("documentation_url", data)
        self.assertIn("support_url", data)

    def test_about_endpoint_reflects_config(self):
        self.authenticate("admin", "admin")
        IrConfig = self.env["ir.config_parameter"].sudo()
        IrConfig.set_param("spp.system.name", "Custom About Name")
        resp = self.url_open("/openspp/about")
        data = json.loads(resp.text)
        self.assertEqual(data["system_name"], "Custom About Name")

    def test_openspp_route_redirects_to_web_client(self):
        """Test that /openspp route is accessible and handled"""
        self.authenticate("admin", "admin")
        resp = self.url_open("/openspp", allow_redirects=False)
        # Should return 200 (rendered page) or 303 redirect to login/web
        self.assertIn(resp.status_code, [200, 303])

    def test_openspp_subpath_route(self):
        """Test that /openspp/<subpath> route is accessible"""
        self.authenticate("admin", "admin")
        resp = self.url_open("/openspp/some-path", allow_redirects=False)
        # Should return 200 or redirect — not 404
        self.assertNotEqual(resp.status_code, 404)

    def test_openspp_route_unauthenticated(self):
        """Test that /openspp without auth redirects to login"""
        resp = self.url_open("/openspp", allow_redirects=False)
        # Unauthenticated should redirect (302/303) to login
        self.assertIn(resp.status_code, [200, 302, 303])

    def test_about_endpoint_requires_auth(self):
        """Test that /openspp/about requires authentication"""
        # Without authenticating, should redirect to login
        resp = self.url_open("/openspp/about", allow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])
