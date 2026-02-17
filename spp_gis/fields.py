import json
import logging

from odoo import _, api, fields
from odoo.exceptions import ValidationError
from odoo.tools import sql

_logger = logging.getLogger(__name__)

try:
    import geojson
    from pyproj import Transformer
    from shapely.geometry import LineString, MultiPolygon, Point, Polygon, shape
    from shapely.geometry.base import BaseGeometry
    from shapely.ops import transform
    from shapely.wkb import loads as wkbloads
    from shapely.wkt import loads as wktloads
except ImportError:
    _logger.warning("Geospatial libraries not available.")

geo_types = {}


def transform_geometry(geometry, from_srid, to_srid):
    transformer = Transformer.from_crs(f"EPSG:{from_srid}", f"EPSG:{to_srid}", always_xy=True)
    return transform(transformer.transform, geometry)  # Using Shapely's transform


def _is_wkb_hex(value):
    """Check if a string is a WKB hex representation.

    WKB hex strings are all hex characters and start with 00 or 01
    (endianness indicator).
    """
    if not isinstance(value, str) or len(value) < 10:
        return False
    # Check first byte is endianness indicator (00 or 01)
    if value[:2] not in ("00", "01"):
        return False
    # Check all characters are valid hex
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def value_to_shape(value, use_wkb=False):
    """Transforms input into a Shapely object"""
    if not value:
        return wktloads("GEOMETRYCOLLECTION EMPTY")
    if isinstance(value, str):
        if "{" in value:
            geo_dict = geojson.loads(value)
            return shape(geo_dict)
        elif use_wkb or _is_wkb_hex(value):
            return wkbloads(value, hex=True)
        else:
            return wktloads(value)
    elif hasattr(value, "wkt"):
        if isinstance(value, BaseGeometry):
            return value
        else:
            return wktloads(value.wkt)
    else:
        raise TypeError(_("Write/create/search geo type must be wkt/geojson string or must respond to wkt"))


def load_geojson(value):
    result = json.loads(value)
    if not isinstance(result, dict):
        raise ValidationError(_("Value should be a geojson"))
    return result


def validate_geojson(geojson):
    if "coordinates" not in geojson or "type" not in geojson:
        raise ValidationError(_("type and coordinates should be in the geojson"))
    elif geojson["type"] not in geo_types:
        raise ValidationError(_("%(geo_type)s is not a valid type.") % {"geo_type": geojson["type"]})


def validate_shapely_geometry(shapely_geometry):
    if shapely_geometry.is_empty:
        raise ValidationError(_("Geometry is empty."))


