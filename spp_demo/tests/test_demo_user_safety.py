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

from odoo.addons.spp_demo import DEFAULT_DEMO_USER_XMLIDS, deactivate_default_demo_users


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
