# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OGC API - Features service adapter.

Translates OGC API parameters to existing CatalogService and LayersService
calls, producing OGC-compliant responses for GovStack GIS BB compliance.
"""

import json
import logging
import re

from psycopg2 import sql

from odoo.exceptions import MissingError

from .catalog_service import CatalogService
from .layers_service import LayersService

_logger = logging.getLogger(__name__)

# OGC API conformance classes (Features + Processes per OGC API Common Part 2)
CONFORMANCE_CLASSES = [
    # OGC API - Features
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
    # OGC API - Processes
    "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/ogc-process-description",
    "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/json",
    "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/job-list",
    "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/dismiss",
    # OGC API - Features Part 4 (Create/Replace/Delete)
    "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete",
]

# Collection ID constants
GEOFENCES_COLLECTION_ID = "geofences"
INCIDENTS_COLLECTION_ID = "incidents"

# Writable collections (OGC Features Part 4)
WRITABLE_COLLECTIONS = {GEOFENCES_COLLECTION_ID, INCIDENTS_COLLECTION_ID}

# Allowed geometry types for geofence creation/update
_ALLOWED_GEOFENCE_GEOMETRY_TYPES = {"Polygon", "MultiPolygon"}


class OGCService:
    """Adapter service for OGC API - Features.

    Wraps CatalogService and LayersService to produce OGC-compliant
    responses from existing GIS data sources.
    """

    def __init__(self, env, base_url=""):
        """Initialize OGC service.

        Args:
            env: Odoo environment for database access
            base_url: Base URL for generating self-referencing links
        """
        self.env = env
        self.base_url = base_url.rstrip("/")
        self.catalog_service = CatalogService(env)
        self.layers_service = LayersService(env)

    def get_landing_page(self):
        """Build OGC API landing page.

        Returns:
            dict: Landing page with navigation links
        """
        ogc_base = f"{self.base_url}/gis/ogc"
        return {
            "title": "OpenSPP GIS API",
            "description": (
                "OGC API - Features endpoints for OpenSPP geospatial data. "
                "Provides access to GIS reports and data layers as OGC-compliant "
                "feature collections."
            ),
            "links": [
                {
                    "href": ogc_base,
                    "rel": "self",
                    "type": "application/json",
                    "title": "This document",
                },
                {
                    "href": f"{ogc_base}/conformance",
                    "rel": "conformance",
                    "type": "application/json",
                    "title": "OGC API conformance classes",
                },
                {
                    "href": f"{ogc_base}/collections",
                    "rel": "data",
                    "type": "application/json",
                    "title": "Feature collections",
                },
                {
                    "href": f"{ogc_base}/processes",
                    "rel": "http://www.opengis.net/def/rel/ogc/1.0/processes",
                    "type": "application/json",
                    "title": "Processes",
                },
                {
                    "href": f"{self.base_url}/openapi.json",
                    "rel": "service-desc",
                    "type": "application/vnd.oai.openapi+json;version=3.0",
                    "title": "OpenAPI definition",
                },
            ],
        }

    def get_conformance(self):
        """Build OGC API conformance declaration.

        Returns:
            dict: Conformance class URIs
        """
        return {"conformsTo": CONFORMANCE_CLASSES}

    def get_collections(self):
        """Build OGC collections list from catalog.

        Each report fans out into one collection per available admin level.
        This prevents larger polygons from overlapping smaller ones.

        Returns:
            dict: Collections response with links
        """
        catalog = self.catalog_service.get_catalog()
        ogc_base = f"{self.base_url}/gis/ogc"
        area_level_names = catalog.get("area_level_names", {})

        collections = []

        # Map reports to collections — one per available admin level
        for report in catalog.get("reports", []):
            levels = report.get("admin_levels_available", [])
            if not levels:
                # Fallback: single collection at base_area_level
                levels = [report["area_level"]]
            for level in levels:
                collection = self._report_to_collection(report, admin_level=level, area_level_names=area_level_names)
                collections.append(collection)

        # Map data layers to collections
        for layer in catalog.get("data_layers", []):
            collection = self._data_layer_to_collection(layer)
            collections.append(collection)

        # Add geofences as a static collection
        geofence_collection = self._geofences_to_collection()
        collections.append(geofence_collection)

        # Add incidents as a static collection
        incidents_collection = self._incidents_to_collection()
        collections.append(incidents_collection)

        return {
            "links": [
                {
                    "href": f"{ogc_base}/collections",
                    "rel": "self",
                    "type": "application/json",
                    "title": "This document",
                },
            ],
            "collections": collections,
        }

    def get_collection(self, collection_id):
        """Get single collection metadata.

        Supports three ID formats:
        - "layer_{id}" — data layer
        - "{code}_adm{N}" — report at specific admin level
        - "{code}" (bare) — backward compat, defaults to base_area_level

        Args:
            collection_id: Collection identifier

        Returns:
            dict: Collection metadata

        Raises:
            MissingError: If collection not found
        """
        layer_type, layer_id, admin_level = self._parse_collection_id(collection_id)

        # Geofences collection
        if layer_type == "geofence":
            return self._geofences_to_collection()

        # Incidents collection
        if layer_type == "incident":
            return self._incidents_to_collection()

        # Data layer lookup
        if layer_type == "layer":
            catalog = self.catalog_service.get_catalog()
            for layer in catalog.get("data_layers", []):
                if layer["id"] == layer_id:
                    return self._data_layer_to_collection(layer)
            raise MissingError(f"Collection not found: {collection_id}")

        # Report lookup
        catalog = self.catalog_service.get_catalog()
        area_level_names = catalog.get("area_level_names", {})

        for report in catalog.get("reports", []):
            if report["id"] == layer_id:
                # If bare code (no _admN suffix), default to base_area_level
                if admin_level is None:
                    admin_level = report["area_level"]
                return self._report_to_collection(report, admin_level=admin_level, area_level_names=area_level_names)

        raise MissingError(f"Collection not found: {collection_id}")

    def get_collection_items(
        self,
        collection_id,
        limit=1000,
        offset=0,
        bbox=None,
        geofence_type=None,
        active=None,
        datetime_param=None,
        event=None,
        severity=None,
        incident_status=None,
        incident_code=None,
    ):
        """Get features from a collection.

        For data layers, pagination is pushed to the database via ORM
        search(limit, offset). For reports, the dataset is bounded by
        geographic area count (typically hundreds) so Python-level
        pagination is acceptable.

        Args:
            collection_id: Collection identifier
            limit: Maximum features to return (default 1000)
            offset: Pagination offset
            bbox: Bounding box filter [west, south, east, north]
            geofence_type: Filter by geofence type (geofences collection only)
            active: Include archived geofences (geofences collection only)
            datetime_param: OGC datetime filter string (incidents/geofences)
            event: Filter by event type (incidents collection only)
            severity: Filter by severity code (incidents collection only)
            incident_status: Filter by status (incidents collection only)
            incident_code: Filter geofences by incident code

        Returns:
            dict: GeoJSON FeatureCollection with OGC pagination links

        Raises:
            MissingError: If collection not found
        """
        layer_type, layer_id, admin_level = self._parse_collection_id(collection_id)

        # Incident collection: handle separately
        if layer_type == "incident":
            return self._get_incident_items(
                limit=limit,
                offset=offset,
                bbox=bbox,
                datetime_param=datetime_param,
                event=event,
                severity=severity,
                status=incident_status,
            )

        # Geofence collection: handle separately
        if layer_type == "geofence":
            return self._get_geofence_items(
                limit=limit,
                offset=offset,
                bbox=bbox,
                geofence_type=geofence_type,
                active=active,
                datetime_param=datetime_param,
                incident_code=incident_code,
            )

        # For bare report codes, default to base_area_level
        if layer_type == "report" and admin_level is None:
            admin_level = self._get_report_base_level(layer_id)

        # Get total count without loading all features
        total_count = self.layers_service.get_feature_count(
            layer_id=layer_id,
            layer_type=layer_type,
            admin_level=admin_level,
        )

        # Fetch features with pagination and spatial filter pushed to PostGIS
        geojson = self.layers_service.get_layer_geojson(
            layer_id=layer_id,
            layer_type=layer_type,
            admin_level=admin_level,
            limit=limit,
            offset=offset,
            bbox=bbox,
        )

        features = geojson.get("features", [])

        # Apply Python-level pagination for report layers.
        # Reports return all features from _to_geojson() since they are
        # bounded by area count. Data layers handle pagination at the DB level.
        if layer_type == "report" and (offset > 0 or len(features) > limit):
            features = features[offset : offset + limit]

        # Build OGC response
        ogc_base = f"{self.base_url}/gis/ogc"
        items_url = f"{ogc_base}/collections/{collection_id}/items"

        links = [
            {
                "href": f"{items_url}?limit={limit}&offset={offset}",
                "rel": "self",
                "type": "application/geo+json",
                "title": "This page",
            },
            {
                "href": f"{ogc_base}/collections/{collection_id}",
                "rel": "collection",
                "type": "application/json",
                "title": "Collection metadata",
            },
        ]

        # Add next link if more features exist
        if offset + limit < total_count:
            next_offset = offset + limit
            links.append(
                {
                    "href": f"{items_url}?limit={limit}&offset={next_offset}",
                    "rel": "next",
                    "type": "application/geo+json",
                    "title": "Next page",
                }
            )

        # Add previous link if not on first page
        if offset > 0:
            previous_offset = max(0, offset - limit)
            links.append(
                {
                    "href": f"{items_url}?limit={limit}&offset={previous_offset}",
                    "rel": "prev",
                    "type": "application/geo+json",
                    "title": "Previous page",
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
            "links": links,
            "numberMatched": total_count,
            "numberReturned": len(features),
        }

    def get_collection_item(self, collection_id, feature_id):
        """Get single feature from a collection.

        Queries the specific record directly by ID without loading the
        full collection.

        Args:
            collection_id: Collection identifier
            feature_id: Feature identifier

        Returns:
            dict: GeoJSON Feature

        Raises:
            MissingError: If collection or feature not found
        """
        layer_type, layer_id, _admin_level = self._parse_collection_id(collection_id)

        # Geofence: look up by UUID
        if layer_type == "geofence":
            return self._get_geofence_item(feature_id)

        # Incident: look up by UUID
        if layer_type == "incident":
            return self._get_incident_item(feature_id)

        feature = self.layers_service.get_feature_by_id(
            layer_id=layer_id,
            feature_id=feature_id,
            layer_type=layer_type,
        )

        # Add OGC links
        ogc_base = f"{self.base_url}/gis/ogc"
        feature.setdefault("links", [])
        feature["links"].append(
            {
                "href": f"{ogc_base}/collections/{collection_id}/items/{feature_id}",
                "rel": "self",
                "type": "application/geo+json",
            }
        )
        feature["links"].append(
            {
                "href": f"{ogc_base}/collections/{collection_id}",
                "rel": "collection",
                "type": "application/json",
            }
        )
        return feature

    def _report_to_collection(self, report, admin_level=None, area_level_names=None):
        """Convert a catalog report to an OGC collection.

        When admin_level is provided, the collection ID becomes
        "{code}_adm{level}" and the title includes the level name.

        Args:
            report: Report info dict from CatalogService
            admin_level: Admin level for this collection (optional)
            area_level_names: Dict mapping area_level to type name (optional)

        Returns:
            dict: OGC CollectionInfo
        """
        report_code = report["id"]
        ogc_base = f"{self.base_url}/gis/ogc"

        # Build collection ID and title with admin level suffix
        if admin_level is not None:
            collection_id = f"{report_code}_adm{admin_level}"
            level_name = (area_level_names or {}).get(admin_level, f"Level {admin_level}")
            title = f"{report['name']} ({level_name})"
        else:
            collection_id = report_code
            title = report["name"]

        collection = {
            "id": collection_id,
            "title": title,
            "description": report.get("description"),
            "itemType": "feature",
            "crs": [
                "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            ],
            "links": [
                {
                    "href": f"{ogc_base}/collections/{collection_id}",
                    "rel": "self",
                    "type": "application/json",
                    "title": "Collection metadata",
                },
                {
                    "href": f"{ogc_base}/collections/{collection_id}/items",
                    "rel": "items",
                    "type": "application/geo+json",
                    "title": "Feature items",
                },
                {
                    "href": f"{ogc_base}/collections/{collection_id}/qml",
                    "rel": "describedby",
                    "type": "text/xml",
                    "title": "QGIS style file (QML)",
                },
            ],
        }

        # Build extent with spatial bbox and optional temporal info
        extent = {}

        spatial_bbox = self._compute_report_bbox(report_code)
        if spatial_bbox:
            extent["spatial"] = {"bbox": [spatial_bbox], "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}

        if report.get("last_refresh"):
            extent["temporal"] = {"interval": [[report["last_refresh"], None]]}

        if extent:
            collection["extent"] = extent

        return collection

    def _data_layer_to_collection(self, layer):
        """Convert a data layer to an OGC collection.

        Args:
            layer: Data layer info dict from CatalogService

        Returns:
            dict: OGC CollectionInfo
        """
        collection_id = f"layer_{layer['id']}"
        ogc_base = f"{self.base_url}/gis/ogc"

        links = [
            {
                "href": f"{ogc_base}/collections/{collection_id}",
                "rel": "self",
                "type": "application/json",
                "title": "Collection metadata",
            },
            {
                "href": f"{ogc_base}/collections/{collection_id}/items",
                "rel": "items",
                "type": "application/geo+json",
                "title": "Feature items",
            },
        ]

        # Add QML link for report-driven data layers
        if layer.get("report_code"):
            links.append(
                {
                    "href": f"{ogc_base}/collections/{collection_id}/qml",
                    "rel": "describedby",
                    "type": "text/xml",
                    "title": "QGIS style file (QML)",
                }
            )

        collection = {
            "id": collection_id,
            "title": layer["name"],
            "description": f"Data layer from {layer.get('source_model', 'unknown')}",
            "itemType": "feature",
            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
            "links": links,
        }

        bbox = self._compute_data_layer_bbox(layer["id"])
        if bbox:
            collection["extent"] = {
                "spatial": {
                    "bbox": [bbox],
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                },
            }

        return collection

    def _compute_data_layer_bbox(self, layer_id):
        """Compute spatial bounding box for a data layer via PostGIS.

        Args:
            layer_id: Data layer database ID

        Returns:
            list: [west, south, east, north] or None if no geometry
        """
        try:
            # nosemgrep: odoo-sudo-without-context
            Layer = self.env["spp.gis.data.layer"].sudo()
            layer = Layer.browse(int(layer_id))
            if not layer.exists() or not layer.geo_field_id or not layer.model_name:
                return None

            table_name = self.env[layer.model_name]._table
            column_name = layer.geo_field_id.name

            # Identifiers come from model metadata; quote them safely via
            # psycopg2.sql to avoid any SQL injection risk.
            query = sql.SQL(
                """
                SELECT
                    ST_XMin(ST_Extent({col})),
                    ST_YMin(ST_Extent({col})),
                    ST_XMax(ST_Extent({col})),
                    ST_YMax(ST_Extent({col}))
                FROM {table}
                WHERE {col} IS NOT NULL
                """
            ).format(
                col=sql.Identifier(column_name),
                table=sql.Identifier(table_name),
            )
            self.env.cr.execute(query)
            row = self.env.cr.fetchone()
            if row and row[0] is not None:
                return [row[0], row[1], row[2], row[3]]
        except Exception as e:
            _logger.warning("Failed to compute bbox for data layer %s: %s", layer_id, e)
        return None

    def _compute_report_bbox(self, report_code):
        """Compute spatial bounding box for a report's areas via PostGIS.

        Args:
            report_code: Report code (collection ID)

        Returns:
            list: [west, south, east, north] or None if no geometry
        """
        try:
            self.env.cr.execute(
                """
                SELECT
                    ST_XMin(ST_Extent(a.geo_polygon)),
                    ST_YMin(ST_Extent(a.geo_polygon)),
                    ST_XMax(ST_Extent(a.geo_polygon)),
                    ST_YMax(ST_Extent(a.geo_polygon))
                FROM spp_gis_report_data d
                JOIN spp_area a ON a.id = d.area_id
                JOIN spp_gis_report r ON r.id = d.report_id
                WHERE r.code = %s AND a.geo_polygon IS NOT NULL
                """,
                (report_code,),
            )
            row = self.env.cr.fetchone()
            if row and row[0] is not None:
                return [row[0], row[1], row[2], row[3]]
        except Exception as e:
            _logger.warning("Failed to compute bbox for report %s: %s", report_code, e)
        return None

    def _parse_collection_id(self, collection_id):
        """Parse collection ID into layer type, layer ID, and admin level.

        Supported formats:
        - "geofences" → ("geofence", None, None)
        - "layer_{id}" → ("layer", "{id}", None)
        - "{code}_adm{N}" → ("report", "{code}", N)
        - "{code}" → ("report", "{code}", None)

        Args:
            collection_id: Collection identifier

        Returns:
            tuple: (layer_type, layer_id, admin_level)
        """
        if collection_id == GEOFENCES_COLLECTION_ID:
            return "geofence", None, None

        if collection_id == INCIDENTS_COLLECTION_ID:
            return "incident", None, None

        if collection_id.startswith("layer_"):
            return "layer", collection_id[6:], None

        match = re.match(r"^(.+)_adm(\d+)$", collection_id)
        if match:
            return "report", match.group(1), int(match.group(2))

        return "report", collection_id, None

    # --- Geofence collection methods ---

    def _geofences_to_collection(self):
        """Build OGC collection metadata for geofences.

        Returns:
            dict: OGC CollectionInfo for geofences
        """
        ogc_base = f"{self.base_url}/gis/ogc"
        collection = {
            "id": GEOFENCES_COLLECTION_ID,
            "title": "Geofences",
            "description": "User-defined geographic areas of interest",
            "itemType": "feature",
            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
            "links": [
                {
                    "href": f"{ogc_base}/collections/{GEOFENCES_COLLECTION_ID}",
                    "rel": "self",
                    "type": "application/json",
                    "title": "Collection metadata",
                },
                {
                    "href": f"{ogc_base}/collections/{GEOFENCES_COLLECTION_ID}/items",
                    "rel": "items",
                    "type": "application/geo+json",
                    "title": "Feature items",
                },
            ],
        }

        # Advertise geometry type so QGIS recognizes this as a spatial layer
        # even when the collection is empty
        collection["storageCrs"] = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
        collection["geometryDimension"] = 2

        bbox = self._compute_geofence_bbox()
        if bbox:
            collection["extent"] = {
                "spatial": {
                    "bbox": [bbox],
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                },
            }

        return collection

    def _compute_geofence_bbox(self):
        """Compute spatial bounding box from all active geofence geometries.

        Returns:
            list: [west, south, east, north] or None if no geometries
        """
        try:
            self.env.cr.execute(
                """
                SELECT
                    ST_XMin(ST_Extent(geometry::geometry)),
                    ST_YMin(ST_Extent(geometry::geometry)),
                    ST_XMax(ST_Extent(geometry::geometry)),
                    ST_YMax(ST_Extent(geometry::geometry))
                FROM spp_gis_geofence
                WHERE active = TRUE AND geometry IS NOT NULL
                """
            )
            row = self.env.cr.fetchone()
            if row and row[0] is not None:
                return [row[0], row[1], row[2], row[3]]
        except Exception as e:
            _logger.warning("Failed to compute bbox for geofences: %s", e)
        return None

    def _get_geofence_items(
        self, limit=1000, offset=0, bbox=None, geofence_type=None, active=None, datetime_param=None, incident_code=None
    ):
        """Get geofence features as a GeoJSON FeatureCollection.

        Args:
            limit: Maximum features to return
            offset: Pagination offset
            bbox: Bounding box filter [west, south, east, north]
            geofence_type: Filter by geofence type
            active: Include archived (default: only active)
            datetime_param: OGC datetime filter (filters on create_date)
            incident_code: Filter by linked incident code

        Returns:
            dict: GeoJSON FeatureCollection with OGC pagination
        """
        # nosemgrep: odoo-sudo-without-context
        Geofence = self.env["spp.gis.geofence"].sudo()

        domain = []
        if active is not None:
            domain.append(("active", "=", active))
        else:
            domain.append(("active", "=", True))

        if geofence_type:
            domain.append(("geofence_type", "=", geofence_type))

        if incident_code:
            # nosemgrep: odoo-sudo-without-context
            incident = self.env["spp.hazard.incident"].sudo().search([("code", "=", incident_code)], limit=1)
            if incident:
                domain.append(("incident_id", "=", incident.id))
            else:
                # No matching incident: return empty
                domain.append(("id", "=", 0))

        if datetime_param:
            dt_start, dt_end = self._parse_datetime_param(datetime_param)
            if dt_start:
                domain.append(("create_date", ">=", dt_start))
            if dt_end:
                domain.append(("create_date", "<=", dt_end))

        if bbox:
            bbox_geojson = self.layers_service._bbox_to_geojson(bbox)
            domain.append(("geometry", "gis_intersects", bbox_geojson))

        total_count = Geofence.search_count(domain)
        geofences = Geofence.search(domain, limit=limit, offset=offset, order="name")

        # Prefetch related fields to avoid N+1 queries
        geofences.mapped("tag_ids.name")
        geofences.mapped("create_uid.name")

        features = [rec.to_geojson() for rec in geofences]

        # Build OGC response with pagination links
        ogc_base = f"{self.base_url}/gis/ogc"
        items_url = f"{ogc_base}/collections/{GEOFENCES_COLLECTION_ID}/items"

        links = [
            {
                "href": f"{items_url}?limit={limit}&offset={offset}",
                "rel": "self",
                "type": "application/geo+json",
                "title": "This page",
            },
            {
                "href": f"{ogc_base}/collections/{GEOFENCES_COLLECTION_ID}",
                "rel": "collection",
                "type": "application/json",
                "title": "Collection metadata",
            },
        ]

        if offset + limit < total_count:
            links.append(
                {
                    "href": f"{items_url}?limit={limit}&offset={offset + limit}",
                    "rel": "next",
                    "type": "application/geo+json",
                    "title": "Next page",
                }
            )

        if offset > 0:
            links.append(
                {
                    "href": f"{items_url}?limit={limit}&offset={max(0, offset - limit)}",
                    "rel": "prev",
                    "type": "application/geo+json",
                    "title": "Previous page",
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
            "links": links,
            "numberMatched": total_count,
            "numberReturned": len(features),
        }

    def _get_geofence_item(self, feature_id):
        """Get a single geofence by UUID.

        Args:
            feature_id: Geofence UUID

        Returns:
            dict: GeoJSON Feature with OGC links

        Raises:
            MissingError: If geofence not found or inactive
        """
        # nosemgrep: odoo-sudo-without-context
        geofence = (
            self.env["spp.gis.geofence"].sudo().search([("uuid", "=", feature_id), ("active", "=", True)], limit=1)
        )
        if not geofence:
            raise MissingError(f"Feature {feature_id} not found in collection geofences")

        feature = geofence.to_geojson()

        # Add OGC links
        ogc_base = f"{self.base_url}/gis/ogc"
        feature.setdefault("links", [])
        feature["links"].append(
            {
                "href": f"{ogc_base}/collections/{GEOFENCES_COLLECTION_ID}/items/{feature_id}",
                "rel": "self",
                "type": "application/geo+json",
            }
        )
        feature["links"].append(
            {
                "href": f"{ogc_base}/collections/{GEOFENCES_COLLECTION_ID}",
                "rel": "collection",
                "type": "application/json",
            }
        )
        return feature

    # --- Geofence write methods (OGC Features Part 4) ---

    def _validate_geofence_input(self, feature_input):
        """Validate and extract fields from a GeoJSON Feature for geofence create/replace.

        Args:
            feature_input: GeoJSON Feature dict

        Returns:
            tuple: (geometry_dict, properties_dict, name, geofence_type)

        Raises:
            ValueError: If validation fails
        """
        geometry = feature_input.get("geometry")
        properties = feature_input.get("properties", {})

        if not geometry:
            raise ValueError("Geometry is required")
        geom_type = geometry.get("type", "")
        if geom_type not in _ALLOWED_GEOFENCE_GEOMETRY_TYPES:
            raise ValueError(f"Geometry type '{geom_type}' is not allowed. Must be Polygon or MultiPolygon.")

        name = properties.get("name")
        if not name:
            raise ValueError("Property 'name' is required")

        geofence_type = properties.get("geofence_type", "custom")
        self._validate_geofence_type(geofence_type)

        return geometry, properties, name, geofence_type

    def create_geofence_feature(self, feature_input):
        """Create a geofence from a GeoJSON Feature.

        Args:
            feature_input: GeoJSON Feature dict with geometry and properties

        Returns:
            dict: {"feature": GeoJSON Feature, "location": URL string}

        Raises:
            ValueError: If input validation fails
        """
        geometry, properties, name, geofence_type = self._validate_geofence_input(feature_input)

        # Build create vals
        vals = {
            "name": name,
            "geometry": json.dumps(geometry),
            "geofence_type": geofence_type,
            "created_from": "api",
        }

        if properties.get("description"):
            vals["description"] = properties["description"]

        # Resolve tags
        if properties.get("tags"):
            vals["tag_ids"] = self._resolve_geofence_tags(properties["tags"])

        # Resolve incident_code
        if properties.get("incident_code"):
            vals["incident_id"] = self._resolve_incident_code(properties["incident_code"])

        # nosemgrep: odoo-sudo-without-context
        geofence = self.env["spp.gis.geofence"].sudo().create(vals)

        feature = geofence.to_geojson()
        ogc_base = f"{self.base_url}/gis/ogc"
        location = f"{ogc_base}/collections/{GEOFENCES_COLLECTION_ID}/items/{geofence.uuid}"

        return {"feature": feature, "location": location}

    def replace_geofence_feature(self, feature_id, feature_input):
        """Replace a geofence (PUT semantics: full replacement).

        Args:
            feature_id: Geofence UUID
            feature_input: GeoJSON Feature dict

        Returns:
            dict: Updated GeoJSON Feature

        Raises:
            MissingError: If geofence not found
            ValueError: If input validation fails
        """
        # nosemgrep: odoo-sudo-without-context
        geofence = (
            self.env["spp.gis.geofence"].sudo().search([("uuid", "=", feature_id), ("active", "=", True)], limit=1)
        )
        if not geofence:
            raise MissingError(f"Feature {feature_id} not found in collection geofences")

        geometry, properties, name, geofence_type = self._validate_geofence_input(feature_input)

        # Build write vals (full replacement)
        vals = {
            "name": name,
            "geometry": json.dumps(geometry),
            "geofence_type": geofence_type,
            "description": properties.get("description", False),
        }

        # Resolve tags (replace all)
        if "tags" in properties:
            vals["tag_ids"] = self._resolve_geofence_tags(properties["tags"])
        else:
            # PUT is full replacement: clear tags if not provided
            from odoo import Command

            vals["tag_ids"] = [Command.clear()]

        # Resolve incident_code
        if properties.get("incident_code"):
            vals["incident_id"] = self._resolve_incident_code(properties["incident_code"])
        else:
            vals["incident_id"] = False

        geofence.write(vals)

        return geofence.to_geojson()

    def delete_geofence_feature(self, feature_id):
        """Soft delete a geofence (set active=False).

        Args:
            feature_id: Geofence UUID

        Raises:
            MissingError: If geofence not found
            ValueError: If geofence is referenced by a program
        """
        # nosemgrep: odoo-sudo-without-context
        geofence = (
            self.env["spp.gis.geofence"].sudo().search([("uuid", "=", feature_id), ("active", "=", True)], limit=1)
        )
        if not geofence:
            raise MissingError(f"Feature {feature_id} not found in collection geofences")

        self._check_geofence_not_referenced(geofence)
        geofence.write({"active": False})

    def _check_geofence_not_referenced(self, geofence):
        """Block deletion if the geofence is linked to any program.

        Checks both active and inactive programs since geofences serve as
        historical records of a program's geographic scope.

        Args:
            geofence: spp.gis.geofence record

        Raises:
            ValueError: If geofence is referenced by one or more programs
        """
        if "spp.program" not in self.env or "geofence_ids" not in self.env["spp.program"]._fields:
            return
        # sudo: deletion-integrity check must see every program (incl. archived
        # and those outside the caller's record rules) that references the
        # geofence, otherwise a referenced geofence could be wrongly deleted.
        program_model = self.env[
            "spp.program"
        ].sudo()  # nosemgrep: odoo-sudo-without-context,odoo-sudo-on-sensitive-models
        programs = program_model.with_context(active_test=False).search([("geofence_ids", "in", geofence.ids)], limit=5)
        if programs:
            names = ", ".join(programs.mapped("name")[:5])
            raise ValueError(f"Cannot delete geofence: referenced by program(s): {names}")

    def _validate_geofence_type(self, geofence_type):
        """Validate geofence_type against available selection values.

        Args:
            geofence_type: Type string to validate

        Raises:
            ValueError: If type is not valid, with message listing valid options
        """
        # nosemgrep: odoo-sudo-without-context
        field = self.env["spp.gis.geofence"].sudo()._fields["geofence_type"]
        valid_values = [key for key, _label in field.selection]
        if geofence_type not in valid_values:
            raise ValueError(f"Invalid geofence_type '{geofence_type}'. Valid options: {', '.join(valid_values)}")

    def _resolve_geofence_tags(self, tag_names):
        """Resolve tag names to Many2many write commands (search-or-create).

        Batch-searches existing tags first to avoid N+1 queries.

        Args:
            tag_names: List of tag name strings

        Returns:
            list: Odoo Command list for tag_ids field
        """
        from odoo import Command

        if not tag_names:
            return [Command.clear()]

        # nosemgrep: odoo-sudo-without-context
        Tag = self.env["spp.gis.geofence.tag"].sudo()

        # Batch search: one query for all existing tags
        existing = Tag.search([("name", "in", tag_names)])
        existing_by_name = {t.name: t.id for t in existing}

        # Create only the missing tags
        tag_ids = []
        for name in tag_names:
            if name in existing_by_name:
                tag_ids.append(existing_by_name[name])
            else:
                new_tag = Tag.create({"name": name})
                tag_ids.append(new_tag.id)

        return [Command.set(tag_ids)]

    def _resolve_incident_code(self, incident_code):
        """Resolve incident code to incident record ID.

        Args:
            incident_code: Hazard incident code string

        Returns:
            int: Incident record ID

        Raises:
            ValueError: If incident not found
        """
        # nosemgrep: odoo-sudo-without-context
        incident = self.env["spp.hazard.incident"].sudo().search([("code", "=", incident_code)], limit=1)
        if not incident:
            raise ValueError(f"Incident with code '{incident_code}' not found")
        return incident.id

    def _get_report_base_level(self, report_code):
        """Look up the base_area_level for a report by code.

        Used as default admin_level when a bare code is provided
        (no _admN suffix) for backward compatibility.

        Args:
            report_code: Report code

        Returns:
            int: base_area_level or None if report not found
        """
        # nosemgrep: odoo-sudo-without-context
        report = self.env["spp.gis.report"].sudo().search([("code", "=", report_code)], limit=1)
        if report:
            return report.base_area_level
        return None

    # --- Incident collection methods ---

    def _incidents_to_collection(self):
        """Build OGC collection metadata for incidents.

        Returns:
            dict: OGC CollectionInfo for incidents
        """
        ogc_base = f"{self.base_url}/gis/ogc"
        return {
            "id": INCIDENTS_COLLECTION_ID,
            "title": "Hazard Incidents",
            "description": "Hazard incidents from external alert systems and internal reporting",
            "itemType": "feature",
            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
            "links": [
                {
                    "href": f"{ogc_base}/collections/{INCIDENTS_COLLECTION_ID}",
                    "rel": "self",
                    "type": "application/json",
                    "title": "Collection metadata",
                },
                {
                    "href": f"{ogc_base}/collections/{INCIDENTS_COLLECTION_ID}/items",
                    "rel": "items",
                    "type": "application/geo+json",
                    "title": "Feature items",
                },
            ],
            "storageCrs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            "geometryDimension": 2,
        }

    def _get_incident_items(
        self, limit=1000, offset=0, bbox=None, datetime_param=None, event=None, severity=None, status=None
    ):
        """Get incident features as a GeoJSON FeatureCollection.

        Args:
            limit: Maximum features to return
            offset: Pagination offset
            bbox: Bounding box filter (filters through linked geofences)
            datetime_param: OGC datetime filter on [effective, expires]
            event: Filter by cap_event
            severity: Filter by severity vocabulary code
            status: Filter by incident status

        Returns:
            dict: GeoJSON FeatureCollection with OGC pagination
        """
        # nosemgrep: odoo-sudo-without-context
        Incident = self.env["spp.hazard.incident"].sudo()

        domain = []

        if event:
            domain.append(("cap_event", "=ilike", event))

        if severity:
            VocabCode = self.env["spp.vocabulary.code"].sudo()
            severity_code = VocabCode.get_code("urn:oasis:names:tc:cap:severity", severity)
            if severity_code:
                domain.append(("severity_id", "=", severity_code.id))
            else:
                domain.append(("id", "=", 0))  # No match

        if status:
            domain.append(("status", "=", status))

        if datetime_param:
            dt_start, dt_end = self._parse_datetime_param(datetime_param)
            # Temporal overlap: effective <= end AND (expires >= start OR expires IS NULL)
            # Incidents with no effective date have no temporal extent and must not match.
            if dt_end:
                domain.append(("effective", "!=", False))
                domain.append(("effective", "<=", dt_end))
            if dt_start:
                domain.append("|")
                domain.append(("expires", ">=", dt_start))
                domain.append(("expires", "=", False))

        if bbox:
            # Filter through linked geofences
            # nosemgrep: odoo-sudo-without-context
            Geofence = self.env["spp.gis.geofence"].sudo()
            bbox_geojson = self.layers_service._bbox_to_geojson(bbox)
            geofences = Geofence.search(
                [
                    ("active", "=", True),
                    ("geofence_type", "=", "hazard_zone"),
                    ("geometry", "gis_intersects", bbox_geojson),
                ]
            )
            incident_ids = geofences.mapped("incident_id").ids
            domain.append(("id", "in", incident_ids))

        total_count = Incident.search_count(domain)
        incidents = Incident.search(domain, limit=limit, offset=offset, order="start_date desc, name")

        # Prefetch related fields
        incidents.mapped("severity_id.code")
        incidents.mapped("cap_urgency_id.code")
        incidents.mapped("cap_certainty_id.code")
        incidents.mapped("cap_msg_type_id.code")
        incidents.mapped("category_id.name")

        features = [rec.to_geojson() for rec in incidents]

        # Build OGC response with pagination links
        ogc_base = f"{self.base_url}/gis/ogc"
        items_url = f"{ogc_base}/collections/{INCIDENTS_COLLECTION_ID}/items"

        links = [
            {
                "href": f"{items_url}?limit={limit}&offset={offset}",
                "rel": "self",
                "type": "application/geo+json",
                "title": "This page",
            },
            {
                "href": f"{ogc_base}/collections/{INCIDENTS_COLLECTION_ID}",
                "rel": "collection",
                "type": "application/json",
                "title": "Collection metadata",
            },
        ]

        if offset + limit < total_count:
            links.append(
                {
                    "href": f"{items_url}?limit={limit}&offset={offset + limit}",
                    "rel": "next",
                    "type": "application/geo+json",
                    "title": "Next page",
                }
            )

        if offset > 0:
            links.append(
                {
                    "href": f"{items_url}?limit={limit}&offset={max(0, offset - limit)}",
                    "rel": "prev",
                    "type": "application/geo+json",
                    "title": "Previous page",
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
            "links": links,
            "numberMatched": total_count,
            "numberReturned": len(features),
        }

    def _get_incident_item(self, feature_id):
        """Get a single incident by UUID.

        Args:
            feature_id: Incident UUID

        Returns:
            dict: GeoJSON Feature with OGC links

        Raises:
            MissingError: If incident not found
        """
        # nosemgrep: odoo-sudo-without-context
        incident = self.env["spp.hazard.incident"].sudo().search([("uuid", "=", feature_id)], limit=1)
        if not incident:
            raise MissingError(f"Feature {feature_id} not found in collection incidents")

        feature = incident.to_geojson()

        # Add OGC links
        ogc_base = f"{self.base_url}/gis/ogc"
        feature.setdefault("links", [])
        feature["links"].append(
            {
                "href": f"{ogc_base}/collections/{INCIDENTS_COLLECTION_ID}/items/{feature_id}",
                "rel": "self",
                "type": "application/geo+json",
            }
        )
        feature["links"].append(
            {
                "href": f"{ogc_base}/collections/{INCIDENTS_COLLECTION_ID}",
                "rel": "collection",
                "type": "application/json",
            }
        )
        return feature

    def create_incident_feature(self, feature_input):
        """Create an incident from a GeoJSON Feature.

        Delegates to spp.hazard.incident.create_from_alert().

        Args:
            feature_input: GeoJSON Feature dict with geometry and properties

        Returns:
            dict: {"feature": GeoJSON Feature, "location": URL string}

        Raises:
            ValueError: If input validation fails or duplicate detected
        """
        geometry = feature_input.get("geometry")
        properties = feature_input.get("properties", {})

        if not geometry:
            raise ValueError("Geometry is required for incident creation")

        # Duplicate detection: check source_alert_id
        source_alert_id = properties.get("source_alert_id")
        if source_alert_id:
            # nosemgrep: odoo-sudo-without-context
            existing = (
                self.env["spp.hazard.incident"].sudo().search([("source_alert_id", "=", source_alert_id)], limit=1)
            )
            if existing:
                ogc_base = f"{self.base_url}/gis/ogc"
                location = f"{ogc_base}/collections/{INCIDENTS_COLLECTION_ID}/items/{existing.uuid}"
                raise DuplicateAlertError(
                    f"Incident with source_alert_id '{source_alert_id}' already exists",
                    location=location,
                )

        # nosemgrep: odoo-sudo-without-context
        Incident = self.env["spp.hazard.incident"].sudo()
        incident = Incident.create_from_alert(geometry, properties)

        feature = incident.to_geojson()
        ogc_base = f"{self.base_url}/gis/ogc"
        location = f"{ogc_base}/collections/{INCIDENTS_COLLECTION_ID}/items/{incident.uuid}"

        return {"feature": feature, "location": location}

    def replace_incident_feature(self, feature_id, feature_input):
        """Update an incident (PUT semantics).

        Args:
            feature_id: Incident UUID
            feature_input: GeoJSON Feature dict

        Returns:
            dict: Updated GeoJSON Feature

        Raises:
            MissingError: If incident not found
        """
        # nosemgrep: odoo-sudo-without-context
        incident = self.env["spp.hazard.incident"].sudo().search([("uuid", "=", feature_id)], limit=1)
        if not incident:
            raise MissingError(f"Feature {feature_id} not found in collection incidents")

        geometry = feature_input.get("geometry")
        properties = feature_input.get("properties", {})

        incident.update_from_alert(geometry, properties)

        return incident.to_geojson()

    # --- Datetime parsing ---

    def _parse_datetime_param(self, datetime_str):
        """Parse OGC datetime parameter into (start, end) tuple.

        Formats:
            "2026-04-01T00:00:00Z"      -> (instant, instant)
            "2026-01-01/2026-06-01"     -> (start, end)
            "../2026-06-01"             -> (None, end)
            "2026-01-01/.."             -> (start, None)

        Returns:
            tuple: (start_str, end_str) - either may be None for open intervals
        """
        if "/" in datetime_str:
            parts = datetime_str.split("/", 1)
            start = parts[0] if parts[0] != ".." else None
            end = parts[1] if parts[1] != ".." else None
            return start, end
        # Single instant
        return datetime_str, datetime_str


class DuplicateAlertError(ValueError):
    """Raised when a POST arrives with a source_alert_id that already exists.

    Carries a location URL pointing to the existing resource so the router
    can return 409 Conflict with a Location header.
    """

    def __init__(self, message, location=None):
        super().__init__(message)
        self.location = location
