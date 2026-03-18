from odoo import fields, models


class OAuthConfig(models.TransientModel):
    _inherit = "res.config.settings"

    oauth_private_key = fields.Char(
        string="OAuth Private Key",
        config_parameter="spp_oauth.oauth_private_key",
    )
    oauth_public_key = fields.Char(
        string="OAuth Public Key",
        config_parameter="spp_oauth.oauth_public_key",
    )
