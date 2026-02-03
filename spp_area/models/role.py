# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResUsersRoleCustomSPP(models.Model):
    _inherit = "res.users.role"

    @api.onchange("role_type")
    def _onchange_role_type(self):
        for rec in self:
            if rec.role_type == "global":
                for line in rec.line_ids:
                    if line.local_area_ids:
                        line.local_area_ids = [Command.clear()]


class ResUsersRoleLineCustomSPP(models.Model):
    _inherit = "res.users.role.line"

    local_area_ids = fields.Many2many(
        "spp.area",
        "spp_user_role_line_area_rel",
        "role_line_id",
        "area_id",
        string="Center Areas",
    )

    @api.constrains("role_type", "local_area_ids")
    def _check_local_area_ids(self):
        for rec in self:
            if rec.role_type == "local" and not rec.local_area_ids:
                raise ValidationError("Local roles must have at least one area assigned.")
            if rec.role_type == "global" and rec.local_area_ids:
                raise ValidationError("Global roles cannot have areas assigned.")
