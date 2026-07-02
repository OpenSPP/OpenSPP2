from odoo import fields, models

# The OAuth signing keys are only meaningful to system administrators. Access to
# res.config.settings is restricted to base.group_system via Odoo core's ACL (this
# module no longer widens it), but default_get() reads config_parameter fields with
# sudo() and performs no access check, so it is guarded explicitly below.
OAUTH_KEY_FIELDS = ("oauth_priv_key", "oauth_pub_key")


class RegistryConfig(models.TransientModel):
    _inherit = "res.config.settings"

    oauth_priv_key = fields.Char(
        string="OAuth Private Key",
        config_parameter="spp_oauth.oauth_priv_key",
    )
    oauth_pub_key = fields.Char(
        string="OAuth Public Key",
        config_parameter="spp_oauth.oauth_pub_key",
    )

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # default_get sources config_parameter values via sudo(), bypassing model
        # and field access checks. Never expose the OAuth signing keys to a user
        # who is not a system administrator.
        if not self.env.user.has_group("base.group_system"):
            for field_name in OAUTH_KEY_FIELDS:
                res.pop(field_name, None)
        return res