class GeoField(fields.Field):
    """
    Base class for geospatial fields, handling common attributes and methods.
    """

    _type = "geo"
    geo_type = None  # To be defined in subclasses
    geo_class = None  # To be defined in subclasses
    srid = 4326  # Default SRID, can be overridden in subclasses
    column_type = ("geometry", "geometry")
    dim = 2

    # Define supported GIS operators at the field level
    _gis_operators = {
        "gis_intersects",
        "gis_contains",
        "gis_within",
        "gis_touches",
        "gis_crosses",
        "gis_equals",
        "gis_disjoint",
        "gis_covers",
        "gis_coveredby",
    }

    def __init__(self, *args, **kwargs):
        # Store our own index flag for GiST index creation
        self._gist_index = kwargs.pop("index", True)
        # Prevent Odoo from creating a btree index (geometry needs GiST)
        kwargs["index"] = False
        if isinstance(self, GeoField) and self.geo_type and self.geo_class:
            geo_types.update({self.geo_type: self.geo_class})
        super().__init__(*args, **kwargs)

    def condition_to_sql(self, field_expr, operator, value, model, alias, query):
        """
        Generate SQL for domain conditions involving this field (Odoo 19 method).

        This method is called by Odoo's domain system when processing domain conditions.
        For GIS operators, we use the Operator class to generate the appropriate PostGIS SQL.
        For standard operators, we delegate to the parent class.

        :param field_expr: Field expression (e.g., 'geo_polygon_field')
        :param operator: The operator (e.g., 'gis_intersects', '=', etc.)
        :param value: The value to compare against
        :param model: The model being queried
        :param alias: Table alias in the SQL query
        :param query: The Query object being built
        :return: SQL object for the comparison
        """
        from odoo.tools import SQL

        from .operators import Operator

        # Check if this is a GIS operator
        if operator in self._gis_operators:
            try:
                operator_obj = Operator(self, table_alias=alias)
                return operator_obj.domain_query(operator, value)
            except Exception as e:
                _logger.error(f"Failed to generate GIS SQL for operator {operator}: {e}")
                # Return a safe fallback that evaluates to False
                return SQL("FALSE")
        else:
            # For non-GIS operators, use the standard field behavior
            return super().condition_to_sql(field_expr, operator, value, model, alias, query)

    def validate_value(self, value):
        try:
            result = load_geojson(value)
            validate_geojson(result)
            shapely_geometry = shape(result)
            validate_shapely_geometry(shapely_geometry)
        except json.JSONDecodeError as e:
            raise ValidationError(e) from e

    @api.model
    def create_geo_column(self, model, column_name):
        table_name = model._table
        cr = model.env.cr
        geo_type = self.geo_type.upper()
        srid = self.srid
        index = self._gist_index
        dim = self.dim
        column_type = f"geometry({geo_type}, {srid})"

        cr.execute(
            "SELECT AddGeometryColumn( %s, %s, %s, %s, %s)",
            (table_name, column_name, srid, geo_type, dim),
        )

        if index:
            index_name = f"{table_name}_{column_name}_gist_index"
            sql.create_index(model.env.cr, index_name, table_name, [column_name], method="GIST")

        _logger.info(f"Geospatial column {column_name} of type {column_type} created in {table_name}.")

    @classmethod
    def transform_geometry_srid(cls, value, from_srid=4326, to_srid=3857, output="json"):
        if value is None:
            return None
        geom = shape(value)  # Assuming value is in GeoJSON-like dict format
        transformed_geom = transform_geometry(geom, from_srid, to_srid)
        if output == "geom":
            return transformed_geom
        return geojson.dumps(transformed_geom)  # Convert back to GeoJSON string

    def convert_to_column(self, value, record, values=None, validate=True):
        if not value:
            return None
        # Skip validation for WKB hex (already validated when originally set)
        if validate and not _is_wkb_hex(value):
            self.validate_value(value)
        shape_to_write = value_to_shape(value)
        if shape_to_write.is_empty:
            return None
        else:
            return f"SRID={self.srid};{shape_to_write.wkt}"

    def convert_to_cache(self, value, record, validate=True):
        val = value
        if isinstance(val, bytes | str):
            try:
                int(val, 16)
            except Exception:
                value = value_to_shape(value, use_wkb=False)
        if isinstance(value, BaseGeometry):
            val = value.wkb_hex
        return val

    def convert_to_record(self, value, record):
        if not value:
            return False
        return value_to_shape(value, use_wkb=True)

    def convert_to_read(self, value, record, use_display_name=True):
        if not isinstance(value, BaseGeometry):
            shape = wkbloads(value, hex=True) if value else False
        else:
            shape = value
        if not shape or shape.is_empty:
            return False
        return geojson.dumps(shape)

    def check_geometry_columns(self, cursor, table_name, column_name, expected_values):
        query = """
            SELECT srid, type, coord_dimension
            FROM geometry_columns
            WHERE f_table_name = %s AND f_geometry_column = %s
        """
        cursor.execute(query, (table_name, column_name))
        return cursor.fetchone() == expected_values

    def update_geometry_columns(self, cursor, table_name, column_name, expected_values):
        if not self.check_geometry_columns(cursor, table_name, column_name, expected_values):
            raise ValidationError(
                f"Geometry column validation failed for table '{table_name}', column '{column_name}'."
            )

    def update_db_column(self, model, column_info):
        cursor = model.env.cr
        table_name = model._table
        column_name = self.name

        if not column_info:
            self.create_geo_column(model, column_name)
            return

        if column_info["udt_name"] == self.column_type[0]:
            return

        expected_geo_values = (self.srid, self.geo_type.upper(), self.dim)
        self.update_geometry_columns(cursor, table_name, column_name, expected_geo_values)


class GeoPointField(GeoField):
    type = "geo_point"
    geo_class = Point
    geo_type = Point.__name__


class GeoLineStringField(GeoField):
    type = "geo_line"
    geo_class = LineString
    geo_type = LineString.__name__


class GeoPolygonField(GeoField):
    """Geospatial field for polygon geometries.

    Supports both Polygon and MultiPolygon geometry types to handle
    areas with islands or disconnected regions (e.g., provinces with
    offshore islands).

    The database column uses generic 'geometry' type to accept both.
    """

    type = "geo_polygon"
    geo_class = Polygon  # Primary class for validation
    geo_type = "Geometry"  # Generic type to accept Polygon and MultiPolygon

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Register both Polygon and MultiPolygon as valid types
        geo_types.update({"Polygon": Polygon, "MultiPolygon": MultiPolygon})


fields.GeoPointField = GeoPointField
fields.GeoLineStringField = GeoLineStringField
fields.GeoPolygonField = GeoPolygonField
