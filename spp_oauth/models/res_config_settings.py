from odoo import api, fields, models

# The OAuth signing keys are only meaningful to system administrators. Access to
# res.config.settings is restricted to base.group_system via Odoo core's ACL (this
# module no longer widens it), but default_get() reads config_parameter fields with
# sudo() and performs no access check, so it is guarded explicitly below.
OAUTH_KEY_FIELDS = ("oauth_priv_key", "oauth_pub_key")


class RegistryConfig(models.TransientModel):
    _inherit = "res.config.settings"

    # groups= is enforced by the ORM on read/write/create/search AND on
    # internal attribute access - so an unauthorized principal reaching the
    # settings save path fails with AccessError instead of silently writing
    # False into set_param() (which would DELETE the stored keys and kill
    # RS256 issuance). It does NOT cover default_get, hence the override below.
    oauth_priv_key = fields.Char(
        string="OAuth Private Key",
        config_parameter="spp_oauth.oauth_priv_key",
        groups="base.group_system",
    )
    oauth_pub_key = fields.Char(
        string="OAuth Public Key",
        config_parameter="spp_oauth.oauth_pub_key",
        groups="base.group_system",
    )

    # @api.model is dispatch metadata read off the MOST-DERIVED method by
    # call_kw: without it here, every external RPC call to
    # res.config.settings.default_get (for any module's settings) crashes
    # with a TypeError. It is not inherited from the base method.
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # default_get sources config_parameter values via sudo(), bypassing model
        # and field access checks. Never expose the OAuth signing keys to a user
        # who is not a system administrator. Superuser mode (self.env.su) is a
        # trusted server-side context that already bypasses ACLs, so honour it here
        # too — env.user stays the original (possibly non-admin) user under sudo().
        if not self.env.su and not self.env.user.has_group("base.group_system"):
            for field_name in OAUTH_KEY_FIELDS:
                res.pop(field_name, None)
        return res
