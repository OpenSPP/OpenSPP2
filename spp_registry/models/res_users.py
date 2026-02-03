# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # Override chatter_position from muk_web_chatter to set default to 'bottom'
    chatter_position = fields.Selection(
        default="bottom",
    )
