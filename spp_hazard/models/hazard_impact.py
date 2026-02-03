# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HazardImpact(models.Model):
    """
    Records the impact of a hazard incident on a specific registrant.

    This model captures how a registrant was affected by an incident,
    including the type of impact, severity/damage level, verification
    status, and other relevant details.
    """

    _name = "spp.hazard.impact"
    _description = "Hazard Impact"
    _order = "impact_date desc, incident_id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        required=True,
        ondelete="cascade",
        tracking=True,
        index=True,
    )
    registrant_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        required=True,
        ondelete="cascade",
        tracking=True,
        index=True,
        domain=[("is_registrant", "=", True)],
    )
    impact_type_id = fields.Many2one(
        "spp.hazard.impact.type",
        string="Impact Type",
        required=True,
        tracking=True,
        ondelete="restrict",
        domain=[("active", "=", True)],
    )
    damage_level = fields.Selection(
        [
            ("minimal", "Minimal"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
            ("critical", "Critical"),
            ("partially_damaged", "Partially Damaged"),
            ("totally_damaged", "Totally Damaged"),
        ],
        required=True,
        tracking=True,
        help="Severity of the damage or impact",
    )
    impact_date = fields.Date(
        required=True,
        tracking=True,
        help="Date when the impact occurred (may differ from incident start)",
    )
    verification_status = fields.Selection(
        [
            ("reported", "Reported"),
            ("verified", "Verified"),
            ("disputed", "Disputed"),
            ("closed", "Closed"),
        ],
        default="reported",
        required=True,
        tracking=True,
        help="Current verification status of this impact record",
    )
    notes = fields.Text(
        tracking=True,
        help="Additional details about the impact",
    )
    verified_by_id = fields.Many2one(
        "res.users",
        string="Verified By",
        tracking=True,
        readonly=True,
        help="User who verified this impact",
    )
    verified_date = fields.Datetime(
        string="Verification Date",
        tracking=True,
        readonly=True,
        help="Date and time when the impact was verified",
    )

    # Related fields for display
    incident_name = fields.Char(
        related="incident_id.name",
        string="Incident Name",
        store=True,
    )
    incident_status = fields.Selection(
        related="incident_id.status",
        string="Incident Status",
        store=True,
    )
    registrant_name = fields.Char(
        related="registrant_id.name",
        string="Registrant Name",
        store=True,
    )
    impact_type_category = fields.Selection(
        related="impact_type_id.category",
        string="Impact Category",
        store=True,
    )

    _incident_registrant_type_unique = models.Constraint(
        "unique (incident_id, registrant_id, impact_type_id)",
        "This registrant already has an impact of this type for this incident!",
    )

    @api.constrains("impact_date", "incident_id")
    def _check_impact_date(self):
        """Validate that impact_date is not before the incident start_date."""
        # Prefetch incidents to avoid N+1 queries
        self.mapped("incident_id")
        for rec in self:
            if rec.impact_date and rec.incident_id.start_date:
                if rec.impact_date < rec.incident_id.start_date:
                    raise ValidationError(_("Impact date cannot be before the incident start date."))

    @api.onchange("incident_id")
    def _onchange_incident_id(self):
        """Set default impact_date to incident start_date."""
        if self.incident_id and not self.impact_date:
            self.impact_date = self.incident_id.start_date

    def action_verify(self):
        """Mark the impact as verified."""
        self.write(
            {
                "verification_status": "verified",
                "verified_by_id": self.env.user.id,
                "verified_date": fields.Datetime.now(),
            }
        )

    def action_dispute(self):
        """Mark the impact as disputed."""
        self.write(
            {
                "verification_status": "disputed",
            }
        )

    def action_close(self):
        """Close the impact record."""
        self.write(
            {
                "verification_status": "closed",
            }
        )

    def action_reset_to_reported(self):
        """Reset the verification status to reported."""
        self.write(
            {
                "verification_status": "reported",
                "verified_by_id": False,
                "verified_date": False,
            }
        )

    @api.model
    def bulk_create_impacts(self, incident, area, impact_type, damage_level):
        """
        Create impact records for all registrants in an area.

        This is a utility method for quickly creating impact records
        when an area is known to be affected.

        :param incident: spp.hazard.incident record
        :param area: spp.area record
        :param impact_type: spp.hazard.impact.type record
        :param damage_level: string damage level selection value
        :return: created spp.hazard.impact recordset
        """
        # Find all registrants in the area
        registrants = self.env["res.partner"].search(
            [
                ("is_registrant", "=", True),
                ("area_id", "=", area.id),
            ]
        )

        # Find existing impacts for this incident/type to avoid duplicates
        existing_impacts = self.search(
            [
                ("incident_id", "=", incident.id),
                ("impact_type_id", "=", impact_type.id),
                ("registrant_id", "in", registrants.ids),
            ]
        )
        existing_registrant_ids = existing_impacts.mapped("registrant_id").ids

        # Create impacts for registrants without existing records
        vals_list = []
        for registrant in registrants:
            if registrant.id not in existing_registrant_ids:
                vals_list.append(
                    {
                        "incident_id": incident.id,
                        "registrant_id": registrant.id,
                        "impact_type_id": impact_type.id,
                        "damage_level": damage_level,
                        "impact_date": incident.start_date,
                        "verification_status": "reported",
                    }
                )

        if vals_list:
            return self.create(vals_list)
        return self.browse()
