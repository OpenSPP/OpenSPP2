# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


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
        required=True,
        tracking=True,
        ondelete="restrict",
        domain=[("active", "=", True)],
    )
    description = fields.Html(
        tracking=True,
        help="Narrative details about the incident",
    )
    start_date = fields.Date(
        required=True,
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
    severity = fields.Selection(
        [
            ("1", "Level 1 - Minor"),
            ("2", "Level 2 - Moderate"),
            ("3", "Level 3 - Significant"),
            ("4", "Level 4 - Severe"),
            ("5", "Level 5 - Catastrophic"),
        ],
        tracking=True,
        help="Overall magnitude/severity of the incident",
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
    # This aggregate is derived from the sensitive spp.hazard.impact table
    # (registrant-linked) and is computed via raw SQL that bypasses record
    # ACLs. spp.hazard.incident itself stays broadly readable (sibling modules
    # such as spp_drims read incidents), so this field must carry its own
    # group guard: without it, any internal user could read the affected-
    # registrant aggregate over RPC even though they cannot read impact rows.
    affected_registrant_count = fields.Integer(
        compute="_compute_affected_registrant_count",
        string="Affected Registrants",
        groups="spp_hazard.group_hazard_read,spp_registry.group_registry_viewer,spp_security.group_spp_admin",
    )

    _code_unique = models.Constraint(
        "unique (code)",
        "An incident with this code already exists!",
    )

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

    @api.depends("area_ids", "incident_area_ids.area_id")
    def _compute_area_count(self):
        """Compute the number of affected areas from both M2M and detail records."""
        for rec in self:
            detail_areas = rec.incident_area_ids.mapped("area_id")
            all_areas = rec.area_ids | detail_areas
            rec.area_count = len(all_areas)

    @api.depends("impact_ids")
    def _compute_impact_count(self):
        """Compute the number of impact records."""
        data = self.env["spp.hazard.impact"].read_group(
            [("incident_id", "in", self.ids)],
            ["incident_id"],
            ["incident_id"],
        )
        mapped = {d["incident_id"][0]: d["incident_id_count"] for d in data}
        for rec in self:
            rec.impact_count = mapped.get(rec.id, 0)

    @api.depends("impact_ids.registrant_id")
    def _compute_affected_registrant_count(self):
        """Compute the number of unique affected registrants."""
        if not self.ids:
            self.affected_registrant_count = 0
            return
        self.env.cr.execute(
            """
            SELECT incident_id, COUNT(DISTINCT registrant_id)
            FROM spp_hazard_impact
            WHERE incident_id IN %s
            GROUP BY incident_id
            """,
            [tuple(self.ids)],
        )
        mapped = dict(self.env.cr.fetchall())
        for rec in self:
            rec.affected_registrant_count = mapped.get(rec.id, 0)

    def action_set_active(self):
        """Set incident status to active."""
        self.write({"status": "active"})

    def action_set_recovery(self):
        """Set incident status to recovery."""
        self.write({"status": "recovery"})

    def action_close(self):
        """Close the incident."""
        for rec in self:
            rec.write(
                {
                    "status": "closed",
                    "end_date": rec.end_date or fields.Date.today(),
                }
            )
        _logger.info(
            "Closed %d incident(s): %s",
            len(self),
            ", ".join(self.mapped("name")),
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

    def _get_all_area_ids(self):
        """Get all affected area IDs from both M2M and detail records."""
        self.ensure_one()
        detail_areas = self.incident_area_ids.mapped("area_id")
        return (self.area_ids | detail_areas).ids

    def action_view_areas(self):
        """Open a list view of affected areas."""
        self.ensure_one()
        return {
            "name": _("Affected Areas - %s", self.name),
            "type": "ir.actions.act_window",
            "res_model": "spp.area",
            "view_mode": "list,form",
            "domain": [("id", "in", self._get_all_area_ids())],
        }

    def identify_potentially_affected_registrants(self):
        """
        Find all registrants located in the affected areas.

        Returns a recordset of res.partner records that are potentially
        affected based on their location in the incident's geographic scope.
        """
        self.ensure_one()
        all_area_ids = self._get_all_area_ids()
        if not all_area_ids:
            return self.env["res.partner"].browse()

        # Find registrants in affected areas
        return self.env["res.partner"].search(
            [
                ("is_registrant", "=", True),
                ("area_id", "in", all_area_ids),
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
    _rec_name = "display_name"

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
    severity_override = fields.Selection(
        [
            ("1", "Level 1 - Minor"),
            ("2", "Level 2 - Moderate"),
            ("3", "Level 3 - Significant"),
            ("4", "Level 4 - Severe"),
            ("5", "Level 5 - Catastrophic"),
        ],
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

    @api.depends("incident_id.name", "area_id.name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.incident_id.name} - {rec.area_id.name}"
