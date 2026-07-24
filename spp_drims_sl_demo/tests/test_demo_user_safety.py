# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Safety tests for this module's default-credential demo users.

``data/demo_users.xml`` creates DRIMS Sri Lanka demo users with the shared
password ``demo``. On a production database (installed without demo data) they
must be deactivated; on a demo/evaluation database they must stay active. The
archiving helper is reused from spp_drims_sl (this module's dependency).
"""

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_drims_sl import deactivate_default_demo_users, demo_data_enabled
from odoo.addons.spp_drims_sl_demo import DEFAULT_DEMO_USER_XMLIDS, post_init_hook


@tagged("post_install", "-at_install")
class TestDrimsSlDemoDemoUserSafety(TransactionCase):
    def _default_users(self):
        users = self.env["res.users"].browse()
        for xmlid in DEFAULT_DEMO_USER_XMLIDS:
            user = self.env.ref(xmlid, raise_if_not_found=False)
            if user:
                users |= user
        return users

    def test_default_users_deactivated_when_demo_disabled(self):
        users = self._default_users()
        self.assertTrue(users, "DRIMS-SL demo users should exist in the test database")
        users.active = True

        deactivated = deactivate_default_demo_users(self.env, DEFAULT_DEMO_USER_XMLIDS, demo_enabled=False)

        self.assertEqual(set(deactivated.ids), set(users.ids))
        self.assertFalse(
            any(users.mapped("active")),
            "all DRIMS-SL demo default-credential users must be inactive when demo is disabled",
        )

    def test_default_users_active_when_demo_enabled(self):
        users = self._default_users()
        users.active = True

        deactivate_default_demo_users(self.env, DEFAULT_DEMO_USER_XMLIDS, demo_enabled=True)

        self.assertTrue(
            all(users.mapped("active")),
            "DRIMS-SL demo users must remain active when demo data is enabled",
        )

    def test_post_init_hook_archives_users_on_production(self):
        users = self._default_users()
        users.active = True
        module = self.env["ir.module.module"].search([("name", "=", "spp_drims_sl_demo")], limit=1)

        if module.demo:
            self.skipTest("demo data enabled on this database; production path not exercised")

        post_init_hook(self.env)

        self.assertFalse(
            any(users.mapped("active")),
            "post_init_hook must archive default-credential users when demo is disabled",
        )

    def test_demo_data_enabled_matches_module_flag(self):
        module = self.env["ir.module.module"].search([("name", "=", "spp_drims_sl_demo")], limit=1)
        self.assertEqual(demo_data_enabled(self.env, "spp_drims_sl_demo"), bool(module.demo))

    def test_manifest_wires_post_init_hook(self):
        self.assertEqual(get_manifest("spp_drims_sl_demo").get("post_init_hook"), "post_init_hook")
