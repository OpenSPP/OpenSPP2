# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    irrigation_asset_ids = fields.One2many(
        "spp.irrigation.asset",
        "farm_id",
        string="Irrigation Assets",
        help="Irrigation infrastructure (reservoirs, canals, pumps, wells, etc.) "
        "operated by or serving this farm. Surfaces the same records exposed "
        "by the standalone Irrigation menu, scoped to the current farm.",
    )
