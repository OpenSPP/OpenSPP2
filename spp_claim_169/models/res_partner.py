import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Extension of res.partner to add QR credential integration."""

    _inherit = "res.partner"

    # One2many to credentials for this partner
    qr_credential_ids = fields.One2many(
        comodel_name="spp.claim169.credential",
        inverse_name="partner_id",
        string="QR Credentials",
        help="Claim 169 QR credentials issued to this registrant",
    )

    # Computed fields for stat button
    qr_credential_count = fields.Integer(
        compute="_compute_qr_credential_stats",
        string="Credential Count",
        help="Total number of QR credentials",
    )

    qr_credential_active_count = fields.Integer(
        compute="_compute_qr_credential_stats",
        string="Active Credentials",
        help="Number of active QR credentials",
    )

    qr_credential_count_string = fields.Char(
        compute="_compute_qr_credential_stats",
        string="QR Credentials",
        help="Display string for stat button",
    )

    # Latest active credential for inline display
    latest_qr_credential_id = fields.Many2one(
        comodel_name="spp.claim169.credential",
        compute="_compute_latest_qr_credential",
        store=True,
        string="Latest Credential",
        help="Most recent active QR credential",
    )

    latest_qr_image = fields.Binary(
        related="latest_qr_credential_id.qr_image",
        string="Latest QR Code",
        help="QR code image of the latest credential",
    )

    latest_qr_status = fields.Selection(
        related="latest_qr_credential_id.status",
        string="Credential Status",
        help="Status of the latest credential",
    )

    latest_qr_expires_at = fields.Datetime(
        related="latest_qr_credential_id.expires_at",
        string="Expires At",
        help="Expiration date of the latest credential",
    )

    latest_qr_credential_name = fields.Char(
        related="latest_qr_credential_id.name",
        string="Credential ID",
        help="ID of the latest credential",
    )

    def _compute_qr_credential_stats(self):
        """Compute credential counts for stat button."""
        for record in self:
            credentials = record.qr_credential_ids
            record.qr_credential_count = len(credentials)
            record.qr_credential_active_count = len(credentials.filtered(lambda c: c.status == "active"))
            active = record.qr_credential_active_count
            total = record.qr_credential_count
            record.qr_credential_count_string = f"{active} / {total}"

    @api.depends("qr_credential_ids", "qr_credential_ids.status")
    def _compute_latest_qr_credential(self):
        """Get the most recent active credential."""
        for record in self:
            # Get latest active credential (already ordered by issued_at desc)
            latest = self.env["spp.claim169.credential"].search(
                [
                    ("partner_id", "=", record.id),
                    ("status", "=", "active"),
                ],
                limit=1,
            )
            record.latest_qr_credential_id = latest

    def action_view_qr_credentials(self):
        """Open list view of QR credentials for this partner."""
        self.ensure_one()
        return {
            "name": _("QR Credentials - %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "spp.claim169.credential",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {
                "default_partner_id": self.id,
                "search_default_filter_active": 1,
            },
        }

    def action_generate_qr_credential(self):
        """Open wizard to generate QR credential for this partner."""
        self.ensure_one()
        return {
            "name": _("Generate QR Credential"),
            "type": "ir.actions.act_window",
            "res_model": "spp.claim169.generate.qr.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "res.partner",
                "active_ids": [self.id],
                "active_id": self.id,
            },
        }

    def action_view_latest_qr_credential(self):
        """Open form view of the latest QR credential."""
        self.ensure_one()
        if not self.latest_qr_credential_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Credential"),
                    "message": _("No active QR credential found."),
                    "type": "warning",
                },
            }
        return {
            "name": _("QR Credential"),
            "type": "ir.actions.act_window",
            "res_model": "spp.claim169.credential",
            "res_id": self.latest_qr_credential_id.id,
            "view_mode": "form",
            "target": "current",
        }
