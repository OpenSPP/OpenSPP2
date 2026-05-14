# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResUsersRoleCustomSPP(models.Model):
    _inherit = "res.users.role"

    role_type = fields.Selection([("local", "Local"), ("global", "Global")], default="global")

    @api.model_create_multi
    def create(self, vals_list):
        # Workaround: same Odoo cache-clearing bug as in base_user_role's write()
        # override. When res.groups fields are set via _inherits on create(),
        # implied_ids gets dropped. Extract group fields and write them to
        # group_id directly after creation, mirroring the write() fix.
        groups_vals_list = []
        group_fields = set(self.env["res.groups"]._fields) - {"name"}
        for vals in vals_list:
            group_vals = {}
            for field in group_fields:
                if field in vals:
                    group_vals[field] = vals.pop(field)
            groups_vals_list.append(group_vals)

        new_records = super().create(vals_list)

        for record, group_vals in zip(new_records, groups_vals_list, strict=True):
            if group_vals:
                record.group_id.write(group_vals)

        return new_records

    def action_update_users(self):
        """
        Call the update_users function to force the update of associated users in the role.
        :return:
        """
        for rec in self:
            _logger.info("Update user roles for role_id=%s", rec.id)
            rec.update_users()


class ResUsersRoleLineCustomSPP(models.Model):
    _inherit = "res.users.role.line"

    role_type = fields.Selection(related="role_id.role_type")
