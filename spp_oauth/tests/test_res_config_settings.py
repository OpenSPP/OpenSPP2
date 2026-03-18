# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase


class TestResConfigSettings(TransactionCase):
    """Test res.config.settings OAuth key fields."""

    def test_set_oauth_keys_via_settings(self):
        """Test that OAuth keys set through settings are persisted to config parameters."""
        config = self.env["res.config.settings"].create({})
        config.oauth_private_key = "test-private-key"
        config.oauth_public_key = "test-public-key"
        config.execute()

        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("spp_oauth.oauth_private_key"), "test-private-key")
        self.assertEqual(icp.get_param("spp_oauth.oauth_public_key"), "test-public-key")

    def test_get_oauth_keys_from_settings(self):
        """Test that OAuth keys stored in config parameters are loaded into settings."""
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("spp_oauth.oauth_private_key", "stored-private-key")
        icp.set_param("spp_oauth.oauth_public_key", "stored-public-key")

        config = self.env["res.config.settings"].create({})
        self.assertEqual(config.oauth_private_key, "stored-private-key")
        self.assertEqual(config.oauth_public_key, "stored-public-key")
