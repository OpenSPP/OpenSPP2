# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Geofence model for saved geographic areas of interest."""

import json
import logging
import uuid

import psycopg2
from psycopg2 import sql
from shapely.geometry import mapping

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class GisGeofenceTag(models.Model):
    """Tags for classifying geofences."""

    _name = "spp.gis.geofence.tag"
    _description = "Geofence Tag"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    color = fields.Integer(string="Color Index")
    active = fields.Boolean(default=True)


class GisGeofence(models.Model):
    """Saved Geographic Areas of Interest.

    Geofences are user-defined polygons that can be:
    - Created from QGIS plugin
    - Used for spatial queries and reports
    - Tagged for classification
    """

    _name = "spp.gis.geofence"
    _description = "Geographic Area of Interest"
    _order = "name"

    uuid = fields.Char(
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False,
        index=True,
        help="External identifier for this geofence",
    )
    name = fields.Char(
        required=True,
        help="Name of this geofence",
    )
    description = fields.Text(
        help="Description of this area of interest",
    )

    # Geometry field using GeoPolygonField from spp_gis
    geometry = fields.GeoPolygonField(
        string="Geographic Polygon",
        required=True,
        help="Geographic boundary as polygon or multipolygon",
    )

    # Classification
    geofence_type = fields.Selection(
        [
            ("area_of_interest", "Area of Interest"),
            ("custom", "Custom Area"),
        ],
        default="custom",
        required=True,
        help="Type of geofence",
    )

    # Tags for flexible classification
    tag_ids = fields.Many2many(
        "spp.gis.geofence.tag",
        "spp_gis_geofence_tag_rel",
        "geofence_id",
        "tag_id",
        string="Tags",
        help="Classification tags for this geofence",
    )

    # Status
    active = fields.Boolean(
        default=True,
        help="Uncheck to archive this geofence",
    )

    created_from = fields.Selection(
        [
            ("qgis", "QGIS Plugin"),
            ("api", "External API"),
            ("ui", "OpenSPP UI"),
        ],
        default="ui",
        required=True,
        string="Created From",
        help="Source of geofence creation",
    )

    # Computed area in square kilometers
    area_sqkm = fields.Float(
        string="Area (sq km)",
        compute="_compute_area_sqkm",
        store=True,
        help="Area of the polygon in square kilometers (computed from geometry)",
    )

    @api.depends("geometry")
    def _compute_area_sqkm(self):
        """Compute area in square kilometers from geometry using PostGIS.

        Uses ST_Area with geography type for accurate area calculation
        in square meters, then converts to square kilometers.
        """
        records_with_geom = self.filtered(lambda r: r.geometry and r.id)
        records_without = self - records_with_geom

        for rec in records_without:
            rec.area_sqkm = 0.0

        if not records_with_geom:
            return

        try:
            # Batch query: compute area for all records with geometry in one roundtrip
            query = sql.SQL(
                "SELECT id, ST_Area(ST_Transform(geometry::geometry, 4326)::geography) / 1000000.0 "
                "FROM {} WHERE id IN %s"
            ).format(sql.Identifier(self._table))
            self.env.cr.execute(query, (tuple(records_with_geom.ids),))
            results = dict(self.env.cr.fetchall())
            for rec in records_with_geom:
                rec.area_sqkm = results.get(rec.id, 0.0)
        except psycopg2.Error as e:
            _logger.warning("Failed to compute area for geofences %s: %s", records_with_geom.ids, str(e))
            for rec in records_with_geom:
                rec.area_sqkm = 0.0

    @api.constrains("name", "active")
    def _check_name_unique_active(self):
        """Ensure name is unique among active geofences."""
        for rec in self:
            if rec.active:
                existing = self.search(
                    [
                        ("name", "=", rec.name),
                        ("active", "=", True),
                        ("id", "!=", rec.id),
                    ],
                    limit=1,
                )
                if existing:
                    raise ValidationError(
                        _("A geofence with the name '%s' already exists. Please use a unique name.") % rec.name
                    )

    @api.constrains("geometry")
    def _check_geometry_valid(self):
        """Validate that geometry is not empty and is a valid polygon."""
        for rec in self:
            if not rec.geometry:
                raise ValidationError(_("Geometry cannot be empty."))

            # Geometry validity is handled by the GeoPolygonField itself
            # We just ensure it exists and is not empty

    def to_geojson(self):
        """Return GeoJSON Feature representation of this geofence.

        Returns:
            dict: GeoJSON Feature with geometry and properties
        """
        self.ensure_one()

        if not self.geometry:
            return {
                "type": "Feature",
                "geometry": None,
                "properties": self._get_geojson_properties(),
            }

        # Convert shapely geometry to GeoJSON
        try:
            geometry_dict = mapping(self.geometry)
        except (ValueError, TypeError, AttributeError) as e:
            _logger.warning("Failed to convert geometry to GeoJSON for geofence %s: %s", self.id, str(e))
            geometry_dict = None

        return {
            "type": "Feature",
            "geometry": geometry_dict,
            "properties": self._get_geojson_properties(),
        }

    def _get_geojson_properties(self):
        """Get properties dictionary for GeoJSON representation.

        Returns:
            dict: Properties including uuid, name, type, tags, etc.
        """
        self.ensure_one()

        return {
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description or "",
            "geofence_type": self.geofence_type,
            "geofence_type_label": dict(self._fields["geofence_type"].selection).get(self.geofence_type, ""),
            "area_sqkm": self.area_sqkm,
            "tags": self.tag_ids.mapped("name"),
            "created_from": self.created_from,
            "created_by": self.create_uid.name,
            "create_date": self.create_date.isoformat() if self.create_date else None,
        }

    def to_geojson_collection(self):
        """Return GeoJSON FeatureCollection for multiple geofences.

        Returns:
            dict: GeoJSON FeatureCollection with all features
        """
        # Prefetch related fields to avoid N+1 queries on singletons
        self.mapped("tag_ids.name")
        self.mapped("create_uid.name")
        features = [rec.to_geojson() for rec in self]
        return {
            "type": "FeatureCollection",
            "features": features,
        }

    @api.model
    def create_from_geojson(self, geojson_str, name, geofence_type="custom", created_from="api", **kwargs):
        """Create a geofence from GeoJSON string.

        Args:
            geojson_str: GeoJSON string (Feature or FeatureCollection)
            name: Name for the geofence
            geofence_type: Type of geofence (default: custom)
            created_from: Source of creation (default: api)
            **kwargs: Additional field values

        Returns:
            Created geofence record

        Raises:
            ValidationError: If GeoJSON is invalid
        """
        try:
            geojson_data = json.loads(geojson_str) if isinstance(geojson_str, str) else geojson_str
        except json.JSONDecodeError as e:
            raise ValidationError(_("Invalid GeoJSON format: %s") % str(e)) from e

        # Handle FeatureCollection or Feature
        if geojson_data.get("type") == "FeatureCollection":
            if not geojson_data.get("features"):
                raise ValidationError(_("FeatureCollection must contain at least one feature"))
            # Use first feature's geometry
            geometry = geojson_data["features"][0].get("geometry")
        elif geojson_data.get("type") == "Feature":
            geometry = geojson_data.get("geometry")
        else:
            # Assume it's a raw geometry
            geometry = geojson_data

        if not geometry:
            raise ValidationError(_("No geometry found in GeoJSON"))

        # Convert geometry dict to GeoJSON string for the GeoPolygonField
        geometry_str = json.dumps(geometry)

        vals = {
            "name": name,
            "geometry": geometry_str,
            "geofence_type": geofence_type,
            "created_from": created_from,
        }
        vals.update(kwargs)

        return self.create(vals)
