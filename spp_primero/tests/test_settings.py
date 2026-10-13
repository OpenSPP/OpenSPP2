# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The OpenFn webhook API key must not leak to non-admins through default_get()."""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import WEBHOOK_API_KEY, WEBHOOK_URL, PrimeroTestCase

SETTINGS_FIELDS = ["primero_webhook_url", "primero_webhook_api_key"]


@tagged("post_install", "-at_install")
class TestSettings(PrimeroTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls._make_user("primero_admin", ["base.group_system"])

    def test_fields_are_admin_only(self):
        Settings = self.env["res.config.settings"]
        for name in SETTINGS_FIELDS:
            with self.subTest(field=name):
                self.assertEqual(Settings._fields[name].groups, "base.group_system")

    def test_officer_cannot_read_values_via_default_get(self):
        """Odoo's res.config.settings.default_get checks model read access first, so a
        non-admin is refused outright; the field-level guard is defence in depth."""
        with self.assertRaises(AccessError):
            self.env["res.config.settings"].with_user(self.officer).default_get(SETTINGS_FIELDS)

    def test_admin_reads_values_via_default_get(self):
        values = self.env["res.config.settings"].with_user(self.admin).default_get(SETTINGS_FIELDS)
        self.assertEqual(values.get("primero_webhook_url"), WEBHOOK_URL)
        self.assertEqual(values.get("primero_webhook_api_key"), WEBHOOK_API_KEY)

    def test_superuser_mode_keeps_values(self):
        settings = self.env["res.config.settings"].with_user(self.officer).sudo()
        values = settings.default_get(SETTINGS_FIELDS)
        self.assertEqual(values.get("primero_webhook_api_key"), WEBHOOK_API_KEY)

    def test_settings_roundtrip(self):
        settings = (
            self.env["res.config.settings"]
            .with_user(self.admin)
            .create(
                {
                    "primero_webhook_url": "https://lightning.example.test/i/abc",
                    "primero_webhook_api_key": "new-key",
                }
            )
        )
        settings.execute()
        params = self.env["ir.config_parameter"].sudo()
        self.assertEqual(params.get_param("spp_primero.webhook_url"), "https://lightning.example.test/i/abc")
        self.assertEqual(params.get_param("spp_primero.webhook_api_key"), "new-key")
