from odoo import fields, models


class ShowCredentialWizard(models.TransientModel):
    """One-time display of freshly generated API client credentials.

    The plaintext secret lives only on this transient record (vacuumed by
    Odoo); the credential record itself keeps only the scrypt hash.
    """

    _name = "spp.attendance.show.credential.wizard"
    _description = "Show Attendance API Client Credential"

    credential_id = fields.Many2one("spp.attendance.api.client.credential", readonly=True)
    client_name = fields.Char(readonly=True)
    display_client_id = fields.Char(string="Client ID", readonly=True)
    display_client_secret = fields.Char(
        string="Client Secret",
        readonly=True,
        help="Copy this now - it will not be shown again!",
    )
