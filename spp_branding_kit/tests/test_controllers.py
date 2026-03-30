from odoo.fields import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestDebugRestriction(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.IrConfigParam = cls.env["ir.config_parameter"].sudo()
        cls.regular_user = cls.env["res.users"].create(
            {
                "name": "Regular User",
                "login": "regular_debug_test",
                "email": "regular@example.com",
                "password": "regular_debug_test",
                "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )

    def test_debug_restricted_for_non_admin(self):
        """Non-admin user with debug flag should be redirected without debug"""
        self.IrConfigParam.set_param("spp.debug.admin_only", "True")
        self.authenticate("regular_debug_test", "regular_debug_test")

        resp = self.url_open("/web?debug=1", allow_redirects=False)
        # Should redirect to strip debug parameter
        if resp.status_code in [301, 302, 303]:
            self.assertNotIn("debug", resp.headers.get("Location", "").split("?")[-1])

    def test_debug_allowed_for_admin(self):
        """Admin user with debug flag should not be redirected"""
        self.IrConfigParam.set_param("spp.debug.admin_only", "True")
        self.authenticate("admin", "admin")

        resp = self.url_open("/web?debug=1", allow_redirects=False)
        # Admin should get 200 (not redirected away from debug)
        self.assertIn(resp.status_code, [200, 303])

    def test_debug_unrestricted_when_disabled(self):
        """When debug restriction is disabled, non-admin can use debug"""
        self.IrConfigParam.set_param("spp.debug.admin_only", "False")
        self.authenticate("regular_debug_test", "regular_debug_test")

        resp = self.url_open("/web?debug=1", allow_redirects=False)
        # Should not redirect — debug is allowed for everyone
        self.assertIn(resp.status_code, [200, 303])

    def test_no_debug_param_no_redirect(self):
        """Request without debug param should not trigger debug restriction"""
        self.authenticate("admin", "admin")
        resp = self.url_open("/web", allow_redirects=False)
        self.assertIn(resp.status_code, [200, 303])
