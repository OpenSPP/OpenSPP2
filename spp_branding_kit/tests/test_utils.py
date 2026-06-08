from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestUtils(TransactionCase):
    def setUp(self):
        super().setUp()
        self.IrConfigParam = self.env["ir.config_parameter"].sudo()

    def test_get_param_returns_stored_value(self):
        """get_param returns the stored config parameter value"""
        from ..utils import get_param

        self.IrConfigParam.set_param("spp.test.key", "test_value")
        result = get_param(self.env, "spp.test.key")
        self.assertEqual(result, "test_value")

    def test_get_param_returns_default_when_missing(self):
        """get_param returns default when parameter does not exist"""
        from ..utils import get_param

        # Ensure param doesn't exist
        self.IrConfigParam.search([("key", "=", "spp.test.nonexistent")]).unlink()
        result = get_param(self.env, "spp.test.nonexistent", "fallback")
        self.assertEqual(result, "fallback")

    def test_get_param_returns_none_default(self):
        """get_param returns None when no default specified and param missing"""
        from ..utils import get_param

        self.IrConfigParam.search([("key", "=", "spp.test.none")]).unlink()
        result = get_param(self.env, "spp.test.none")
        self.assertFalse(result)

    def test_get_branding_config_defaults(self):
        """get_branding_config returns expected keys with defaults"""
        from ..utils import get_branding_config

        config = get_branding_config(self.env)
        self.assertIn("spp_system_name", config)
        self.assertIn("spp_documentation_url", config)
        self.assertIn("spp_support_url", config)
        self.assertIn("is_spp_show_powered_by", config)
        self.assertIn("is_spp_telemetry_enabled", config)
        self.assertIn("spp_telemetry_endpoint", config)

    def test_get_branding_config_uses_stored_values(self):
        """get_branding_config reflects stored config parameter values"""
        from ..utils import get_branding_config

        self.IrConfigParam.set_param("spp.system.name", "Custom System")
        self.IrConfigParam.set_param("spp.documentation.url", "https://custom.docs")
        self.IrConfigParam.set_param("spp.support.url", "https://custom.support")

        config = get_branding_config(self.env)
        self.assertEqual(config["spp_system_name"], "Custom System")
        self.assertEqual(config["spp_documentation_url"], "https://custom.docs")
        self.assertEqual(config["spp_support_url"], "https://custom.support")

    def test_get_branding_config_boolean_true(self):
        """get_branding_config parses 'True' string as boolean True"""
        from ..utils import get_branding_config

        self.IrConfigParam.set_param("spp.show.powered_by", "True")
        self.IrConfigParam.set_param("spp.telemetry.enabled", "True")

        config = get_branding_config(self.env)
        self.assertTrue(config["is_spp_show_powered_by"])
        self.assertTrue(config["is_spp_telemetry_enabled"])

    def test_get_branding_config_boolean_false(self):
        """get_branding_config parses non-'True' string as boolean False"""
        from ..utils import get_branding_config

        self.IrConfigParam.set_param("spp.show.powered_by", "False")
        self.IrConfigParam.set_param("spp.telemetry.enabled", "False")

        config = get_branding_config(self.env)
        self.assertFalse(config["is_spp_show_powered_by"])
        self.assertFalse(config["is_spp_telemetry_enabled"])

    def test_version_info_payload_structure(self):
        """version_info_payload returns expected structure"""
        from ..utils import version_info_payload

        result = version_info_payload(self.env)
        self.assertIn("server_version", result)
        self.assertIn("server_serie", result)
        self.assertIn("protocol_version", result)
        self.assertEqual(result["server_serie"], "19.0")
        self.assertEqual(result["protocol_version"], 1)

    def test_version_info_payload_uses_system_name(self):
        """version_info_payload uses stored system name"""
        from ..utils import version_info_payload

        self.IrConfigParam.set_param("spp.system.name", "My SPP")
        result = version_info_payload(self.env)
        self.assertEqual(result["server_version"], "My SPP")

    def test_telemetry_payload_disabled(self):
        """telemetry_payload returns disabled status when telemetry is off"""
        from ..utils import telemetry_payload

        self.IrConfigParam.set_param("spp.telemetry.enabled", "False")
        result = telemetry_payload(self.env)
        self.assertEqual(result["status"], "disabled")
        self.assertIn("message", result)
        self.assertNotIn("endpoint", result)

    def test_telemetry_payload_enabled(self):
        """telemetry_payload returns redirected status with endpoint when enabled"""
        from ..utils import telemetry_payload

        self.IrConfigParam.set_param("spp.telemetry.enabled", "True")
        self.IrConfigParam.set_param("spp.telemetry.endpoint", "https://test.endpoint")
        result = telemetry_payload(self.env)
        self.assertEqual(result["status"], "redirected")
        self.assertEqual(result["endpoint"], "https://test.endpoint")
        self.assertIn("message", result)

    def test_telemetry_payload_default_endpoint(self):
        """telemetry_payload uses default endpoint when none configured"""
        from ..utils import telemetry_payload

        self.IrConfigParam.set_param("spp.telemetry.enabled", "True")
        # Remove custom endpoint to test default
        self.IrConfigParam.search([("key", "=", "spp.telemetry.endpoint")]).unlink()
        result = telemetry_payload(self.env)
        self.assertEqual(result["status"], "redirected")
        self.assertEqual(result["endpoint"], "https://telemetry.openspp.org")
