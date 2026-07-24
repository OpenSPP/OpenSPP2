# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Safety tests for this module's default-credential demo users.

``data/demo_users.xml`` creates MIS demo users with the shared password
``demo``. On a production database (installed without demo data) they must be
deactivated; on a demo/evaluation database they must stay active. The module's
``post_init_hook`` composes the demo-variable activation with this archiving.
"""

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_mis_demo_v2 import (
    DEFAULT_DEMO_USER_XMLIDS,
    deactivate_default_demo_users,
    demo_data_enabled,
    post_init_hook,
)


@tagged("post_install", "-at_install")
class TestMisDemoUserSafety(TransactionCase):
    def _default_users(self):
        users = self.env["res.users"].browse()
        for xmlid in DEFAULT_DEMO_USER_XMLIDS:
            user = self.env.ref(xmlid, raise_if_not_found=False)
            if user:
                users |= user
        return users

    def test_default_users_deactivated_when_demo_disabled(self):
        users = self._default_users()
        self.assertTrue(users, "MIS demo users should exist in the test database")
        users.active = True

        deactivated = deactivate_default_demo_users(self.env, DEFAULT_DEMO_USER_XMLIDS, demo_enabled=False)

        self.assertEqual(set(deactivated.ids), set(users.ids))
        self.assertFalse(
            any(users.mapped("active")),
            "all MIS default-credential demo users must be inactive when demo is disabled",
        )

    def test_default_users_active_when_demo_enabled(self):
        users = self._default_users()
        users.active = True

        deactivate_default_demo_users(self.env, DEFAULT_DEMO_USER_XMLIDS, demo_enabled=True)

        self.assertTrue(
            all(users.mapped("active")),
            "MIS demo users must remain active when demo data is enabled",
        )

    def test_composed_hook_archives_users_on_production(self):
        """The module's own post_init_hook must archive the users when demo is off."""
        users = self._default_users()
        users.active = True
        module = self.env["ir.module.module"].search([("name", "=", "spp_mis_demo_v2")], limit=1)

        if module.demo:
            self.skipTest("demo data enabled on this database; production path not exercised")

        post_init_hook(self.env)

        self.assertFalse(
            any(users.mapped("active")),
            "the composed post_init_hook must archive default-credential users when demo is disabled",
        )

    def test_mis_demo_not_marked_production_stable(self):
        self.assertNotEqual(
            get_manifest("spp_mis_demo_v2").get("development_status"),
            "Production/Stable",
        )

    def test_demo_data_enabled_matches_module_flag(self):
        module = self.env["ir.module.module"].search([("name", "=", "spp_mis_demo_v2")], limit=1)
        self.assertEqual(demo_data_enabled(self.env, "spp_mis_demo_v2"), bool(module.demo))

    def test_manifest_wires_post_init_hook(self):
        self.assertEqual(get_manifest("spp_mis_demo_v2").get("post_init_hook"), "post_init_hook")
