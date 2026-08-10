# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Safety tests for this module's default-credential demo users.

``data/demo_users.xml`` creates DRIMS Sri Lanka users with the shared password
``demo`` (including ``user_admin_dmc``, which holds ``base.group_system``). On a
production database (installed without demo data) they must be deactivated; on a
demo/evaluation database they must stay active. This module does not depend on
spp_demo, so the archiving helper is self-contained here.
"""

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_drims_sl import (
    DEFAULT_DEMO_USER_XMLIDS,
    deactivate_default_demo_users,
    demo_data_enabled,
    post_init_hook,
)


@tagged("post_install", "-at_install")
class TestDrimsSlDemoUserSafety(TransactionCase):
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
            "all DRIMS-SL default-credential demo users must be inactive when demo is disabled",
        )

    def test_admin_user_is_covered(self):
        """The base.group_system super-admin demo account must be in the archive set."""
        self.assertIn("spp_drims_sl.user_admin_dmc", DEFAULT_DEMO_USER_XMLIDS)
        admin = self.env.ref("spp_drims_sl.user_admin_dmc", raise_if_not_found=False)
        self.assertTrue(admin, "user_admin_dmc should exist")
        self.assertTrue(admin.has_group("base.group_system"))

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
        module = self.env["ir.module.module"].search([("name", "=", "spp_drims_sl")], limit=1)

        if module.demo:
            self.skipTest("demo data enabled on this database; production path not exercised")

        post_init_hook(self.env)

        self.assertFalse(
            any(users.mapped("active")),
            "post_init_hook must archive default-credential users when demo is disabled",
        )

    def test_demo_data_enabled_matches_module_flag(self):
        module = self.env["ir.module.module"].search([("name", "=", "spp_drims_sl")], limit=1)
        self.assertEqual(demo_data_enabled(self.env, "spp_drims_sl"), bool(module.demo))

    def test_manifest_wires_post_init_hook(self):
        self.assertEqual(get_manifest("spp_drims_sl").get("post_init_hook"), "post_init_hook")
