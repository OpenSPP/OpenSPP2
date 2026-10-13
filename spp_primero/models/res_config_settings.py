# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

# The webhook key is a credential for the OpenFn trigger. res.config.settings is
# admin-only through Odoo's ACL (and Odoo 19's default_get checks it), but
# default_get() reads config parameters with sudo(), so the values are also
# stripped here as defence in depth should the model ACL ever be widened (same
# pattern as spp_oauth, whose ACL once was).
PRIMERO_SETTINGS_FIELDS = ("primero_webhook_url", "primero_webhook_api_key")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    primero_webhook_url = fields.Char(
        string="OpenFn Webhook URL",
        config_parameter="spp_primero.webhook_url",
        groups="base.group_system",
        help="The webhook trigger URL of the OpenFn workflow that refers a child to Primero.",
    )
    primero_webhook_api_key = fields.Char(
        string="OpenFn Webhook API Key",
        config_parameter="spp_primero.webhook_api_key",
        groups="base.group_system",
        help="API key attached to the webhook trigger in OpenFn (sent as the x-api-key header).",
    )

    # @api.model is dispatch metadata read off the most-derived method by call_kw;
    # without it every RPC call to res.config.settings.default_get crashes.
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Superuser mode is a trusted server-side context that already bypasses
        # ACLs; env.user stays the original user under sudo().
        if not self.env.su and not self.env.user.has_group("base.group_system"):
            for field_name in PRIMERO_SETTINGS_FIELDS:
                res.pop(field_name, None)
        return res
