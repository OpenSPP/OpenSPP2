from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def write(self, vals):
        res = super().write(vals)

        pm_group = self.env.ref("spp_programs.group_programs_manager")
        admin_group = self.env.ref("spp_security.group_spp_admin")
        contact_creation_group = self.env.ref("base.group_partner_manager")

        for user in self:
            if pm_group in user.group_ids and not (user._is_admin() or admin_group in user.group_ids):
                # getting recursion using orm
                # avoid recursion so directly sql injected
                self.env.cr.execute(
                    "DELETE FROM res_groups_users_rel WHERE uid = %s AND gid = %s",
                    (user.id, contact_creation_group.id),
                )
                user._invalidate_cache(["group_ids"])
        return res
