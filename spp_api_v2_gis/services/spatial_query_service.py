# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for executing PostGIS spatial queries."""

import json
import logging
from datetime import UTC, datetime

from odoo.addons.spp_aggregation.services import build_explicit_scope

_logger = logging.getLogger(__name__)


class SpatialQueryService:
    """Service for PostGIS spatial queries.

    This service handles spatial queries for registrants within a polygon.
    It supports two query methods:
    - coordinates: Direct spatial query when registrants have coordinates (preferred)
    - area_fallback: Match via area_id when coordinates are not available

    Statistics computation:
    - Delegates to AggregationService (spp_aggregation)
    - AggregationService provides unified computation with k-anonymity protection
    """

    def __init__(self, env):
        """Initialize spatial query service.

        Args:
            env: Odoo environment
        """
        self.env = env

    def query_statistics_batch(
        self,
        geometries,
        filters=None,
        variables=None,
        group_by=None,
        on_progress=None,
        population_filter=None,
    ):
        """Execute spatial query for multiple geometries.

        Queries each geometry individually and computes an aggregate summary.

        Args:
            geometries: List of dicts with 'id' and 'geometry' keys
            filters: Additional filters for registrants (dict)
            variables: List of statistic names to compute
            on_progress: Optional callback(completed_count) called after each geometry

        Returns:
            dict: Batch results with per-geometry results and summary
                - results: List of per-geometry result dicts with metadata
                - summary: Aggregate summary across all geometries with metadata
        """
        results = []
        all_registrant_ids = set()
        geometries_failed = 0

        for item in geometries:
            geometry_id = item["id"]
            geometry = item["geometry"]

            try:
                result = self.query_statistics(
                    geometry=geometry,
                    filters=filters,
                    variables=variables,
                    group_by=group_by,
                    population_filter=population_filter,
                )
                # Collect registrant IDs for deduplication in summary
                registrant_ids = result.pop("registrant_ids", [])
                all_registrant_ids.update(registrant_ids)

                results.append(
                    {
                        "id": geometry_id,
                        "total_count": result["total_count"],
                        "query_method": result["query_method"],
                        "areas_matched": result["areas_matched"],
                        "statistics": result["statistics"],
                        "breakdown": result.get("breakdown"),
                        "access_level": result.get("access_level"),
                        "from_cache": result.get("from_cache", False),
                        "computed_at": result.get("computed_at"),
                    }
                )
            except Exception as e:
                _logger.warning("Batch query failed for geometry '%s': %s", geometry_id, e)
                geometries_failed += 1
                results.append(
                    {
                        "id": geometry_id,
                        "total_count": 0,
                        "query_method": "error",
                        "areas_matched": 0,
                        "statistics": {},
                        "breakdown": None,
                        "access_level": None,
                        "from_cache": False,
                        "computed_at": None,
                    }
                )

            if on_progress:
                on_progress(len(results))

        # Compute summary by aggregating unique registrants with metadata
        summary_stats_with_metadata = {"statistics": {}}
        if all_registrant_ids:
            summary_stats_with_metadata = self._compute_statistics(
                list(all_registrant_ids), variables or [], group_by=group_by
            )

        summary = {
            "total_count": len(all_registrant_ids),
            "geometries_queried": len(geometries),
            "geometries_failed": geometries_failed,
            "statistics": summary_stats_with_metadata.get("statistics", {}),
            "breakdown": summary_stats_with_metadata.get("breakdown"),
            "access_level": summary_stats_with_metadata.get("access_level"),
            "from_cache": summary_stats_with_metadata.get("from_cache", False),
            "computed_at": summary_stats_with_metadata.get("computed_at"),
        }

        return {
            "results": results,
            "summary": summary,
        }

    def query_statistics(self, geometry, filters=None, variables=None, group_by=None, population_filter=None):
        """Execute spatial query for statistics within polygon.

        Args:
            geometry: GeoJSON geometry (Polygon or MultiPolygon)
            filters: Additional filters for registrants (dict)
            variables: List of statistic names to compute

        Returns:
            dict: Query results with statistics and metadata
                - total_count: Number of registrants in polygon
                - query_method: "coordinates" or "area_fallback"
                - areas_matched: Number of areas intersecting polygon
                - statistics: Computed statistics
                - access_level: Access level applied to statistics
                - from_cache: Whether statistics were served from cache
                - computed_at: ISO 8601 timestamp when statistics were computed
        """
        filters = filters or {}
        variables = variables or []

        # Convert GeoJSON to PostGIS-compatible format
        geometry_json = json.dumps(geometry)

        # Try coordinate-based query first (preferred method)
        try:
            result = self._query_by_coordinates(geometry_json, filters, population_filter=population_filter)
            if result["total_count"] > 0:
                _logger.info(
                    "Spatial query using coordinates: %s registrants found",
                    result["total_count"],
                )
                # Compute statistics for the matched registrants with metadata
                stats_with_metadata = self._compute_statistics(result["registrant_ids"], variables, group_by=group_by)
                result.update(stats_with_metadata)
                return result
        except Exception as e:
            _logger.warning(
                "Coordinate-based query failed: %s, falling back to area-based query",
                e,
            )

        # Fall back to area-based query
        result = self._query_by_area(geometry_json, filters, population_filter=population_filter)
        _logger.info(
            f"Spatial query using area fallback: {result['total_count']} registrants in {result['areas_matched']} areas"
        )

        # Compute statistics for the matched registrants with metadata
        stats_with_metadata = self._compute_statistics(result["registrant_ids"], variables, group_by=group_by)
        result.update(stats_with_metadata)

        return result

    def _query_by_coordinates(self, geometry_json, filters, population_filter=None):
        """Query registrants by coordinates using ST_Intersects.

        This is the preferred method when registrants have coordinate data.

        Args:
            geometry_json: GeoJSON geometry as JSON string
            filters: Additional filters for registrants

        Returns:
            dict: Query results with registrant_ids
        """
        # Build WHERE clause from filters
        where_clauses = ["p.is_registrant = true"]
        filter_params = []

        if filters.get("is_group") is not None:
            where_clauses.append("p.is_group = %s")
            filter_params.append(filters["is_group"])

        if filters.get("disabled") is not None:
            if filters["disabled"]:
                where_clauses.append("p.disabled IS NOT NULL")
            else:
                where_clauses.append("p.disabled IS NULL")

        where_clause = " AND ".join(where_clauses)

        pop_where, pop_params = self._build_population_filter_sql(population_filter)

        # Query using ST_Intersects with coordinates
        # Note: This assumes res.partner has a 'coordinates' GeoPointField
        # For now, we'll check if the field exists, otherwise return empty result
        Partner = self.env["res.partner"]
        if not hasattr(Partner, "_fields") or "coordinates" not in Partner._fields:
            # Coordinates field doesn't exist, can't use this method
            raise ValueError("coordinates field not available on res.partner")

        query = f"""
            SELECT p.id
            FROM res_partner p
            WHERE {where_clause}
              AND p.coordinates IS NOT NULL
              AND ST_Intersects(
                  p.coordinates,
                  ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
              ){pop_where}
        """  # nosec B608 - SQL clauses built from hardcoded fragments, data uses %s params

        # Params ordered to match SQL: filter params, geometry, population filter
        params = filter_params + [geometry_json] + pop_params

        self.env.cr.execute(query, params)
        registrant_ids = [row[0] for row in self.env.cr.fetchall()]

        return {
            "total_count": len(registrant_ids),
            "query_method": "coordinates",
            "areas_matched": 0,  # Not applicable for coordinate-based query
            "registrant_ids": registrant_ids,
        }

    def _query_by_area(self, geometry_json, filters, population_filter=None):
        """Query registrants by area intersection (fallback method).

        This method finds areas that intersect the query polygon,
        then returns all registrants in those areas. Individuals who
        lack their own area_id are included if their group (household)
        is in a matched area.

        Args:
            geometry_json: GeoJSON geometry as JSON string
            filters: Additional filters for registrants

        Returns:
            dict: Query results with registrant_ids and areas_matched
        """
        # First, find areas that intersect the polygon
        areas_query = """
            SELECT a.id
            FROM spp_area a
            WHERE a.geo_polygon IS NOT NULL
              AND ST_Intersects(
                  a.geo_polygon,
                  ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
              )
        """

        self.env.cr.execute(areas_query, [geometry_json])
        area_ids = [row[0] for row in self.env.cr.fetchall()]

        if not area_ids:
            return {
                "total_count": 0,
                "query_method": "area_fallback",
                "areas_matched": 0,
                "registrant_ids": [],
            }

        area_tuple = tuple(area_ids)

        # Build filter clauses shared by both queries
        extra_clauses = []
        extra_params = []

        if filters.get("is_group") is not None:
            extra_clauses.append("p.is_group = %s")
            extra_params.append(filters["is_group"])

        if filters.get("disabled") is not None:
            if filters["disabled"]:
                extra_clauses.append("p.disabled IS NOT NULL")
            else:
                extra_clauses.append("p.disabled IS NULL")

        extra_where = (" AND " + " AND ".join(extra_clauses)) if extra_clauses else ""

        pop_where, pop_params = self._build_population_filter_sql(population_filter)
        extra_where += pop_where
        extra_params += pop_params

        # Query registrants: those directly in matched areas PLUS
        # individuals whose group (household) is in a matched area.
        # Individuals often lack area_id; they inherit it from their group.
        registrants_query = f"""
            SELECT DISTINCT p.id
            FROM res_partner p
            WHERE p.is_registrant = true
              AND (
                  p.area_id IN %s
                  OR (
                      p.is_group = false
                      AND p.area_id IS NULL
                      AND EXISTS (
                          SELECT 1
                          FROM spp_group_membership gm
                          JOIN res_partner g ON g.id = gm.\"group\"
                          WHERE gm.individual = p.id
                            AND gm.is_ended = false
                            AND g.area_id IN %s
                      )
                  )
              ){extra_where}
        """  # nosec B608 - SQL clauses built from hardcoded fragments, data uses %s params

        params = [area_tuple, area_tuple] + extra_params
        self.env.cr.execute(registrants_query, params)
        registrant_ids = [row[0] for row in self.env.cr.fetchall()]

        return {
            "total_count": len(registrant_ids),
            "query_method": "area_fallback",
            "areas_matched": len(area_ids),
            "registrant_ids": registrant_ids,
        }

    def _compute_statistics(self, registrant_ids, variables, group_by=None):
        """Compute statistics using the unified aggregation engine only.

        Args:
            registrant_ids: List of registrant IDs
            variables: List of statistic names to compute
            group_by: Optional list of dimension names for demographic breakdown

        Returns:
            dict: Statistics with metadata (statistics, access_level, from_cache, computed_at)
        """
        if not registrant_ids:
            return {
                "statistics": self._get_empty_statistics(),
                "access_level": None,
                "from_cache": False,
                "computed_at": datetime.now(UTC).isoformat(),
            }

        if "spp.aggregation.service" not in self.env:
            raise RuntimeError("spp.aggregation.service is required for GIS statistics queries.")

        return self._compute_via_aggregation_service(registrant_ids, variables, group_by=group_by)

    def _compute_via_aggregation_service(self, registrant_ids, variables, group_by=None):
        """Compute statistics using AggregationService.

        Delegates to the unified aggregation service for statistics computation
        with built-in privacy protection.

        Args:
            registrant_ids: List of registrant IDs
            variables: List of statistic names to compute (or None for GIS defaults)
            group_by: Optional list of dimension names for demographic breakdown

        Returns:
            dict: Statistics with metadata (statistics, access_level, from_cache, computed_at)
        """
        if not registrant_ids:
            return {"statistics": {}}

        # Create an explicit scope for the registrant IDs
        scope = build_explicit_scope(registrant_ids)

        # Determine statistics to compute
        statistics_to_compute = variables
        if not statistics_to_compute:
            # Use GIS-published statistics
            # nosemgrep: odoo-sudo-without-context
            Statistic = self.env["spp.statistic"].sudo()
            gis_stats = Statistic.get_published_for_context("gis")
            statistics_to_compute = [stat.name for stat in gis_stats] if gis_stats else None
            _logger.info(
                "No variables requested, falling back to GIS-published: %r",
                statistics_to_compute,
            )
        else:
            _logger.info("Computing requested variables: %r", statistics_to_compute)

        if not statistics_to_compute:
            return {
                "statistics": {},
                "access_level": None,
                "from_cache": False,
                "computed_at": datetime.now(UTC).isoformat(),
            }

        # Call AggregationService (no sudo - let service determine access level from calling user)
        aggregation_service = self.env["spp.aggregation.service"]
        result = aggregation_service.compute_aggregation(
            scope=scope,
            statistics=statistics_to_compute,
            group_by=group_by,
            context="gis",
            use_cache=False,  # Spatial queries are dynamic, don't cache
        )

        # Convert AggregationService result to expected format with metadata
        return self._convert_aggregation_result(result, registrant_ids)

    def _convert_aggregation_result(self, agg_result, registrant_ids=None):
        """Convert AggregationService result to spatial query format.

        Args:
            agg_result: Result from AggregationService
            registrant_ids: Backward-compatible arg; not used.

        Returns:
            dict: Statistics and metadata (statistics, access_level, from_cache, computed_at)
        """
        # Get the statistics dict from aggregation result
        statistics = agg_result.get("statistics", {})

        # Organize by category (if available)
        result = {}
        grouped_stats = {}

        # nosemgrep: odoo-sudo-without-context
        Statistic = self.env["spp.statistic"].sudo()
        statistic_by_name = {stat.name: stat for stat in Statistic.search([("name", "in", list(statistics.keys()))])}

        for stat_name, stat_data in statistics.items():
            stat = statistic_by_name.get(stat_name)

            if stat:
                config = stat.get_context_config("gis")
                stat_key = stat.name
                stat_label = config.get("label", stat.label)
                stat_group = config.get("group") or "general"
                stat_format = config.get("format", stat.format)
            else:
                # Keep unknown/built-in stats visible with generic metadata.
                stat_key = stat_name
                stat_label = stat_name.replace("_", " ").title()
                stat_group = "general"
                stat_format = "count" if stat_name == "count" else "number"

            # Extract value and suppressed flag
            display_value = stat_data.get("value")
            is_suppressed = stat_data.get("suppressed", False)

            # Format the result
            stat_entry = {
                "label": stat_label,
                "value": display_value,
                "format": stat_format,
                "suppressed": is_suppressed,
            }

            # Store both flat and grouped
            result[stat_key] = display_value

            # Also organize by group for UI
            if stat_group not in grouped_stats:
                grouped_stats[stat_group] = {}
            grouped_stats[stat_group][stat_key] = stat_entry

        # Add grouped organization to result
        if grouped_stats:
            result["_grouped"] = grouped_stats

        # Return statistics with metadata
        return {
            "statistics": result,
            "breakdown": agg_result.get("breakdown"),
            "access_level": agg_result.get("access_level"),
            "from_cache": agg_result.get("from_cache", False),
            "computed_at": agg_result.get("computed_at"),
        }

    def query_proximity(
        self,
        reference_points,
        radius_km,
        relation="within",
        filters=None,
        variables=None,
        group_by=None,
        population_filter=None,
    ):
        """Query registrants by proximity to reference points.

        Uses a temp table with pre-buffered geometries and ST_Intersects
        against the indexed res_partner.coordinates column.

        Args:
            reference_points: List of dicts with 'longitude' and 'latitude' keys
            radius_km: Search radius in kilometers
            relation: 'within' (inside radius) or 'beyond' (outside radius)
            filters: Additional filters for registrants (dict)
            variables: List of statistic names to compute

        Returns:
            dict: Query results with statistics and metadata

        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if not reference_points:
            raise ValueError("reference_points must not be empty")
        if radius_km <= 0:
            raise ValueError("radius_km must be positive")
        if relation not in ("within", "beyond"):
            raise ValueError(f"relation must be 'within' or 'beyond', got '{relation}'")

        filters = filters or {}
        variables = variables or []
        radius_meters = radius_km * 1000

        # Try coordinate-based query first
        try:
            result = self._proximity_by_coordinates(
                reference_points,
                radius_meters,
                relation,
                filters,
                population_filter=population_filter,
            )
            if result["total_count"] > 0:
                _logger.info(
                    "Proximity query (%s, %.1f km) using coordinates: %s registrants found",
                    relation,
                    radius_km,
                    result["total_count"],
                )
                registrant_ids = result["registrant_ids"]
                stats_with_metadata = self._compute_statistics(registrant_ids, variables, group_by=group_by)
                result.update(stats_with_metadata)
                result["reference_points_count"] = len(reference_points)
                result["radius_km"] = radius_km
                result["relation"] = relation
                return result
        except Exception as e:
            _logger.warning(
                "Coordinate-based proximity query failed: %s, falling back to area-based",
                e,
            )

        # Fall back to area-based query
        result = self._proximity_by_area(
            reference_points,
            radius_meters,
            relation,
            filters,
            population_filter=population_filter,
        )
        _logger.info(
            "Proximity query (%s, %.1f km) using area fallback: %s registrants in %s areas",
            relation,
            radius_km,
            result["total_count"],
            result["areas_matched"],
        )
        registrant_ids = result["registrant_ids"]
        stats_with_metadata = self._compute_statistics(registrant_ids, variables, group_by=group_by)
        result.update(stats_with_metadata)
        result["reference_points_count"] = len(reference_points)
        result["radius_km"] = radius_km
        result["relation"] = relation
        return result

    def _create_proximity_temp_table(self, reference_points, radius_meters):
        """Create temp table with pre-buffered reference point geometries.

        Buffers are computed on the reference points (small set) in geography
        for meter-accurate radius, then converted back to geometry so that
        ST_Intersects can use the GiST index on res_partner.coordinates.

        Args:
            reference_points: List of dicts with 'longitude' and 'latitude'
            radius_meters: Buffer radius in meters
        """
        # Drop any leftover temp table from a previous call in the same transaction
        self.env.cr.execute("DROP TABLE IF EXISTS _prox_ref_points")

        self.env.cr.execute(
            """
            CREATE TEMPORARY TABLE _prox_ref_points (
                buffer_geom geometry
            ) ON COMMIT DROP
            """
        )

        # Extract lon/lat arrays for bulk insert via unnest
        longitudes = [pt["longitude"] for pt in reference_points]
        latitudes = [pt["latitude"] for pt in reference_points]

        self.env.cr.execute(
            """
            INSERT INTO _prox_ref_points (buffer_geom)
            SELECT
                ST_Buffer(
                    ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography,
                    %(radius_m)s
                )::geometry
            FROM unnest(%(lons)s::float[], %(lats)s::float[]) AS t(lon, lat)
            """,
            {
                "radius_m": radius_meters,
                "lons": longitudes,
                "lats": latitudes,
            },
        )

        # Create spatial index on buffered geometries for efficient intersection
        self.env.cr.execute("CREATE INDEX ON _prox_ref_points USING GIST (buffer_geom)")

    def _build_filter_clauses(self, filters):
        """Build SQL WHERE clauses and params from filter dict.

        Args:
            filters: Dict with optional 'is_group' and 'disabled' keys

        Returns:
            tuple: (extra_where_sql, extra_params)
        """
        extra_clauses = []
        extra_params = []

        if filters.get("is_group") is not None:
            extra_clauses.append("p.is_group = %s")
            extra_params.append(filters["is_group"])

        if filters.get("disabled") is not None:
            if filters["disabled"]:
                extra_clauses.append("p.disabled IS NOT NULL")
            else:
                extra_clauses.append("p.disabled IS NULL")

        extra_where = (" AND " + " AND ".join(extra_clauses)) if extra_clauses else ""
        return extra_where, extra_params

    def _build_population_filter_sql(self, population_filter):
        """Build SQL clause from population_filter input.

        Args:
            population_filter: Dict with optional keys: program, cel_expression, mode

        Returns:
            tuple: (sql_clause, params) where sql_clause is a string like
                   "AND p.id IN (...)" and params is a list of query parameters.
                   Returns ("", []) if no filter is active.
        """
        if not population_filter:
            return "", []

        # TODO: Replace program ID with code field (see gis-analytics-enrichment.md Task 1)
        program_id = population_filter.get("program")
        cel_expression_code = population_filter.get("cel_expression")
        mode = population_filter.get("mode", "and")

        if mode not in ("and", "or", "gap"):
            raise ValueError(f"Invalid population_filter mode: {mode!r}. Must be 'and', 'or', or 'gap'.")

        if program_id is not None and not isinstance(program_id, int):
            raise ValueError("population_filter.program must be an integer")

        program_sql = ""
        program_params = []
        cel_sql = ""
        cel_params = []

        # Build program filter subquery
        if program_id:
            program_sql = """
                SELECT pm.partner_id FROM spp_program_membership pm
                WHERE pm.program_id = %s AND pm.state = 'enrolled'
            """
            program_params = [program_id]

        # Build CEL expression filter subquery
        if cel_expression_code:
            # nosemgrep: odoo-sudo-without-context
            Expression = self.env["spp.cel.expression"].sudo()
            expression = Expression.search([("code", "=", cel_expression_code)], limit=1)
            if not expression:
                _logger.warning("Population filter: expression '%s' not found", cel_expression_code)
                return "AND false", []

            cel_service = self.env["spp.cel.service"]
            result = cel_service.compile_expression(
                expression.cel_expression,
                profile="registry_groups",
                limit=0,
            )
            if not result.get("valid"):
                _logger.warning(
                    "Population filter: CEL expression '%s' failed to compile: %s",
                    cel_expression_code,
                    result.get("error"),
                )
                return "AND false", []

            domain = result.get("domain", [])
            # nosemgrep: odoo-sudo-without-context
            Partner = self.env["res.partner"].sudo()
            matching_ids = Partner.search(domain).ids
            if not matching_ids:
                return "AND false", []

            if len(matching_ids) > 10000:
                _logger.warning(
                    "Population filter: CEL expression '%s' matched %d registrants. "
                    "Consider using SQL subquery optimization for large result sets.",
                    cel_expression_code,
                    len(matching_ids),
                )

            cel_sql = "SELECT unnest(%s::int[])"
            cel_params = [list(matching_ids)]

        # Combine based on mode
        if program_sql and cel_sql:
            if mode == "and":
                return (
                    "AND p.id IN (" + program_sql + ") AND p.id IN (" + cel_sql + ")",
                    program_params + cel_params,
                )
            elif mode == "or":
                return (
                    "AND (p.id IN (" + program_sql + ") OR p.id IN (" + cel_sql + "))",
                    program_params + cel_params,
                )
            elif mode == "gap":
                return (
                    "AND p.id IN (" + cel_sql + ") AND p.id NOT IN (" + program_sql + ")",
                    cel_params + program_params,
                )
        elif program_sql:
            return "AND p.id IN (" + program_sql + ")", program_params
        elif cel_sql:
            return "AND p.id IN (" + cel_sql + ")", cel_params

        return "", []

    def _proximity_by_coordinates(self, reference_points, radius_meters, relation, filters, population_filter=None):
        """Query registrants by coordinate proximity to reference points.

        Args:
            reference_points: List of dicts with 'longitude' and 'latitude'
            radius_meters: Search radius in meters
            relation: 'within' or 'beyond'
            filters: Additional filters for registrants

        Returns:
            dict: Query results with registrant_ids
        """
        Partner = self.env["res.partner"]
        if not hasattr(Partner, "_fields") or "coordinates" not in Partner._fields:
            raise ValueError("coordinates field not available on res.partner")

        self._create_proximity_temp_table(reference_points, radius_meters)

        extra_where, extra_params = self._build_filter_clauses(filters)

        pop_where, pop_params = self._build_population_filter_sql(population_filter)
        extra_where += pop_where
        extra_params += pop_params

        if relation == "within":
            # Find registrants whose coordinates intersect any buffer
            query = f"""
                SELECT p.id
                FROM res_partner p
                WHERE p.is_registrant = true
                  AND p.coordinates IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM _prox_ref_points r
                      WHERE ST_Intersects(p.coordinates, r.buffer_geom)
                  ){extra_where}
            """  # nosec B608 - SQL clauses built from hardcoded fragments, data uses %s params
        else:
            # "beyond": find all registrants with coords, minus those within
            query = f"""
                SELECT p.id
                FROM res_partner p
                WHERE p.is_registrant = true
                  AND p.coordinates IS NOT NULL
                  AND p.id NOT IN (
                      SELECT p2.id
                      FROM res_partner p2
                      WHERE p2.is_registrant = true
                        AND p2.coordinates IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM _prox_ref_points r
                            WHERE ST_Intersects(p2.coordinates, r.buffer_geom)
                        )
                  ){extra_where}
            """  # nosec B608 - SQL clauses built from hardcoded fragments, data uses %s params

        self.env.cr.execute(query, extra_params)
        registrant_ids = [row[0] for row in self.env.cr.fetchall()]

        return {
            "total_count": len(registrant_ids),
            "query_method": "coordinates",
            "areas_matched": 0,
            "registrant_ids": registrant_ids,
        }

    def _proximity_by_area(self, reference_points, radius_meters, relation, filters, population_filter=None):
        """Query registrants by area proximity (fallback when coordinates unavailable).

        Uses ST_Intersects between area polygons and buffered reference points
        (NOT centroid, which is geometrically incorrect for large areas).

        Args:
            reference_points: List of dicts with 'longitude' and 'latitude'
            radius_meters: Search radius in meters
            relation: 'within' or 'beyond'
            filters: Additional filters for registrants

        Returns:
            dict: Query results with registrant_ids and areas_matched
        """
        self._create_proximity_temp_table(reference_points, radius_meters)

        # Find areas whose polygon intersects (or doesn't) any reference buffer
        if relation == "within":
            areas_query = """
                SELECT a.id
                FROM spp_area a
                WHERE a.geo_polygon IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM _prox_ref_points r
                      WHERE ST_Intersects(a.geo_polygon, r.buffer_geom)
                  )
            """
        else:
            areas_query = """
                SELECT a.id
                FROM spp_area a
                WHERE a.geo_polygon IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM _prox_ref_points r
                      WHERE ST_Intersects(a.geo_polygon, r.buffer_geom)
                  )
            """

        self.env.cr.execute(areas_query)
        area_ids = [row[0] for row in self.env.cr.fetchall()]

        if not area_ids:
            return {
                "total_count": 0,
                "query_method": "area_fallback",
                "areas_matched": 0,
                "registrant_ids": [],
            }

        area_tuple = tuple(area_ids)
        extra_where, extra_params = self._build_filter_clauses(filters)

        pop_where, pop_params = self._build_population_filter_sql(population_filter)
        extra_where += pop_where
        extra_params += pop_params

        # Reuse the same registrant lookup as _query_by_area (includes group membership)
        registrants_query = f"""
            SELECT DISTINCT p.id
            FROM res_partner p
            WHERE p.is_registrant = true
              AND (
                  p.area_id IN %s
                  OR (
                      p.is_group = false
                      AND p.area_id IS NULL
                      AND EXISTS (
                          SELECT 1
                          FROM spp_group_membership gm
                          JOIN res_partner g ON g.id = gm.\"group\"
                          WHERE gm.individual = p.id
                            AND gm.is_ended = false
                            AND g.area_id IN %s
                      )
                  )
              ){extra_where}
        """  # nosec B608 - SQL clauses built from hardcoded fragments, data uses %s params

        params = [area_tuple, area_tuple] + extra_params
        self.env.cr.execute(registrants_query, params)
        registrant_ids = [row[0] for row in self.env.cr.fetchall()]

        return {
            "total_count": len(registrant_ids),
            "query_method": "area_fallback",
            "areas_matched": len(area_ids),
            "registrant_ids": registrant_ids,
        }

    def _get_empty_statistics(self):
        """Return empty statistics structure.

        Returns:
            dict: Empty statistics
        """
        return {}
