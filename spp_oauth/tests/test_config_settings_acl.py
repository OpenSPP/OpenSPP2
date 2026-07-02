# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: OAuth signing keys must be restricted to system administrators.

Regression test for "OAuth signing keys exposed to all internal users": the
module granted ``base.group_user`` read/write on ``res.config.settings``, which
exposes ``oauth_priv_key`` (the RS256 JWT signing key) and ``oauth_pub_key``.
Any internal user could therefore:
  - read the model directly (``read``/``search``) via RPC, and
  - retrieve the keys through ``res.config.settings.default_get()``, which reads
    the backing ``ir.config_parameter`` values with ``sudo()`` and performs no
    model-ACL or field-group check.

Access must require a system administrator (``base.group_system``), and the
signing keys must not leak through ``default_get`` to non-admins.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

PRIV_KEY_SENTINEL = "TEST-OAUTH-PRIVATE-KEY-DO-NOT-LEAK"
PUB_KEY_SENTINEL = "TEST-OAUTH-PUBLIC-KEY"


@tagged("post_install", "-at_install")
class TestOAuthConfigSettingsAcl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param("spp_oauth.oauth_priv_key", PRIV_KEY_SENTINEL)
        icp.set_param("spp_oauth.oauth_pub_key", PUB_KEY_SENTINEL)

        # A plain internal user: base.group_user only, no system access.
        cls.plain_user = cls.env["res.users"].create(
            {
                "name": "Plain Internal User",
                "login": "plain_internal_oauth_test",
                "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )
        # A system administrator.
        cls.admin_user = cls.env["res.users"].create(
            {
                "name": "System Admin User",
                "login": "system_admin_oauth_test",
                "group_ids": [Command.link(cls.env.ref("base.group_system").id)],
            }
        )

    def test_plain_user_cannot_access_settings_model(self):
        """base.group_user (any internal user) must NOT have read access to
        res.config.settings — that is the model exposing the signing keys."""
        with self.assertRaises(AccessError):
            self.env["res.config.settings"].with_user(self.plain_user).check_access("read")

    def test_plain_user_cannot_read_keys_via_default_get(self):
        """The signing keys must not leak to a non-admin through default_get(),
        which reads the backing config parameters with sudo()."""
        settings = self.env["res.config.settings"].with_user(self.plain_user)
        values = settings.default_get(["oauth_priv_key", "oauth_pub_key"])
        self.assertNotIn("oauth_priv_key", values)
        self.assertNotIn("oauth_pub_key", values)

    def test_admin_can_access_settings_model(self):
        """A system administrator retains read access to res.config.settings."""
        # Raises AccessError only if admin access was wrongly removed.
        self.env["res.config.settings"].with_user(self.admin_user).check_access("read")

    def test_admin_can_read_keys_via_default_get(self):
        """A system administrator can still read the signing keys, so the
        Settings UI keeps working for admins."""
        settings = self.env["res.config.settings"].with_user(self.admin_user)
        values = settings.default_get(["oauth_priv_key", "oauth_pub_key"])
        self.assertEqual(values.get("oauth_priv_key"), PRIV_KEY_SENTINEL)
        self.assertEqual(values.get("oauth_pub_key"), PUB_KEY_SENTINEL)
