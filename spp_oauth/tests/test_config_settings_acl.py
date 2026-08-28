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
from odoo.service.model import call_kw
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

    def test_superuser_mode_bypasses_key_filter(self):
        """Superuser mode (sudo) is a trusted server-side context that already
        bypasses ACLs; default_get must not strip the keys there, even though
        env.user remains the original non-admin user. The RPC attack path is
        never in superuser mode, so this does not reopen the exposure."""
        settings = self.env["res.config.settings"].with_user(self.plain_user).sudo()
        self.assertTrue(settings.env.su)
        values = settings.default_get(["oauth_priv_key", "oauth_pub_key"])
        self.assertEqual(values.get("oauth_priv_key"), PRIV_KEY_SENTINEL)
        self.assertEqual(values.get("oauth_pub_key"), PUB_KEY_SENTINEL)

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

    def test_default_get_dispatches_as_model_method_over_rpc(self):
        """default_get must stay @api.model-dispatched through the RPC layer.

        call_kw reads the ``_api_model`` marker off the MOST-DERIVED method, so
        an undecorated override silently flips every external
        ``res.config.settings.default_get`` RPC call onto the record-style path
        (browse(fields_list) → TypeError). The in-process tests above cannot
        catch that, so go through the real dispatcher here.
        """
        model = self.env["res.config.settings"].with_user(self.admin_user)
        values = call_kw(model, "default_get", [["oauth_priv_key", "oauth_pub_key"]], {})
        self.assertEqual(values.get("oauth_priv_key"), PRIV_KEY_SENTINEL)
        self.assertEqual(values.get("oauth_pub_key"), PUB_KEY_SENTINEL)

        # The RPC leak path this module guards: a plain internal user calling
        # default_get remotely must get a clean dict, not a crash and not keys.
        model = self.env["res.config.settings"].with_user(self.plain_user)
        values = call_kw(model, "default_get", [["oauth_priv_key", "oauth_pub_key"]], {})
        self.assertNotIn("oauth_priv_key", values)
        self.assertNotIn("oauth_pub_key", values)

    def test_key_fields_are_group_gated_on_direct_read(self):
        """The signing-key fields carry groups="base.group_system", enforced by
        the ORM even on internal attribute access: a non-admin reading the
        field must get an AccessError, independently of the model ACL.

        The fields_get() check is the part the model ACL cannot mask: it is
        metadata-level, so it proves the FIELD gate itself exists — the
        attribute-access checks below would also be satisfied by the model
        ACL alone in today's topology."""
        fields_visible = self.env["res.config.settings"].with_user(self.plain_user).fields_get()
        self.assertNotIn("oauth_priv_key", fields_visible)
        self.assertNotIn("oauth_pub_key", fields_visible)

        settings = self.env["res.config.settings"].create({})
        with self.assertRaises(AccessError):
            settings.with_user(self.plain_user).oauth_priv_key  # noqa: B018
        with self.assertRaises(AccessError):
            settings.with_user(self.plain_user).oauth_pub_key  # noqa: B018

    def test_save_by_unauthorized_user_fails_closed_without_blanking_keys(self):
        """Pins the fail-closed OUTCOME: an unauthorized save attempt raises
        and the stored keys survive. In today's topology the model ACL raises
        before the field gate is consulted — the gate is defence-in-depth for
        the day another module re-widens the model ACL (exactly how this
        module leaked before 2.0.1), where a save would otherwise write False
        into set_param(), DELETING the parameters and killing RS256 issuance."""
        settings = self.env["res.config.settings"].create({})
        with self.assertRaises(AccessError):
            settings.with_user(self.plain_user).set_values()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("spp_oauth.oauth_priv_key"), PRIV_KEY_SENTINEL)
        self.assertEqual(icp.get_param("spp_oauth.oauth_pub_key"), PUB_KEY_SENTINEL)

    def test_admin_save_round_trip_preserves_keys(self):
        """A legitimate admin save must not disturb the stored keys: admin's
        default_get returns them, so create() backfills the real values and
        set_values() writes them back unchanged."""
        settings = self.env["res.config.settings"].with_user(self.admin_user).create({})
        settings.set_values()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("spp_oauth.oauth_priv_key"), PRIV_KEY_SENTINEL)
        self.assertEqual(icp.get_param("spp_oauth.oauth_pub_key"), PUB_KEY_SENTINEL)
