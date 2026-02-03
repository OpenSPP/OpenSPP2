# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResUsersCustomSPP(models.Model):
    _inherit = "res.users"

    # Stored version of role_ids for list view display
    # The base_user_role One2many computed field doesn't display in list views
    role_ids_stored = fields.Many2many(
        comodel_name="res.users.role",
        string="Roles",
        compute="_compute_role_ids_stored",
        store=True,
        groups="base.group_erp_manager",
    )

    @api.depends("role_line_ids.role_id", "role_line_ids.is_enabled")
    def _compute_role_ids_stored(self):
        for user in self:
            user.role_ids_stored = user.role_line_ids.filtered(lambda r: r.is_enabled).mapped("role_id")

    @api.model
    def _default_role_lines(self):
        """Build default role lines from a template user when available.

        ``base.default_user`` disappeared in Odoo 19.0, so we gracefully fall
        back to the first user that already has role lines defined. This keeps
        the feature working while remaining backward compatible when the XMLID
        is present.
        """

        default_user = self.env.ref("base.default_user", raise_if_not_found=False)
        if not default_user:
            default_user = self.env["res.users"].search([("role_line_ids", "!=", False)], limit=1)

        default_values = []
        if default_user:
            for role_line in default_user.with_context(active_test=False).role_line_ids:
                default_values.append(
                    {
                        "role_id": role_line.role_id.id,
                        "date_from": role_line.date_from,
                        "date_to": role_line.date_to,
                        "is_enabled": role_line.is_enabled,
                    }
                )
        return default_values

    def set_groups_from_roles(self, force=False):
        """Override the original method to exclude some groups in removing."""
        DO_NOT_REMOVE_GROUPS = [
            self.env.ref("base.group_user").id,
            self.env.ref("base.group_no_one").id,
            self.env.ref("mail.group_mail_template_editor").id,
            self.env.ref("base.group_portal").id,
            self.env.ref("base.group_public").id,
        ]
        role_groups = {}
        # We obtain all the groups associated to each role first, so that
        # it is faster to compare later with each user's groups.
        for role in self.mapped("role_line_ids.role_id"):
            role_groups[role] = list(set(role.group_id.ids + role.implied_ids.ids + role.all_implied_ids.ids))

        for user in self:
            if not user.role_line_ids and not force:
                continue
            group_ids = []
            for role_line in user._get_enabled_roles():
                role = role_line.role_id
                group_ids += role_groups[role]
            group_ids = list(set(group_ids))  # Remove duplicates IDs
            groups_to_add = list(set(group_ids) - set(user.group_ids.ids))
            groups_to_remove = list(set(user.group_ids.ids) - set(group_ids))

            for group in DO_NOT_REMOVE_GROUPS:
                if group in groups_to_remove:
                    groups_to_remove.remove(group)

            # To fix the recurssion error caused by calling the write function of res.users
            add_group_ids = self.env["res.groups"].browse(groups_to_add)
            add_group_ids.write({"user_ids": [(4, user.id)]})

            remove_group_ids = self.env["res.groups"].browse(groups_to_remove)
            remove_group_ids.write({"user_ids": [(3, user.id)]})
        return True
