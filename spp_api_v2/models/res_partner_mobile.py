# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Restore legacy mobile field for res.partner.

This keeps API V2 telecom mapping compatible with test expectations
by providing a dedicated mobile number field when Odoo's base model
does not define one.
"""

from odoo import fields, models


class ResPartnerMobile(models.Model):
    _inherit = "res.partner"

    mobile = fields.Char(string="Mobile")
