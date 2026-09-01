# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .demo_setup import PROGRAM_NAME, create_demo_environment

_logger = logging.getLogger(__name__)

LOCALIZATION_ATTACHMENT = "child_benefit_demo_localization.json"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    demo_environment_ready = fields.Boolean(
        string="Demo Environment Created",
        compute="_compute_demo_environment_ready",
        help="Whether the demonstration programme and its registrants already exist.",
    )
    demo_beneficiary_count = fields.Integer(
        string="Enrolled Beneficiaries",
        compute="_compute_demo_environment_ready",
    )
    demo_localization_file = fields.Binary(
        string="Localization Pack",
        help="Optional JSON pack that renames the demonstration data into a "
        "country's own programme name, currency, banks, areas and people.",
    )
    demo_localization_filename = fields.Char()

    @api.depends_context("uid")
    def _compute_demo_environment_ready(self):
        demo_program = self.env["spp.program"].search_count([("name", "=", PROGRAM_NAME)])
        # The programme may have been renamed by a localization pack, so fall
        # back to the schedules the demo generator creates.
        schedules = self.env["spp.entitlement.schedule"].search_count([("state", "=", "active")])
        for rec in self:
            rec.demo_environment_ready = bool(demo_program or schedules)
            rec.demo_beneficiary_count = schedules

    def _check_demo_superuser(self):
        """Demo tooling creates users and bulk registrant data: restrict it to
        a system administrator, not merely someone who can open Settings."""
        if not self.env.is_admin():
            raise AccessError(_("Only a system administrator may manage the demonstration environment."))

    def action_create_demo_environment(self):
        self.ensure_one()
        self._check_demo_superuser()
        created = create_demo_environment(self.env)
        if not created:
            return self._notify(_("Demonstration environment already exists — nothing to create."), "warning")
        self._apply_stored_localization()
        return self._notify(_("Demonstration environment created."), "success")

    def action_apply_demo_localization(self):
        self.ensure_one()
        self._check_demo_superuser()
        if self.demo_localization_file:
            raw = base64.b64decode(self.demo_localization_file).decode("utf-8")
            self._store_localization(raw)
        else:
            raw = self._stored_localization()
            if not raw:
                raise UserError(_("Upload a localization pack first."))
        summary = self.env["spp.demo.localization"].apply_pack(raw)
        return self._notify(_("Localization applied: %s") % (", ".join(summary) or _("nothing matched")), "success")

    # ------------------------------------------------------------------
    # Stored pack (survives the transient settings record)
    # ------------------------------------------------------------------
    def _localization_attachment(self):
        return (
            self.env["ir.attachment"]
            .sudo()
            .search([("name", "=", LOCALIZATION_ATTACHMENT), ("res_model", "=", "res.config.settings")], limit=1)
        )

    def _store_localization(self, raw):
        attachment = self._localization_attachment()
        datas = base64.b64encode(raw.encode("utf-8"))
        if attachment:
            attachment.datas = datas
        else:
            self.env["ir.attachment"].sudo().create(
                {
                    "name": LOCALIZATION_ATTACHMENT,
                    "res_model": "res.config.settings",
                    "type": "binary",
                    "mimetype": "application/json",
                    "datas": datas,
                }
            )

    def _stored_localization(self):
        attachment = self._localization_attachment()
        return base64.b64decode(attachment.datas).decode("utf-8") if attachment else None

    def _apply_stored_localization(self):
        raw = self._stored_localization()
        if raw:
            self.env["spp.demo.localization"].apply_pack(raw)

    def _notify(self, message, kind):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Demonstration Environment"),
                "message": message,
                "type": kind,
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
