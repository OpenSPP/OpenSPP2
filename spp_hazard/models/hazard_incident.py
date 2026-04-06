# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging
import uuid as uuid_lib

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# CAP vocabulary namespace URIs
CAP_SEVERITY_NS = "urn:oasis:names:tc:cap:severity"
CAP_URGENCY_NS = "urn:oasis:names:tc:cap:urgency"
CAP_CERTAINTY_NS = "urn:oasis:names:tc:cap:certainty"
CAP_MSG_TYPE_NS = "urn:oasis:names:tc:cap:msg-type"


class HazardIncident(models.Model):
    """
    Represents a specific hazard incident/event in the OpenSPP system.

    This model captures the details of a hazard event including its
    temporal scope, geographic scope, severity, and status. Examples
    include a specific typhoon, earthquake, or disease outbreak.
    """

    _name = "spp.hazard.incident"
    _description = "Hazard Incident"
    _order = "start_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    uuid = fields.Char(
        default=lambda self: str(uuid_lib.uuid4()),
        readonly=True,
        copy=False,
        index=True,
        help="External identifier for this incident",
    )
    name = fields.Char(
        required=True,
        tracking=True,
        help="Incident identifier (e.g., 'Typhoon Yolanda', 'COVID-19 Pandemic')",
    )
    code = fields.Char(
        required=True,
        tracking=True,
        help="Unique system code for this incident",
    )
    category_id = fields.Many2one(
        "spp.hazard.category",
        string="Hazard Category",
        tracking=True,
        ondelete="restrict",
        domain=[("active", "=", True)],
    )
    description = fields.Html(
        tracking=True,
        help="Narrative details about the incident",
    )
    start_date = fields.Date(
        tracking=True,
        help="When the hazard began",
    )
    end_date = fields.Date(
        tracking=True,
        help="When the hazard ended (leave empty if ongoing)",
    )
    status = fields.Selection(
        [
            ("alert", "Alert"),
            ("active", "Active"),
            ("recovery", "Recovery"),
            ("closed", "Closed"),
        ],
        default="active",
        required=True,
        tracking=True,
        help="Current status of the incident",
    )
    severity_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Severity",
        tracking=True,
        domain=f"[('namespace_uri', '=', '{CAP_SEVERITY_NS}')]",
        help="Overall magnitude/severity of the incident (CAP vocabulary)",
    )

    # CAP (Common Alerting Protocol) fields
    cap_urgency_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Urgency",
        tracking=True,
        domain=f"[('namespace_uri', '=', '{CAP_URGENCY_NS}')]",
        help="CAP urgency: how quickly action is needed",
    )
    cap_certainty_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Certainty",
        tracking=True,
        domain=f"[('namespace_uri', '=', '{CAP_CERTAINTY_NS}')]",
        help="CAP certainty: confidence in the observation or prediction",
    )
    cap_event = fields.Char(
        string="Event Type",
        help="Raw event type from CAP alert (e.g., 'Flood', 'Typhoon'). "
        "Complements the structured category_id field.",
    )
    cap_msg_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Message Type",
        domain=f"[('namespace_uri', '=', '{CAP_MSG_TYPE_NS}')]",
        help="CAP message type: alert (new), update, or cancel",
    )
    effective = fields.Datetime(
        help="When the alert becomes active (CAP effective time)",
    )
    expires = fields.Datetime(
        help="When the alert expires (CAP expiry time)",
    )
    source = fields.Char(
        help="Organization that issued the alert (e.g., 'INAM Mozambique')",
    )
    source_alert_id = fields.Char(
        index=True,
        help="External alert reference ID from the EWS (e.g., 'MOZ-FLOOD-2026-042'). "
        "Used for duplicate detection on API create.",
    )
    is_ongoing = fields.Boolean(
        compute="_compute_is_ongoing",
        store=True,
        help="Whether this incident is currently ongoing",
    )

    # Geographic scope
    area_ids = fields.Many2many(
        "spp.area",
        "spp_hazard_incident_area_rel",
        "incident_id",
        "area_id",
        string="Affected Areas",
        help="Geographic areas affected by this incident",
    )
    incident_area_ids = fields.One2many(
        "spp.hazard.incident.area",
        "incident_id",
        string="Area Details",
        help="Detailed area-specific information for this incident",
    )
    area_count = fields.Integer(
        compute="_compute_area_count",
        string="Number of Areas",
    )

    # Impact tracking
    impact_ids = fields.One2many(
        "spp.hazard.impact",
        "incident_id",
        string="Impacts",
    )
    impact_count = fields.Integer(
        compute="_compute_impact_count",
        string="Number of Impacts",
    )

    # Computed metrics
    affected_registrant_count = fields.Integer(
        compute="_compute_affected_registrant_count",
        string="Affected Registrants",
    )

    _code_unique = models.Constraint(
        "unique (code)",
        "An incident with this code already exists!",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-populate start_date/end_date from effective/expires if not set."""
        for vals in vals_list:
            if not vals.get("start_date") and vals.get("effective"):
                effective = vals["effective"]
                if isinstance(effective, str):
                    effective = fields.Datetime.from_string(effective)
                vals["start_date"] = effective.date()
            if not vals.get("end_date") and vals.get("expires"):
                expires = vals["expires"]
                if isinstance(expires, str):
                    expires = fields.Datetime.from_string(expires)
                vals["end_date"] = expires.date()
        return super().create(vals_list)

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        """Validate that end_date is after start_date if provided."""
        for rec in self:
            if rec.end_date and rec.start_date and rec.end_date < rec.start_date:
                raise ValidationError(_("End date must be after start date."))

    @api.depends("end_date", "status")
    def _compute_is_ongoing(self):
        """Compute whether the incident is ongoing."""
        for rec in self:
            rec.is_ongoing = not rec.end_date and rec.status in (
                "alert",
                "active",
                "recovery",
            )

    @api.depends("area_ids")
    def _compute_area_count(self):
        """Compute the number of affected areas."""
        for rec in self:
            rec.area_count = len(rec.area_ids)

    @api.depends("impact_ids")
    def _compute_impact_count(self):
        """Compute the number of impact records."""
        for rec in self:
            rec.impact_count = len(rec.impact_ids)

    @api.depends("impact_ids.registrant_id")
    def _compute_affected_registrant_count(self):
        """Compute the number of unique affected registrants."""
        for rec in self:
            rec.affected_registrant_count = len(rec.impact_ids.mapped("registrant_id"))

    def action_set_active(self):
        """Set incident status to active."""
        self.write({"status": "active"})

    def action_set_recovery(self):
        """Set incident status to recovery."""
        self.write({"status": "recovery"})

    def action_close(self):
        """Close the incident."""
        self.write(
            {
                "status": "closed",
                "end_date": self.end_date or fields.Date.today(),
            }
        )

    def action_view_impacts(self):
        """Open a list view of impacts for this incident."""
        self.ensure_one()
        return {
            "name": _("Impacts - %s", self.name),
            "type": "ir.actions.act_window",
            "res_model": "spp.hazard.impact",
            "view_mode": "list,form",
            "domain": [("incident_id", "=", self.id)],
            "context": {"default_incident_id": self.id},
        }

    def action_view_areas(self):
        """Open a list view of affected areas."""
        self.ensure_one()
        return {
            "name": _("Affected Areas - %s", self.name),
            "type": "ir.actions.act_window",
            "res_model": "spp.area",
            "view_mode": "list,form",
            "domain": [("id", "in", self.area_ids.ids)],
        }

    def identify_potentially_affected_registrants(self):
        """
        Find all registrants located in the affected areas.

        Returns a recordset of res.partner records that are potentially
        affected based on their location in the incident's geographic scope.
        """
        self.ensure_one()
        if not self.area_ids:
            return self.env["res.partner"].browse()

        # Find registrants in affected areas
        return self.env["res.partner"].search(
            [
                ("is_registrant", "=", True),
                ("area_id", "in", self.area_ids.ids),
            ]
        )


class HazardIncidentArea(models.Model):
    """
    Links an incident to a specific area with area-specific details.

    This model allows for area-specific severity overrides and
    additional details for each geographic area affected by an incident.
    """

    _name = "spp.hazard.incident.area"
    _description = "Hazard Incident Area"
    _order = "incident_id, area_id"

    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        required=True,
        ondelete="cascade",
        index=True,
    )
    area_id = fields.Many2one(
        "spp.area",
        string="Area",
        required=True,
        ondelete="restrict",
        index=True,
    )
    severity_override_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Severity Override",
        domain=f"[('namespace_uri', '=', '{CAP_SEVERITY_NS}')]",
        help="Area-specific severity (overrides incident-wide severity)",
    )
    notes = fields.Text(
        help="Additional notes about the impact on this area",
    )
    affected_population_estimate = fields.Integer(
        help="Estimated number of people affected in this area",
    )

    _incident_area_unique = models.Constraint(
        "unique (incident_id, area_id)",
        "This area is already linked to this incident!",
    )

    def name_get(self):
        """Return a descriptive name for the record."""
        # Prefetch related records to avoid N+1 queries
        self.mapped("incident_id")
        self.mapped("area_id")
        result = []
        for rec in self:
            name = f"{rec.incident_id.name} - {rec.area_id.name}"
            result.append((rec.id, name))
        return result
