# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging
import uuid as uuid_lib
from datetime import UTC, datetime

import psycopg2

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# CAP vocabulary namespace URIs
CAP_SEVERITY_NS = "urn:oasis:names:tc:cap:severity"
CAP_URGENCY_NS = "urn:oasis:names:tc:cap:urgency"
CAP_CERTAINTY_NS = "urn:oasis:names:tc:cap:certainty"
CAP_MSG_TYPE_NS = "urn:oasis:names:tc:cap:msg-type"


def _parse_datetime_string(value):
    """Parse a datetime string in either ISO 8601 or Odoo format.

    Handles both '2026-04-01T00:00:00Z' (ISO 8601) and
    '2026-04-01 00:00:00' (Odoo Datetime format).

    Returns:
        datetime object
    """
    # Replace 'Z' with '+00:00' for fromisoformat compatibility
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    # Odoo requires naive (UTC) datetimes
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


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
        help="Raw event type from CAP alert (e.g., 'Flood', 'Typhoon'). Complements the structured category_id field.",
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
                    effective = _parse_datetime_string(effective)
                vals["start_date"] = effective.date()
            if not vals.get("end_date") and vals.get("expires"):
                expires = vals["expires"]
                if isinstance(expires, str):
                    expires = _parse_datetime_string(expires)
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

    # --- Alert ingestion methods ---

    @api.model
    def create_from_alert(self, geometry_dict, properties):
        """Create an incident from an external alert with geometry.

        Creates the incident record, a hazard_zone geofence from the geometry,
        and auto-links intersecting administrative areas.

        Args:
            geometry_dict: GeoJSON geometry (Polygon or MultiPolygon)
            properties: dict with CAP-aligned properties (event, headline,
                severity, urgency, certainty, effective, expires, source,
                source_alert_id, cap_msg_type)

        Returns:
            spp.hazard.incident record
        """
        self._validate_alert_geometry(geometry_dict)
        vals = self._map_alert_properties_to_vals(properties)
        incident = self.create(vals)

        # Create hazard_zone geofence from the alert geometry
        self.env["spp.gis.geofence"].create_from_geojson(
            geojson_str=geometry_dict,
            name=f"Alert zone: {incident.name}",
            geofence_type="hazard_zone",
            created_from="api",
            incident_id=incident.id,
        )

        # Auto-link intersecting admin areas
        incident._link_areas_from_geometry(geometry_dict)

        return incident

    def update_from_alert(self, geometry_dict, properties):
        """Update an existing incident from an alert update.

        Updates incident properties. If geometry_dict is provided, updates
        (or creates) the linked hazard_zone geofence and re-links areas.

        Args:
            geometry_dict: GeoJSON geometry or None (skip geofence update)
            properties: dict with CAP-aligned properties
        """
        self.ensure_one()
        vals = self._map_alert_properties_to_vals(properties)

        if geometry_dict:
            self._validate_alert_geometry(geometry_dict)
            # Find existing hazard_zone geofence for this incident
            # nosemgrep: odoo-sudo-without-context
            geofence = (
                self.env["spp.gis.geofence"]
                .sudo()
                .search(
                    [
                        ("incident_id", "=", self.id),
                        ("geofence_type", "=", "hazard_zone"),
                    ],
                    limit=1,
                    order="create_date",
                )
            )
            if geofence:
                geofence.write({"geometry": json.dumps(geometry_dict)})
            else:
                self.env["spp.gis.geofence"].create_from_geojson(
                    geojson_str=geometry_dict,
                    name=f"Alert zone: {self.name}",
                    geofence_type="hazard_zone",
                    created_from="api",
                    incident_id=self.id,
                )
            # Re-link areas from updated geometry
            self._link_areas_from_geometry(geometry_dict)

        # Handle cancellation: merge close fields into a single write rather
        # than calling action_close() separately (avoids two ORM writes).
        cap_msg_type_id = vals.get("cap_msg_type_id")
        if cap_msg_type_id:
            VocabCode = self.env["spp.vocabulary.code"]
            cancel_code = VocabCode.get_code(CAP_MSG_TYPE_NS, "cancel")
            if cancel_code and cap_msg_type_id == cancel_code.id:
                vals["status"] = "closed"
                vals["end_date"] = self.end_date or fields.Date.today()

        self.write(vals)

    def _validate_alert_geometry(self, geometry_dict):
        """Validate that geometry is Polygon or MultiPolygon.

        Args:
            geometry_dict: GeoJSON geometry dict

        Raises:
            ValidationError: If geometry type is not allowed
        """
        allowed = {"Polygon", "MultiPolygon"}
        geom_type = geometry_dict.get("type", "") if isinstance(geometry_dict, dict) else ""
        if geom_type not in allowed:
            raise ValidationError(_("Alert geometry must be Polygon or MultiPolygon, got '%s'.") % geom_type)

    def _map_alert_properties_to_vals(self, properties):
        """Map CAP-aligned properties dict to incident field values.

        Args:
            properties: dict with keys like event, headline, severity, etc.

        Returns:
            dict: Odoo field values for create/write
        """
        VocabCode = self.env["spp.vocabulary.code"]
        vals = {}

        if "headline" in properties:
            vals["name"] = properties["headline"]
        if "event" in properties:
            vals["cap_event"] = properties["event"]
            # Try to resolve event to a hazard category
            category = self._resolve_category_from_event(properties["event"])
            if category:
                vals["category_id"] = category.id
        if "source" in properties:
            vals["source"] = properties["source"]
        if "source_alert_id" in properties:
            vals["source_alert_id"] = properties["source_alert_id"]
        if "effective" in properties and properties["effective"]:
            vals["effective"] = _parse_datetime_string(properties["effective"])
        if "expires" in properties and properties["expires"]:
            vals["expires"] = _parse_datetime_string(properties["expires"])

        # Resolve vocabulary-backed fields by code
        for prop_key, field_name, namespace in [
            ("severity", "severity_id", CAP_SEVERITY_NS),
            ("urgency", "cap_urgency_id", CAP_URGENCY_NS),
            ("certainty", "cap_certainty_id", CAP_CERTAINTY_NS),
            ("cap_msg_type", "cap_msg_type_id", CAP_MSG_TYPE_NS),
        ]:
            if prop_key in properties and properties[prop_key]:
                code_rec = VocabCode.get_code(namespace, properties[prop_key])
                if code_rec:
                    vals[field_name] = code_rec.id

        # Auto-generate code if not provided (for create)
        if "code" not in vals and "source_alert_id" in properties and properties["source_alert_id"]:
            vals["code"] = properties["source_alert_id"]
        if "code" not in vals:
            vals["code"] = f"INC-{uuid_lib.uuid4().hex[:8].upper()}"

        return vals

    def _resolve_category_from_event(self, event_str):
        """Try to match a CAP event string to a hazard category.

        Searches spp.hazard.category by name or code (case-insensitive).

        Args:
            event_str: Event type string (e.g., "Flood", "Typhoon")

        Returns:
            spp.hazard.category record or None
        """
        if not event_str:
            return None
        Category = self.env["spp.hazard.category"]
        # Try exact match on name first, then code
        category = Category.search([("name", "=ilike", event_str)], limit=1)
        if not category:
            category = Category.search([("code", "=ilike", event_str)], limit=1)
        return category or None

    def _link_areas_from_geometry(self, geometry_dict):
        """Find administrative areas that intersect the geometry and link them.

        Uses PostGIS ST_Intersects to find spp.area records whose polygon
        overlaps the alert geometry. Populates area_ids on the incident.

        Args:
            geometry_dict: GeoJSON geometry dict
        """
        self.ensure_one()
        geojson_str = json.dumps(geometry_dict) if isinstance(geometry_dict, dict) else geometry_dict

        try:
            self.env.cr.execute(
                """
                SELECT id FROM spp_area
                WHERE geo_polygon IS NOT NULL
                AND ST_Intersects(
                    geo_polygon::geometry,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
                )
                """,
                (geojson_str,),
            )
            area_ids = [row[0] for row in self.env.cr.fetchall()]
            if area_ids:
                self.write({"area_ids": [Command.set(area_ids)]})
            else:
                _logger.info(
                    "No intersecting areas found for incident %s",
                    self.code,
                )
        except psycopg2.Error as e:
            _logger.warning(
                "Failed to link areas from geometry for incident %s: %s",
                self.code,
                e,
            )

    def to_geojson(self):
        """Return GeoJSON Feature representation of this incident.

        Geometry is pulled from the first linked hazard_zone geofence.
        Returns null geometry if no geofence is linked.

        Returns:
            dict: GeoJSON Feature
        """
        self.ensure_one()
        return {
            "type": "Feature",
            "id": self.uuid,
            "geometry": self._get_alert_geometry(),
            "properties": self._get_geojson_properties(),
        }

    def _get_alert_geometry(self):
        """Get geometry from the first linked hazard_zone geofence.

        Returns:
            dict: GeoJSON geometry or None
        """
        from shapely.geometry import mapping

        # nosemgrep: odoo-sudo-without-context
        geofence = (
            self.env["spp.gis.geofence"]
            .sudo()
            .search(
                [
                    ("incident_id", "=", self.id),
                    ("geofence_type", "=", "hazard_zone"),
                ],
                limit=1,
                order="create_date",
            )
        )
        if not geofence or not geofence.geometry:
            return None
        try:
            return mapping(geofence.geometry)
        except (ValueError, TypeError, AttributeError) as e:
            _logger.warning(
                "Failed to convert geometry for incident %s geofence %s: %s",
                self.id,
                geofence.id,
                e,
            )
            return None

    def _get_geojson_properties(self):
        """CAP-aligned properties for GeoJSON response.

        Returns:
            dict: Properties dictionary
        """
        self.ensure_one()
        return {
            "code": self.code,
            "event": self.cap_event or (self.category_id.name if self.category_id else None),
            "severity": self.severity_id.code if self.severity_id else None,
            "urgency": self.cap_urgency_id.code if self.cap_urgency_id else None,
            "certainty": self.cap_certainty_id.code if self.cap_certainty_id else None,
            "msg_type": self.cap_msg_type_id.code if self.cap_msg_type_id else None,
            "effective": self.effective.isoformat() if self.effective else None,
            "expires": self.expires.isoformat() if self.expires else None,
            "headline": self.name,
            "source": self.source,
            "source_alert_id": self.source_alert_id,
            "status": self.status,
            "start_date": str(self.start_date) if self.start_date else None,
            "end_date": str(self.end_date) if self.end_date else None,
            "created_at": self.create_date.isoformat() if self.create_date else None,
        }


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

    @api.depends("incident_id.name", "area_id.name")
    def _compute_display_name(self):
        """Compute a descriptive display name for the record."""
        for rec in self:
            rec.display_name = f"{rec.incident_id.name} - {rec.area_id.name}"
