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

    def test_token_methods_are_not_rpc_exposed(self):
        """The credential methods must be private (underscore-prefixed), so they
        are not callable over RPC; the public entrypoints must be gone."""
        model = self.env["spp.dci.data.source"]
        self.assertFalse(hasattr(model, "get_oauth2_token"), "get_oauth2_token must be removed (RPC-exposed)")
        self.assertFalse(hasattr(model, "get_headers"), "get_headers must be removed (RPC-exposed)")
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
