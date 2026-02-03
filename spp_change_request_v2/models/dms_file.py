from odoo import fields, models


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
