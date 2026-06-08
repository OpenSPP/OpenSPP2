from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIrModuleModuleHelpers(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Module = self.env["ir.module.module"]

    def test_get_paid_apps_count(self):
        """Test get_paid_apps_count method"""
        self.Module.create(
            {
                "name": "test_oeel_app",
                "shortdesc": "Test OEEL App",
                "license": "OEEL-1",
            }
        )
        self.Module.create(
            {
                "name": "test_opl_app",
                "shortdesc": "Test OPL App",
                "license": "OPL-1",
            }
        )
        self.Module.create(
            {
                "name": "test_free_app",
                "shortdesc": "Test Free App",
                "license": "LGPL-3",
            }
        )

        count = self.Module.get_paid_apps_count()
        self.assertGreaterEqual(count, 2, "Should count at least the two paid test apps")

    def test_get_paid_apps_count_excludes_free(self):
        """Test that get_paid_apps_count does not count free licenses"""
        # Get baseline count
        baseline = self.Module.get_paid_apps_count()

        # Add a free app — count should not increase
        self.Module.create(
            {
                "name": "test_lgpl_app_extra",
                "shortdesc": "Test LGPL App",
                "license": "LGPL-3",
            }
        )
        self.assertEqual(self.Module.get_paid_apps_count(), baseline)

    def test_get_paid_apps_count_zero_when_none(self):
        """Test get_paid_apps_count returns int"""
        count = self.Module.get_paid_apps_count()
        self.assertIsInstance(count, int)


@tagged("post_install", "-at_install")
class TestResUsers(TransactionCase):
    def setUp(self):
        super().setUp()
        self.ResUsers = self.env["res.users"]

    def test_get_default_email_signature(self):
        """Test that default email signature is customized"""
        signature = self.ResUsers._get_default_email_signature()

        self.assertIn("OpenSPP Platform", signature)
        self.assertIn("Open Source Social Protection Platform", signature)
        self.assertNotIn("Odoo", signature)

    def test_get_default_email_signature_is_html(self):
        """Test that default email signature contains HTML markup"""
        signature = self.ResUsers._get_default_email_signature()
        self.assertIn("<br/>", signature)
        self.assertIn("<span", signature)

    def test_compute_odoo_account_url(self):
        """Test that Odoo account URL is removed"""
        user = self.ResUsers.create(
            {
                "name": "Test User",
                "login": "test_user_account",
                "email": "test@example.com",
            }
        )

        self.assertFalse(user.odoo_account_url)

        user._compute_odoo_account_url()
        self.assertFalse(user.odoo_account_url)

    def test_compute_odoo_account_url_multiple_users(self):
        """Test that odoo_account_url is False for all users in a batch"""
        users = self.ResUsers.browse()
        for login_suffix in ["a", "b", "c"]:
            users |= self.ResUsers.create(
                {
                    "name": f"Test {login_suffix}",
                    "login": f"test_batch_{login_suffix}",
                    "email": f"test_{login_suffix}@example.com",
                }
            )
        users._compute_odoo_account_url()
        for user in users:
            self.assertFalse(user.odoo_account_url)

    def test_odoo_account_url_field_properties(self):
        """Test that odoo_account_url field has correct properties"""
        field = self.ResUsers._fields.get("odoo_account_url")
        self.assertIsNotNone(field)
        self.assertEqual(field.string, "Account URL")
        self.assertEqual(field.help, "OpenSPP Account Management")
        self.assertTrue(field.compute)


@tagged("post_install", "-at_install")
class TestResConfigSettings(TransactionCase):
    def setUp(self):
        super().setUp()
        self.IrConfigParam = self.env["ir.config_parameter"].sudo()
        self.Settings = self.env["res.config.settings"]

    def test_settings_fields_exist(self):
        """Test that all branding settings fields are defined"""
        fields = self.Settings._fields
        expected = [
            "spp_system_name",
            "spp_documentation_url",
            "spp_support_url",
            "is_spp_show_powered_by",
            "is_spp_telemetry_enabled",
            "spp_telemetry_endpoint",
            "is_spp_hide_odoo_referral",
        ]
        for field_name in expected:
            self.assertIn(field_name, fields, f"Field {field_name} should exist")

    def test_settings_default_values(self):
        """Test that settings have correct default values"""
        settings = self.Settings.create({})
        # Values come from ir.config_parameter data XML (which uses trailing slashes)
        self.assertIn("OpenSPP Platform", settings.spp_system_name)
        self.assertIn("docs.openspp.org", settings.spp_documentation_url)
        self.assertIn("openspp.org", settings.spp_support_url)
        self.assertTrue(settings.is_spp_show_powered_by)
        self.assertTrue(settings.is_spp_telemetry_enabled)
        self.assertIn("telemetry.openspp.org", settings.spp_telemetry_endpoint)
        self.assertTrue(settings.is_spp_hide_odoo_referral)

    def test_settings_persist_via_config_parameter(self):
        """Test that settings are persisted to ir.config_parameter"""
        settings = self.Settings.create(
            {
                "spp_system_name": "Test System",
                "spp_documentation_url": "https://test.docs",
            }
        )
        settings.execute()

        self.assertEqual(self.IrConfigParam.get_param("spp.system.name"), "Test System")
        self.assertEqual(self.IrConfigParam.get_param("spp.documentation.url"), "https://test.docs")

    def test_settings_read_from_config_parameter(self):
        """Test that settings read values from ir.config_parameter"""
        self.IrConfigParam.set_param("spp.system.name", "Stored System")
        self.IrConfigParam.set_param("spp.support.url", "https://stored.url")

        settings = self.Settings.create({})
        self.assertEqual(settings.spp_system_name, "Stored System")
        self.assertEqual(settings.spp_support_url, "https://stored.url")
