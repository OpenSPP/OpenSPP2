# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SppProgram(models.Model):
    """
    Extends spp.program to add hazard/emergency response capabilities.

    This extension links programs to hazard incidents, enabling:
    - Emergency program eligibility based on hazard impacts
    - Targeting of affected populations
    - Emergency mode with relaxed compliance rules
    """

    _inherit = "spp.program"

    target_incident_ids = fields.Many2many(
        "spp.hazard.incident",
        "spp_program_hazard_incident_rel",
        "program_id",
        "incident_id",
        string="Target Incidents",
        help="Incidents this program responds to. Registrants with verified "
        "impacts from these incidents may be eligible for this program.",
    )
    is_emergency_program = fields.Boolean(
        compute="_compute_is_emergency_program",
        store=True,
        help="Whether this program is responding to any active emergency incidents",
    )
    qualifying_damage_levels = fields.Selection(
        [
            ("any", "Any Damage Level"),
            ("moderate_up", "Moderate and Above"),
            ("severe_up", "Severe and Above"),
            ("critical_only", "Critical/Totally Damaged Only"),
        ],
        default="any",
        help="Minimum damage level required for emergency eligibility",
    )
    is_emergency_mode = fields.Boolean(
        string="Emergency Mode",
        default=False,
        help="When enabled, relaxed compliance rules apply for this program. "
        "Automatically enabled when linked to active incidents.",
    )
    target_incident_count = fields.Integer(
        compute="_compute_target_incident_count",
        string="Number of Target Incidents",
        store=True,
    )
    affected_registrant_count = fields.Integer(
        compute="_compute_affected_registrant_count",
        string="Potentially Affected Registrants",
    )

    @api.depends("target_incident_ids")
    def _compute_target_incident_count(self):
        """Compute the number of target incidents."""
        for rec in self:
            rec.target_incident_count = len(rec.target_incident_ids)

    @api.depends("target_incident_ids.status")
    def _compute_is_emergency_program(self):
        """Compute whether this is an emergency program based on linked incidents."""
        for rec in self:
            rec.is_emergency_program = bool(
                rec.target_incident_ids.filtered(lambda i: i.status in ("alert", "active", "recovery"))
            )

    @api.depends("target_incident_ids", "qualifying_damage_levels")
    def _compute_affected_registrant_count(self):
        """Compute the number of potentially affected registrants."""
        for rec in self:
            if not rec.target_incident_ids:
                rec.affected_registrant_count = 0
                continue

            # Build domain for qualifying damage levels
            damage_domain = rec._get_damage_level_domain()

            # Count unique registrants with qualifying impacts, aggregated in
            # SQL so no impact rows are loaded into memory.
            # sudo: emergency-program eligibility must consider all qualifying
            # impacts regardless of the viewing user's hazard access; impact rows
            # are not exposed, only the aggregate count.
            impact_sudo = self.env["spp.hazard.impact"].sudo()  # nosemgrep: odoo-sudo-without-context
            [(count,)] = impact_sudo._read_group(
                [
                    ("incident_id", "in", rec.target_incident_ids.ids),
                    ("verification_status", "=", "verified"),
                ]
                + damage_domain,
                aggregates=["registrant_id:count_distinct"],
            )
            rec.affected_registrant_count = count

    def _get_damage_level_domain(self):
        """Get the domain filter for qualifying damage levels."""
        self.ensure_one()
        if self.qualifying_damage_levels == "any":
            return []
        elif self.qualifying_damage_levels == "moderate_up":
            return [("damage_level", "in", ("moderate", "severe", "critical", "partially_damaged", "totally_damaged"))]
        elif self.qualifying_damage_levels == "severe_up":
            return [("damage_level", "in", ("severe", "critical", "totally_damaged"))]
        elif self.qualifying_damage_levels == "critical_only":
            return [("damage_level", "in", ("critical", "totally_damaged"))]
        return []

    def get_emergency_eligible_registrants(self):
        """
        Get registrants eligible for this emergency program based on hazard impacts.

        Returns registrants who:
        - Have verified impact from one of the target incidents
        - Meet the qualifying damage level threshold

        :return: recordset of res.partner
        """
        self.ensure_one()
        if not self.target_incident_ids:
            return self.env["res.partner"].browse()

        damage_domain = self._get_damage_level_domain()

        # Find the unique registrants of qualifying impacts, grouped in SQL so
        # no impact rows are loaded into memory.
        # sudo: eligibility must consider all qualifying impacts regardless of the
        # viewing user's hazard access; only the resulting registrants are returned.
        impact_sudo = self.env["spp.hazard.impact"].sudo()  # nosemgrep: odoo-sudo-without-context
        groups = impact_sudo._read_group(
            [
                ("incident_id", "in", self.target_incident_ids.ids),
                ("verification_status", "=", "verified"),
            ]
            + damage_domain,
            groupby=["registrant_id"],
        )

        # Return the registrants in the caller's env (not the sudo one).
        return self.env["res.partner"].browse([registrant.id for (registrant,) in groups if registrant])

    def action_view_target_incidents(self):
        """Open a list view of target incidents."""
        self.ensure_one()
        return {
            "name": _("Target Incidents - %s", self.name),
            "type": "ir.actions.act_window",
            "res_model": "spp.hazard.incident",
            "view_mode": "list,form",
            "domain": [("id", "in", self.target_incident_ids.ids)],
            "context": {},
        }

    def action_view_affected_registrants(self):
        """Open a list view of potentially affected registrants."""
        self.ensure_one()
        registrants = self.get_emergency_eligible_registrants()
        return {
            "name": _("Affected Registrants - %s", self.name),
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [("id", "in", registrants.ids)],
            "context": {},
        }
