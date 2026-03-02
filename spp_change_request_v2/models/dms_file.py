from odoo import Command, api, fields, models

PREVIEWABLE_MIMETYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "video/mp4",
    "video/webm",
}


class SPPDMSFile(models.Model):
    """Extend DMS File with document type from vocabulary."""

    _inherit = "spp.dms.file"

    document_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Document Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:cr_document_type')]",
        index=True,
        help="Type of document from the standard document types vocabulary",
    )

    is_previewable = fields.Boolean(
        compute="_compute_is_previewable",
        string="Can Preview",
    )

    @api.depends("mimetype")
    def _compute_is_previewable(self):
        for rec in self:
            rec.is_previewable = rec.mimetype in PREVIEWABLE_MIMETYPES

    def action_preview(self):
        """Open file preview in the browser."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/spp.dms.file/{self.id}/content/{self.name}",
            "target": "new",
        }

    def action_download(self):
        """Download the file."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/spp.dms.file/{self.id}/content/{self.name}?download=true",
            "target": "self",
        }

    def action_remove_from_cr(self):
        """Remove this document from its change request and delete the file."""
        self.ensure_one()
        change_request = self.env["spp.change.request"].search([("document_ids", "in", self.id)], limit=1)
        if change_request:
            change_request.write({"document_ids": [Command.unlink(self.id)]})
        self.unlink()
