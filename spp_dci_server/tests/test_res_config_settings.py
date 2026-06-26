# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci_server.middleware.signature import _read_security_flag


@tagged("post_install", "-at_install")
class TestDCIServerConfigSettings(TransactionCase):
    """The DCI Server settings page must round-trip to ir.config_parameter
    and feed the values the auth middleware reads."""

    def setUp(self):
        super().setUp()
        self.Settings = self.env["res.config.settings"]
        self.Param = self.env["ir.config_parameter"].sudo()

    def _save(self, values):
        settings = self.Settings.create(values)
        settings.execute()
        return settings

    def test_api_tokens_round_trip(self):
        """Bearer tokens entered in settings persist to dci.api_tokens."""
        self._save({"dci_api_tokens": "alpha,beta"})
        self.assertEqual(self.Param.get_param("dci.api_tokens"), "alpha,beta")

        # And reading settings back reflects the stored value.
        reloaded = self.Settings.create({})
        self.assertEqual(reloaded.dci_api_tokens, "alpha,beta")

    def test_sender_id_round_trip(self):
        self._save({"dci_sender_id": "openspp.test.server"})
        self.assertEqual(self.Param.get_param("dci.sender_id"), "openspp.test.server")

    def test_security_flags_feed_middleware(self):
        """Toggling the dev flags is visible to the middleware's flag reader."""
        self._save(
            {
                "dci_allow_unsigned_requests": True,
                "dci_api_tokens_required": False,
            }
        )
        self.assertEqual(_read_security_flag(self.env, "dci.allow_unsigned_requests"), "true")
        self.assertEqual(_read_security_flag(self.env, "dci.api_tokens_required"), "false")

        # Flipping them back is honoured too.
        self._save(
            {
                "dci_allow_unsigned_requests": False,
                "dci_api_tokens_required": True,
            }
        )
        self.assertEqual(_read_security_flag(self.env, "dci.allow_unsigned_requests"), "false")
        self.assertEqual(_read_security_flag(self.env, "dci.api_tokens_required"), "true")
