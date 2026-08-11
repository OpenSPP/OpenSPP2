# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import Command, fields, models

_logger = logging.getLogger(__name__)


class SppHideMenu(models.Model):
    _name = "spp.hide.menu"
    _description = "Hide Menu Configuration"
    _rec_name = "menu_id"

    # A menu with two configuration rows aborts the registry load: hide_menus()
    # reads `.state` off the result of search([("menu_id", "=", ...)]), and a
    # multi-record set raises Expected singleton from _register_hook, which runs
    # on every registry load. The result is a total outage, not a degraded menu.
    #
    # This does not make _primary() redundant. Registry.post_constraint swallows a
    # constraint it cannot apply (it logs through _schema and continues), so a
    # database still holding duplicates when this lands keeps running without the
    # constraint — and would still crash without the defensive read.
    _unique_menu = models.Constraint(
        "UNIQUE(menu_id)",
        "A menu can only have one hide configuration.",
    )

    menu_id = fields.Many2one("ir.ui.menu", required=True)
    state = fields.Selection(
        [("show", "Show"), ("hide", "Hidden")],
        default="show",
    )
    default_group_ids = fields.Many2many("res.groups")
    xml_id = fields.Char()

    def _hide_group(self):
        """The group a hidden menu is collapsed onto, old xml_id as fallback."""
        try:
            return self.env.ref("spp_hide_menus_base.group_hide_menus_user")
        except ValueError:
            return self.env.ref("spp_hide_menus_base.group_menu_visibility")

    def _primary(self):
        """The single row that governs the menu, when more than one exists.

        ``UNIQUE(menu_id)`` makes this ``self`` on a healthy database. It matters
        where that constraint could not be applied — see the note on the
        constraint — so duplicates can outlive this module's migration.

        Prefers a row that can still restore its menu. ``hide_menu()`` snapshots
        ``group_ids`` into ``default_group_ids``, so a row created *after* the menu
        had already been collapsed holds nothing but the hide group and restores
        nothing. An empty snapshot is not degraded: a menu that declares no groups
        is correctly restored to no groups.
        """
        if len(self) <= 1:
            return self
        hide_group = self._hide_group()
        restorable = self.filtered(lambda rec: rec.default_group_ids != hide_group)
        return (restorable or self)[0]

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

    def _reapply_hide(self):
        """Re-apply hiding when module upgrade reset group_ids via XML."""
        try:
            hide_group = self.env.ref("spp_hide_menus_base.group_hide_menus_user")
        except ValueError:
            hide_group = self.env.ref("spp_hide_menus_base.group_menu_visibility")
        for rec in self:
            if rec.menu_id and hide_group not in rec.menu_id.group_ids:
                rec.default_group_ids = rec.menu_id.group_ids
                rec.menu_id.write({"group_ids": [Command.set([hide_group.id])]})

    def show_menu(self):
        for rec in self:
            if rec.state == "hide" and rec.menu_id:
                rec.menu_id.group_ids = rec.default_group_ids
                rec.state = "show"
