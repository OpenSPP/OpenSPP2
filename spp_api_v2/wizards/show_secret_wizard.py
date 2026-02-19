# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ShowSecretWizard(models.TransientModel):
    """Wizard to display the client secret after generation/regeneration."""

    _name = "spp.api.client.show.secret.wizard"
    _description = "Show API Client Secret"

    client_id = fields.Many2one(
        "spp.api.client",
        string="API Client",
        readonly=True,
    )
    client_name = fields.Char(
        string="Client Name",
        readonly=True,
    )
    oauth_client_id = fields.Char(
        string="Client ID",
        readonly=True,
        help="Use this as client_id in your OAuth requests",
    )
    client_secret = fields.Char(
        string="Client Secret",
        readonly=True,
        help="Copy this now - it will not be shown again!",
    )

    def action_close(self):
        """Close the wizard and clear the secret from the client record."""
        if self.client_id:
            # Clear the plaintext secret from the client record
            # nosemgrep: odoo-sudo-without-context — wizard ACL controls access
            self.client_id.sudo().write({"client_secret": False})
        return {"type": "ir.actions.act_window_close"}
