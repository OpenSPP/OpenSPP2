# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SppAreaHdx(models.Model):
    """
    Extend spp.area with HDX integration fields and GPS lookup.

    Adds HDX-specific fields (P-code, last update timestamp) and provides
    methods for GPS-based area lookup using PostGIS spatial queries.
    """

    _inherit = "spp.area"

    hdx_pcode = fields.Char(
        string="HDX P-code",
        index=True,
        help="Official P-code from COD dataset (e.g., 'LK3101')",
    )
    hdx_last_update = fields.Datetime(
        string="Last HDX Update",
        readonly=True,
        help="Timestamp of last update from HDX COD",
    )

    _hdx_pcode_unique = models.Constraint("UNIQUE(hdx_pcode)", "HDX P-code must be unique")

    @api.model
    def find_by_coordinates(self, latitude, longitude, level=None):
        """
        Find area containing GPS point using PostGIS polygon lookup.

        Uses PostGIS ST_Contains in a single SQL query to find the most specific
        (highest level) area that contains the given GPS coordinates.

        Args:
            latitude: GPS latitude (float, -90 to 90)
            longitude: GPS longitude (float, -180 to 180)
            level: Optional admin level filter (int)

        Returns:
            spp.area record or empty recordset if no area contains the point
        """
        # Construct WKT point (longitude first in WKT)
        point_wkt = f"SRID=4326;POINT({longitude} {latitude})"

        # Single SQL query with spatial check - much more efficient
        # geo_polygon is a native PostGIS geometry column, use it directly
        query = """
            SELECT id FROM spp_area
            WHERE geo_polygon IS NOT NULL
            AND ST_Contains(
                geo_polygon,
                ST_GeomFromText(%s)
            )
        """
        params = [point_wkt]

        if level is not None:
            query += " AND level = %s"
            params.append(level)

        # Order by level DESC to get most specific area first
        query += " ORDER BY level DESC LIMIT 1"

        try:
            self.env.cr.execute(query, params)
            result = self.env.cr.fetchone()
            return self.browse(result[0]) if result else self.browse()
        except Exception as error:
            _logger.error("Error finding area by coordinates: %s", str(error))
            return self.browse()

    @api.model
    def find_all_containing(self, latitude, longitude):
        """
        Find all areas containing point (full hierarchy).

        Uses PostGIS ST_Contains in a single SQL query to return all areas
        at all levels that contain the given GPS coordinates, ordered from
        country level (0) to most specific level.

        Args:
            latitude: GPS latitude (float, -90 to 90)
            longitude: GPS longitude (float, -180 to 180)

        Returns:
            spp.area recordset ordered by level ascending
        """
        point_wkt = f"SRID=4326;POINT({longitude} {latitude})"

        # Single SQL query for all containing areas
        # geo_polygon is a native PostGIS geometry column, use it directly
        query = """
            SELECT id FROM spp_area
            WHERE geo_polygon IS NOT NULL
            AND ST_Contains(
                geo_polygon,
                ST_GeomFromText(%s)
            )
            ORDER BY level ASC
        """

        try:
            self.env.cr.execute(query, [point_wkt])
            ids = [row[0] for row in self.env.cr.fetchall()]
            return self.browse(ids)
        except Exception as error:
            _logger.error("Error finding containing areas: %s", str(error))
            return self.browse()

    @api.model
    def find_by_pcode(self, pcode):
        """
        Find area by HDX P-code or code field.

        Args:
            pcode: P-code string

        Returns:
            spp.area record or empty recordset
        """
        if not pcode:
            return self.browse()

        # Try HDX P-code first
        area = self.search([("hdx_pcode", "=", pcode)], limit=1)
        if area:
            return area

        # Fall back to code field
        return self.search([("code", "=", pcode)], limit=1)
