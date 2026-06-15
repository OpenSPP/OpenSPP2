# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command, api, fields, models


class SPPUserCustom(models.Model):
    _inherit = "res.users"

    center_area_ids = fields.Many2many(
        comodel_name="spp.area",
        string="Center Areas",
        compute="_compute_center_area_ids",
        store=True,
    )

    @api.depends("role_line_ids.role_id", "role_line_ids.local_area_ids")
    def _compute_center_area_ids(self):
        for user in self:
            if user.center_area_ids:
                user.update({"center_area_ids": [Command.clear()]})
            if user.role_line_ids:
                center_area_ids = []
                for rl in user.role_line_ids.filtered(lambda a: a.role_type == "local"):
                    for area in rl.local_area_ids:
                        center_area_ids.append(Command.link(area.id))
                if center_area_ids:
                    user.update({"center_area_ids": center_area_ids})
