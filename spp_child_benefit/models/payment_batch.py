# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class PaymentBatch(models.Model):
    """Surface the generated bank file (CSV) on the payment batch so it can be
    downloaded from the batch form. The file is produced by the Bank File
    (CSV) payment manager and stored as an attachment on the batch; the batch
    form has no attachment area of its own, so expose it explicitly."""

    _inherit = "spp.payment.batch"

    bank_file_ids = fields.Many2many(
        "ir.attachment",
        string="Bank Files",
        compute="_compute_bank_file_ids",
        help="Bank disbursement files generated for this batch. Click to download.",
    )

    def _compute_bank_file_ids(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.bank_file_ids = Attachment.search(
                [
                    ("res_model", "=", "spp.payment.batch"),
                    ("res_id", "=", rec.id),
                    ("mimetype", "=", "text/csv"),
                ]
            )
