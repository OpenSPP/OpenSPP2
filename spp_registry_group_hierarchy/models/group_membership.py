import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPGroupMembership(models.Model):
    _inherit = "spp.group.membership"

    individual_domain = fields.Binary(
        compute="_compute_individual_domain",
        readonly=True,
        store=False,
    )

    @api.depends("group", "group.group_type_id")
    def _compute_individual_domain(self):
        """
        Called whenever kind field is changed

        This method is used for dynamic domain of individual field
        """
        for rec in self:
            domain = [("is_group", "=", False), ("is_registrant", "=", True)]
            if rec.group and rec.group.group_type_id and rec.group.group_type_id.allow_all_member_type:
                if rec.group:
                    try:
                        group_id = int(rec.group.id)
                    except (ValueError, TypeError):
                        group_id = rec.group._origin.id
                    domain = [("is_registrant", "=", True), ("id", "!=", group_id)]
            rec.individual_domain = domain

    def open_member_form(self):
        for rec in self:
            if rec.individual:
                if rec.individual.is_group:
                    return {
                        "name": "Group Membership",
                        "view_mode": "form",
                        "res_model": "res.partner",
                        "res_id": rec.individual.id,
                        "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                        "type": "ir.actions.act_window",
                        "target": "new",
                        "context": {"default_is_group": True},
                        "flags": {"mode": "readonly"},
                    }
                else:
                    return rec.open_individual_form()
            else:
                raise UserError(_("A group or individual must be specified for this member."))
