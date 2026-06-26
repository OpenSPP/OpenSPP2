# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # The DCI auth middleware stores every boolean flag as the literal string
    # "true"/"false" (see middleware/signature.py:_read_security_flag) and falls
    # back to an in-code default when the parameter is missing. Odoo's
    # ``config_parameter`` boolean machinery is incompatible with that: it
    # *deletes* the parameter when the field is False (so a default-true flag can
    # never be turned off) and reads back ``bool("false")`` as True. We therefore
    # manage these flags explicitly in get_values/set_values instead.
    _DCI_FLAG_PARAMS = {
        "dci_api_tokens_required": ("dci.api_tokens_required", True),
        "dci_allow_unsigned_requests": ("dci.allow_unsigned_requests", False),
        "dci_bypass_bearer_auth": ("dci.bypass_bearer_auth", False),
        "dci_allow_http_callbacks": ("dci.allow_http_callbacks", False),
        "dci_allow_internal_callback_ips": ("dci.allow_internal_callback_ips", False),
    }

    # --- API authentication ---
    dci_api_tokens = fields.Char(
        string="DCI API Bearer Tokens",
        config_parameter="dci.api_tokens",
        help="Accepted bearer tokens for incoming DCI requests. "
        "Comma-separated for multiple clients. Each token must match the "
        "Bearer Token configured on the calling client's data source.",
    )
    dci_sender_id = fields.Char(
        string="DCI Server Sender ID",
        config_parameter="dci.sender_id",
        default="openspp",
        help="This server's own DCI sender id, stamped on outgoing envelopes.",
    )
    dci_api_tokens_required = fields.Boolean(
        string="Require DCI API Tokens",
        default=True,
        help="When enabled and no tokens are configured, every request is "
        "rejected (fail-closed). Disable only for development.",
    )

    # --- Development / insecure options (never enable in production) ---
    dci_allow_unsigned_requests = fields.Boolean(
        string="Allow Unsigned Requests",
        default=False,
        help="Development only. Accept DCI envelopes that carry no signature, "
        "skipping signature verification. Never enable in production.",
    )
    dci_bypass_bearer_auth = fields.Boolean(
        string="Bypass Bearer Authentication",
        default=False,
        help="Development only. Skip the bearer-token check entirely. Never enable in production.",
    )
    dci_allow_http_callbacks = fields.Boolean(
        string="Allow HTTP Callbacks",
        default=False,
        help="Development only. Permit plain-http (non-TLS) callback URLs. Never enable in production.",
    )
    dci_allow_internal_callback_ips = fields.Boolean(
        string="Allow Internal Callback IPs",
        default=False,
        help="Development only. Permit callbacks to internal/private IP addresses. Never enable in production.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        # System parameters require sudo; this view is gated to base.group_system.
        # nosemgrep: odoo-sudo-without-context
        icp = self.env["ir.config_parameter"].sudo()
        for field_name, (param, default) in self._DCI_FLAG_PARAMS.items():
            default_str = "true" if default else "false"
            res[field_name] = icp.get_param(param, default_str).lower() == "true"
        return res

    def set_values(self):
        super().set_values()
        # System parameters require sudo; this view is gated to base.group_system.
        # nosemgrep: odoo-sudo-without-context
        icp = self.env["ir.config_parameter"].sudo()
        for field_name, (param, _default) in self._DCI_FLAG_PARAMS.items():
            icp.set_param(param, "true" if self[field_name] else "false")
