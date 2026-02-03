# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    # DRIMS specific
    drims_request_line_id = fields.Many2one(
        "spp.drims.request.line",
        string="Request Line",
        help="Link to the request line this move fulfills",
    )
    drims_donation_line_id = fields.Many2one(
        "spp.drims.donation.line",
        string="Donation Line",
        help="Link to the donation line this move receives",
    )
