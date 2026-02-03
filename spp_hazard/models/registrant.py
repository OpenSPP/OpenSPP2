# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """
    Extends res.partner to add hazard impact tracking.

    This extension adds fields and methods to track the hazard
    impacts affecting each registrant.
    """

    _inherit = "res.partner"

    hazard_impact_ids = fields.One2many(
        "spp.hazard.impact",
        "registrant_id",
        string="Hazard Impacts",
    )
    hazard_impact_count = fields.Integer(
        compute="_compute_hazard_impact_count",
        string="Impact Count",
        store=True,
    )
    has_active_impact = fields.Boolean(
        compute="_compute_has_active_impact",
        string="Has Active Impact",
        store=True,
        help="Whether the registrant has an impact from an active incident",
    )

    @api.depends("hazard_impact_ids")
    def _compute_hazard_impact_count(self):
        """Compute the number of hazard impacts for this registrant."""
        for rec in self:
            rec.hazard_impact_count = len(rec.hazard_impact_ids)

    @api.depends("hazard_impact_ids", "hazard_impact_ids.incident_id.status")
    def _compute_has_active_impact(self):
        """Compute whether the registrant has an impact from an active incident."""
        for rec in self:
            rec.has_active_impact = bool(
                rec.hazard_impact_ids.filtered(lambda i: i.incident_id.status in ("alert", "active", "recovery"))
            )

    def action_view_hazard_impacts(self):
        """Open a list view of hazard impacts for this registrant."""
        self.ensure_one()
        return {
            "name": _("Hazard Impacts - %s", self.name),
            "type": "ir.actions.act_window",
            "res_model": "spp.hazard.impact",
            "view_mode": "list,form",
            "domain": [("registrant_id", "=", self.id)],
            "context": {"default_registrant_id": self.id},
        }

    def get_impact_history(self):
        """
        Get the impact history for this registrant, ordered by date.

        :return: recordset of spp.hazard.impact ordered by impact_date desc
        """
        self.ensure_one()
        return self.hazard_impact_ids.sorted(key=lambda i: i.impact_date, reverse=True)

    def get_active_incident_impacts(self):
        """
        Get impacts from currently active incidents.

        :return: recordset of spp.hazard.impact for active incidents
        """
        self.ensure_one()
        return self.hazard_impact_ids.filtered(lambda i: i.incident_id.status in ("alert", "active", "recovery"))
