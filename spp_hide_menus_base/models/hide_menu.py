# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import Command, fields, models

_logger = logging.getLogger(__name__)


class SppHideMenu(models.Model):
    _name = "spp.hide.menu"
    _description = "Hide Menu Configuration"
    _rec_name = "menu_id"

    menu_id = fields.Many2one("ir.ui.menu", required=True)
    state = fields.Selection(
        [("show", "Show"), ("hide", "Hidden")],
        default="show",
    )
    default_group_ids = fields.Many2many("res.groups")
    xml_id = fields.Char()

    def hide_menu(self, menu_id=None):
        record = self
        if menu_id:
            record = self.browse(menu_id)
        for rec in record:
            if rec.state == "show" and rec.menu_id:
                # Use new XMLID; keep backward-compatible fallback for older databases
                try:
                    group_id = self.env.ref("spp_hide_menus_base.group_hide_menus_user").id
                except ValueError:
                    group_id = self.env.ref("spp_hide_menus_base.group_menu_visibility").id
                show_non_openspp_group = [Command.set([group_id])]
                rec.default_group_ids = rec.menu_id.group_ids
                rec.menu_id.write(
                    {
                        "group_ids": show_non_openspp_group,
                    }
                )
                rec.state = "hide"

    def show_menu(self):
        for rec in self:
            if rec.state == "hide" and rec.menu_id:
                rec.menu_id.group_ids = rec.default_group_ids
                rec.state = "show"
