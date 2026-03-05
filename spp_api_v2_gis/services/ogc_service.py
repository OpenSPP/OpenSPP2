# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OGC API - Features service adapter.

Translates OGC API parameters to existing CatalogService and LayersService
calls, producing OGC-compliant responses for GovStack GIS BB compliance.
"""

import logging
import re

from odoo.exceptions import MissingError

from .catalog_service import CatalogService
from .layers_service import LayersService

_logger = logging.getLogger(__name__)

# OGC API - Features conformance classes
CONFORMANCE_CLASSES = [
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
]


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

        Returns:
            dict: GeoJSON FeatureCollection with OGC pagination links

        Raises:
            MissingError: If collection not found
        """
        layer_type, layer_id, admin_level = self._parse_collection_id(collection_id)

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

        return {
            "id": collection_id,
            "title": layer["name"],
            "description": f"Data layer from {layer.get('source_model', 'unknown')}",
            "itemType": "feature",
            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
            "links": links,
        }

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
        - "layer_{id}" → ("layer", "{id}", None)
        - "{code}_adm{N}" → ("report", "{code}", N)
        - "{code}" → ("report", "{code}", None)

        Args:
            collection_id: Collection identifier

        Returns:
            tuple: (layer_type, layer_id, admin_level)
        """
        if collection_id.startswith("layer_"):
            return "layer", collection_id[6:], None

        match = re.match(r"^(.+)_adm(\d+)$", collection_id)
        if match:
            return "report", match.group(1), int(match.group(2))

        return "report", collection_id, None

    def _get_report_base_level(self, report_code):
        """Look up the base_area_level for a report by code.

        Used as default admin_level when a bare code is provided
        (no _admN suffix) for backward compatibility.

        Args:
            report_code: Report code

        Returns:
            int: base_area_level or None if report not found
        """
        report = self.env["spp.gis.report"].sudo().search([("code", "=", report_code)], limit=1)
        if report:
            return report.base_area_level
        return None
