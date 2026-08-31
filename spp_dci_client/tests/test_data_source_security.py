# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security tests: low-privilege users must not be able to mint or read DCI
OAuth tokens, nor trigger credentialed connection tests.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDataSourceCredentialAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.user = cls.env["res.users"].create(
            {
                "name": "DCI Low-Priv User",
                "login": "dci_lowpriv_user",
                "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )
        cls.ds = cls.DataSource.create(
            {
                "name": "OAuth DS",
                "code": "oauth_ds_sec",
                "base_url": "https://dci.example.org/api",
                "auth_type": "oauth2",
                "our_sender_id": "openspp.test",
                "oauth2_token_url": "https://auth.example.org/token",
                "oauth2_client_id": "cid",
                "oauth2_client_secret": "secret",
            }
        )

    def test_token_methods_are_private(self):
        """The credential methods must be private (underscore-prefixed).

        Odoo blocks RPC ``call_kw`` to underscore-prefixed methods (framework
        guarantee), so making them private removes them as an RPC entry point.
        This asserts the public names are gone (catching a re-added public alias)
        and the private ones exist; the RPC-dispatch block itself is a framework
        property of ``_``-prefixed names.
        """
        model = self.env["spp.dci.data.source"]
        self.assertFalse(hasattr(model, "get_oauth2_token"), "public get_oauth2_token must be removed")
        self.assertFalse(hasattr(model, "get_headers"), "public get_headers must be removed")
        self.assertTrue(hasattr(model, "_get_oauth2_token"))
        self.assertTrue(hasattr(model, "_get_headers"))

    def test_cached_token_field_hidden_from_regular_user(self):
        """The cached access token is a credential; it must not be visible to an
        ordinary internal user (who has read on the model)."""
        fields_for_user = self.ds.with_user(self.user).fields_get()
        self.assertNotIn("_oauth2_access_token", fields_for_user)
        self.assertNotIn("_oauth2_token_expires_at", fields_for_user)
        # An administrator can see them (control).
        fields_for_admin = self.ds.fields_get()
        self.assertIn("_oauth2_access_token", fields_for_admin)

    def test_regular_user_cannot_read_cached_token(self):
        """Even with a token cached, a regular user cannot read it back."""
        self.ds.sudo().write({"_oauth2_access_token": "super-secret-token"})
        with self.assertRaises(AccessError):
            self.ds.with_user(self.user).read(["_oauth2_access_token"])

    def test_test_connection_requires_write_access(self):
        """test_connection mints/uses admin-only credentials and makes an
        outbound call; a read-only user must not be able to trigger it."""
        with self.assertRaises(AccessError):
            self.ds.with_user(self.user).test_connection()

    def test_action_test_connection_requires_write_access(self):
        """The public button alias must inherit the same write gate."""
        with self.assertRaises(AccessError):
            self.ds.with_user(self.user).action_test_connection()

    def test_regular_user_context_can_clear_token_cache(self):
        """The internal cache-clear (used on a 401 retry) must work regardless of
        the current user's privilege — it writes admin-restricted fields via sudo."""
        self.ds.sudo().write({"_oauth2_access_token": "some-token"})
        # Called from server-side code running in a non-admin user context.
        self.ds.with_user(self.user)._clear_oauth2_token_cache()
        self.assertFalse(self.ds.sudo()._oauth2_access_token)

    def test_regular_user_context_can_get_bearer_headers(self):
        """A bearer-auth header must build in a non-admin user context: the
        admin-only bearer_token is read via sudo inside the internal method."""
        bearer_ds = self.DataSource.create(
            {
                "name": "Bearer DS",
                "code": "bearer_ds_sec",
                "base_url": "https://dci.example.org/api",
                "auth_type": "bearer",
                "our_sender_id": "openspp.test",
                "bearer_token": "secret-bearer-token",
            }
        )
        headers = bearer_ds.with_user(self.user)._get_headers()
        self.assertEqual(headers.get("Authorization"), "Bearer secret-bearer-token")
