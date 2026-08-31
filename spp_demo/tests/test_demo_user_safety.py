# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Safety tests for the default-credential demo users.

``data/users_data.xml`` creates active users with the shared, documented
password ``demo`` (including ``sppadmin`` with SPP admin rights) via the
module's ``data`` section, so the accounts exist after any install. On a
production database (installed without demo data) they must be deactivated so
the well-known credentials cannot be used to log in; on a demo/evaluation
database they must stay active so demos and generators work.
"""

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_demo import (
    DEFAULT_DEMO_USER_XMLIDS,
    deactivate_default_demo_users,
    demo_data_enabled,
)


@tagged("post_install", "-at_install")
class TestDemoUserSafety(TransactionCase):
    def _default_users(self):
        users = self.env["res.users"].browse()
        for xmlid in DEFAULT_DEMO_USER_XMLIDS:
            user = self.env.ref(xmlid, raise_if_not_found=False)
            if user:
                users |= user
        return users

    def test_default_users_deactivated_when_demo_disabled(self):
        """On a non-demo (production-style) install the default-credential
        users are archived so their known password cannot be used."""
        users = self._default_users()
        self.assertTrue(users, "demo users should exist in the test database")
        users.active = True  # precondition

        deactivated = deactivate_default_demo_users(self.env, DEFAULT_DEMO_USER_XMLIDS, demo_enabled=False)

        self.assertEqual(set(deactivated.ids), set(users.ids))
        self.assertFalse(
            any(users.mapped("active")),
            "all default-credential demo users must be inactive when demo is disabled",
        )

    def test_default_users_active_when_demo_enabled(self):
        """On a demo/evaluation database the users stay active so the demos
        and generators keep working."""
        users = self._default_users()
        users.active = True

        deactivated = deactivate_default_demo_users(self.env, DEFAULT_DEMO_USER_XMLIDS, demo_enabled=True)

        self.assertFalse(deactivated)
        self.assertTrue(
            all(users.mapped("active")),
            "demo users must remain active when demo data is enabled",
        )

    def test_spp_demo_not_marked_production_stable(self):
        """A demo module that ships default-credential users must not signal
        production-readiness via development_status."""
        self.assertNotEqual(
            get_manifest("spp_demo").get("development_status"),
            "Production/Stable",
        )

    def test_demo_data_enabled_matches_module_flag(self):
        """The production-vs-demo decision is load-bearing: it must reflect the
        module's real demo flag. A regression here (wrong module name, changed
        Odoo semantics) would leave production exposed while the helper tests
        above still pass."""
        module = self.env["ir.module.module"].search([("name", "=", "spp_demo")], limit=1)
        self.assertEqual(demo_data_enabled(self.env, "spp_demo"), bool(module.demo))

    def test_manifest_wires_post_init_hook(self):
        """The guard only runs if the manifest actually registers the hook."""
        self.assertEqual(get_manifest("spp_demo").get("post_init_hook"), "post_init_hook")
