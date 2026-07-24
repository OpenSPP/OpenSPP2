# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Safety tests for this module's default-credential demo users.

``data/demo_users.xml`` creates farmer-registry-specific users with the shared
password ``demo`` (in addition to re-roling the spp_demo users). On a
production database (installed without demo data) they must be deactivated; on
a demo/evaluation database they must stay active.
"""

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_demo import deactivate_default_demo_users
from odoo.addons.spp_farmer_registry_demo import DEFAULT_DEMO_USER_XMLIDS


@tagged("post_install", "-at_install")
class TestFarmerDemoUserSafety(TransactionCase):
    def _default_users(self):
        users = self.env["res.users"].browse()
        for xmlid in DEFAULT_DEMO_USER_XMLIDS:
            user = self.env.ref(xmlid, raise_if_not_found=False)
            if user:
                users |= user
        return users

    def test_default_users_deactivated_when_demo_disabled(self):
        users = self._default_users()
        self.assertTrue(users, "farmer demo users should exist in the test database")
        users.active = True

        deactivated = deactivate_default_demo_users(self.env, DEFAULT_DEMO_USER_XMLIDS, demo_enabled=False)

        self.assertEqual(set(deactivated.ids), set(users.ids))
        self.assertFalse(
            any(users.mapped("active")),
            "all farmer default-credential demo users must be inactive when demo is disabled",
        )

    def test_default_users_active_when_demo_enabled(self):
        users = self._default_users()
        users.active = True

        deactivate_default_demo_users(self.env, DEFAULT_DEMO_USER_XMLIDS, demo_enabled=True)

        self.assertTrue(
            all(users.mapped("active")),
            "farmer demo users must remain active when demo data is enabled",
        )

    def test_farmer_demo_not_marked_production_stable(self):
        self.assertNotEqual(
            get_manifest("spp_farmer_registry_demo").get("development_status"),
            "Production/Stable",
        )
