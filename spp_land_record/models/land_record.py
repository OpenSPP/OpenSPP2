import json
import logging

import pyproj
from shapely.geometry import mapping
from shapely.ops import transform

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class LandRecord(models.Model):
    _name = "spp.land.record"
    _description = "Land Record Details"
    _inherit = ["mail.thread"]
    _record_name = "land_name"

    land_farm_id = fields.Many2one("res.partner", string="Farm")
    land_name = fields.Char(string="Parcel Name/ID")
    land_acreage = fields.Float()

    # TODO: Change to geo_point and geo_polygon
    land_coordinates = fields.GeoPointField()
    land_geo_polygon = fields.GeoPolygonField(string="Land Polygons")

    land_use_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Land Use",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:land-use')]",
        help="Type of land use for this parcel",
    )

    # Computed field for backward compatibility during transition
    land_use = fields.Char(
        string="Land Use Code",
        compute="_compute_land_use",
        store=True,
        help="Deprecated: Use land_use_id instead",
    )

    @api.depends("land_use_id", "land_use_id.code")
    def _compute_land_use(self):
        for record in self:
            record.land_use = record.land_use_id.code if record.land_use_id else False

    owner_id = fields.Many2one("res.partner")
    lessee_id = fields.Many2one("res.partner")

    lease_start = fields.Date()
    lease_end = fields.Date()

    @api.constrains("lease_start", "lease_end")
    def _check_lease_dates(self):
        for record in self:
            if record.lease_start and record.lease_end and record.lease_end < record.lease_start:
                raise ValidationError(_("Lease End date cannot be earlier than Lease Start date."))

    @api.onchange("lease_start")
    def _onchange_lease_start(self):
        if self.lease_start and self.lease_end and self.lease_start > self.lease_end:
            self.lease_start = False
            return {
                "warning": {
                    "title": _("Invalid Lease Date"),
                    "message": _("Lease Start cannot be later than Lease End. The value has been cleared."),
                }
            }

    @api.onchange("lease_end")
    def _onchange_lease_end(self):
        if self.lease_start and self.lease_end and self.lease_end < self.lease_start:
            self.lease_end = False
            return {
                "warning": {
                    "title": _("Invalid Lease Date"),
                    "message": _("Lease End cannot be earlier than Lease Start. The value has been cleared."),
                }
            }

    def _process_record_to_feature(self, record, geometry_type, transformer):
        """
        Convert a record to a GeoJSON feature using shapely and geojson libraries.

        Args:
            record: The record to process.
            geometry_type: The type of geometry to process ('point', 'polygon', or 'all').
            transformer: The transformer to use for the projection.

        Returns:
            A GeoJSON feature dictionary or None if no valid geometry found.
        """
        # Initialize the feature dictionary with properties
        feature = {
            "type": "Feature",
            "properties": {
                "land_name": record.land_name,
                "land_use": record.land_use,
                "land_use_display": record.land_use_id.display if record.land_use_id else None,
                "land_acreage": record.land_acreage,
            },
        }

        # Process polygon geometry with priority
        if geometry_type in ["polygon", "all"] and record.land_geo_polygon:
            # Assuming land_geo_polygon is a shapely object
            feature["geometry"] = mapping(transform(transformer, record.land_geo_polygon))
        # Fallback to point geometry if requested or no polygon is available
        elif geometry_type in ["point", "all"] and record.land_coordinates:
            feature["geometry"] = mapping(transform(transformer, record.land_coordinates))

        else:
            # No valid geometry found based on the preferences
            return None

        return feature

    @api.model
    def get_geojson(self, geometry_type="all", from_srid=3857, to_srid=4326):
        """
        Generate a GeoJSON representation of land records.

        :param geometry_type: A string specifying the type of geometry to include ('point', 'polygon', or 'all').
        :return: A GeoJSON string of land records.
        """
        search_domain = self._get_search_domain_by_geometry_type(geometry_type)
        land_records = self.search(search_domain)

        # Construct GeoJSON structure
        geojson = {"type": "FeatureCollection", "features": []}

        proj_from = pyproj.Proj(f"epsg:{from_srid}")
        proj_to = pyproj.Proj(f"epsg:{to_srid}")
        transformer = pyproj.Transformer.from_proj(proj_from, proj_to, always_xy=True).transform

        for record in land_records:
            feature = self._process_record_to_feature(record, geometry_type, transformer)
            if feature:
                geojson["features"].append(feature)

        return json.dumps(geojson, indent=2)

    def _get_search_domain_by_geometry_type(self, geometry_type):
        """
        Determine the search domain based on the requested geometry type.

        :param geometry_type: The geometry type ('point', 'polygon', or 'all').
        :return: A search domain for the ORM.
        """
        # if geometry_type == 'point':
        #     return [('land_coordinates', '!=', False)]
        # elif geometry_type == 'polygon':
        #     return [('land_geo_polygon', '!=', False)]
        # else:  # 'all'
        #     return ['|', ('land_coordinates', '!=', False), ('land_geo_polygon', '!=', False)]
        return []
