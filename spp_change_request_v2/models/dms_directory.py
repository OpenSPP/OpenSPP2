from odoo import fields, models


class SPPDMSDirectory(models.Model):
    """Extend DMS Directory with change request reference."""

    _inherit = "spp.dms.directory"

    change_request_id = fields.Many2one(
        "spp.change.request",
        string="Change Request",
        ondelete="set null",
        index=True,
        help="Change request that owns this directory",
    )
