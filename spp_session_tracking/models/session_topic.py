# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SessionTopic(models.Model):
    _name = "spp.session.topic"
    _description = "Session Topic"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char()
    description = fields.Text()
    session_type_id = fields.Many2one("spp.session.type", string="Session Type")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
