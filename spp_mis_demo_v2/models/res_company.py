# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    mis_demo_loaded = fields.Boolean(
        string="MIS Demo Data Loaded",
        default=False,
        help="Indicates that MIS demo data has already been generated for this company.",
    )
