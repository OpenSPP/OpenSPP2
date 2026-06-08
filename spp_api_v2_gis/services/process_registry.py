# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Process registry for OGC API - Processes.

Provides process definitions for spatial-statistics and proximity-statistics,
dynamically generating input schemas from spp.statistic records.
"""

import logging

_logger = logging.getLogger(__name__)

# Process IDs
SPATIAL_STATISTICS = "spatial-statistics"
PROXIMITY_STATISTICS = "proximity-statistics"

VALID_PROCESS_IDS = {SPATIAL_STATISTICS, PROXIMITY_STATISTICS}

# Maximum geometries allowed per batch request
MAX_BATCH_GEOMETRIES = 100

# Default maximum reference points for proximity queries.
# Configurable via ir.config_parameter key "spp_gis.max_proximity_points".
DEFAULT_MAX_PROXIMITY_POINTS = 50000


class ProcessRegistry:
    """Registry of available OGC processes.

    Generates process descriptions dynamically from spp.statistic records,
    so that available statistics are always in sync with the database.
    """

    def __init__(self, env):
        self.env = env

    def list_processes(self):
        """Return summary list of all available processes."""
        return [
            {
                "id": SPATIAL_STATISTICS,
                "title": "Spatial Statistics",
                "description": "Compute aggregate registrant statistics within arbitrary polygons using PostGIS.",
                "version": "1.0.0",
                "jobControlOptions": ["sync-execute", "async-execute", "dismiss"],
            },
            {
                "id": PROXIMITY_STATISTICS,
                "title": "Proximity Statistics",
                "description": (
                    "Compute aggregate registrant statistics within or beyond a given radius from reference points."
                ),
                "version": "1.0.0",
                "jobControlOptions": ["sync-execute", "async-execute", "dismiss"],
            },
        ]

    def get_process(self, process_id):
        """Return full process description including input/output schemas.

        Returns None if process_id is not recognized.
        """
        if process_id == SPATIAL_STATISTICS:
            return self._build_spatial_statistics_description()
        if process_id == PROXIMITY_STATISTICS:
            return self._build_proximity_statistics_description()
        return None

    def get_statistics_metadata(self):
        """Get statistics metadata organized by category.

        Used by both process descriptions (for x-openspp-statistics extension)
        and the GET /gis/statistics endpoint.

        Returns:
            tuple: (variable_names, categories_metadata)
                - variable_names: list of str (statistic names for enum)
                - categories_metadata: list of dicts with category info
        """
        # nosemgrep: odoo-sudo-without-context
        Statistic = self.env["spp.indicator"].sudo()
        stats_by_category = Statistic.get_published_by_category("gis")

        variable_names = []
        categories = []

        for category_code, stat_records in stats_by_category.items():
            category_record = stat_records[0].category_id if stat_records else None

            stat_items = []
            for stat in stat_records:
                config = stat.get_context_config("gis")
                variable_names.append(stat.name)
                stat_items.append(
                    {
                        "name": stat.name,
                        "label": config.get("label", stat.label),
                        "description": stat.description,
                        "format": config.get("format", stat.format),
                        "unit": stat.unit,
                    }
                )

            categories.append(
                {
                    "code": category_code,
                    "name": category_record.name if category_record else category_code.replace("_", " ").title(),
                    "icon": getattr(category_record, "icon", None) if category_record else None,
                    "statistics": stat_items,
                }
            )

        return variable_names, categories

    def _build_group_by_input(self):
        """Build the group_by input definition with dynamic enum from active dimensions."""
        # nosemgrep: odoo-sudo-without-context
        Dimension = self.env["spp.demographic.dimension"].sudo()
        active_dimensions = Dimension.search([("active", "=", True)])

        dimension_names = [dim.name for dim in active_dimensions]
        dimension_metadata = [{"name": dim.name, "label": dim.label} for dim in active_dimensions]

        group_by_input = {
            "title": "Disaggregation Dimensions",
            "description": "Dimension names to break down results by. Maximum 3.",
            "minOccurs": 0,
            "schema": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 3,
            },
        }

        if dimension_names:
            group_by_input["schema"]["items"]["enum"] = dimension_names

        if dimension_metadata:
            group_by_input["x-openspp-dimensions"] = dimension_metadata

        return group_by_input

    def _build_population_filter_input(self):
        """Build population_filter input with dynamic enum from programs and expressions."""
        # TODO: Replace program ID with code field (see gis-analytics-enrichment.md Task 1)
        # nosemgrep: odoo-sudo-without-context
        Program = self.env["spp.program"].sudo()
        programs = Program.search([])
        program_ids = [p.id for p in programs]
        program_metadata = [{"id": p.id, "name": p.name} for p in programs]

        # nosemgrep: odoo-sudo-without-context
        Expression = self.env["spp.cel.expression"].sudo()
        expressions = Expression.search(
            [
                ("expression_type", "=", "filter"),
                ("code", "!=", False),
            ]
        )
        expression_codes = [e.code for e in expressions]
        expression_metadata = [{"code": e.code, "name": e.name, "context_type": e.context_type} for e in expressions]

        population_filter = {
            "title": "Population Filter",
            "description": (
                "Filter registrants by program enrollment and/or eligibility criteria. "
                "Use 'gap' mode to find eligible but not enrolled registrants."
            ),
            "minOccurs": 0,
            "schema": {
                "type": "object",
                "properties": {
                    "program": {
                        # TODO: Replace with string type + code enum once spp.program has a code field
                        "type": "integer",
                        "description": "Program ID to filter by enrollment.",
                    },
                    "cel_expression": {
                        "type": "string",
                        "description": "CEL expression code to filter by criteria.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["and", "or", "gap"],
                        "default": "and",
                        "description": (
                            "'and': both filters, 'or': either filter, 'gap': matches CEL but NOT enrolled in program."
                        ),
                    },
                },
            },
        }

        if program_ids:
            population_filter["schema"]["properties"]["program"]["enum"] = program_ids
        if expression_codes:
            population_filter["schema"]["properties"]["cel_expression"]["enum"] = expression_codes
        if program_metadata:
            population_filter["x-openspp-programs"] = program_metadata
        if expression_metadata:
            population_filter["x-openspp-expressions"] = expression_metadata

        return population_filter

    def _build_variables_input(self):
        """Build the variables input definition with dynamic enum and x-openspp-statistics."""
        variable_names, categories = self.get_statistics_metadata()

        variables_input = {
            "title": "Statistics Variables",
            "description": "Names of statistics to compute. Omit for all GIS-published statistics.",
            "minOccurs": 0,
            "schema": {
                "type": "array",
                "items": {"type": "string"},
            },
        }

        # Add enum if we have published indicators
        if variable_names:
            variables_input["schema"]["items"]["enum"] = variable_names

        # Add x-openspp-statistics extension for rich UI metadata
        if categories:
            variables_input["x-openspp-statistics"] = {"categories": categories}

        return variables_input

    def _build_spatial_statistics_description(self):
        """Build full process description for spatial-statistics."""
        return {
            "id": SPATIAL_STATISTICS,
            "title": "Spatial Statistics",
            "description": (
                "Compute aggregate registrant statistics within arbitrary polygons "
                "using PostGIS. Accepts a single geometry or multiple geometries for "
                "batch processing."
            ),
            "version": "1.0.0",
            "jobControlOptions": ["sync-execute", "async-execute", "dismiss"],
            "x-openspp-batch-limit": MAX_BATCH_GEOMETRIES,
            "inputs": {
                "geometry": {
                    "title": "Query Geometry",
                    "description": (
                        f"GeoJSON Polygon or MultiPolygon. Provide one for a single query, "
                        f"or an array of {{id, value}} objects for batch processing. "
                        f"Maximum {MAX_BATCH_GEOMETRIES} geometries."
                    ),
                    "minOccurs": 1,
                    "maxOccurs": MAX_BATCH_GEOMETRIES,
                    "schema": {
                        "oneOf": [
                            {"format": "geojson-geometry"},
                            {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "value": {"format": "geojson-geometry"},
                                },
                                "required": ["id", "value"],
                            },
                        ],
                    },
                },
                "variables": self._build_variables_input(),
                "group_by": self._build_group_by_input(),
                "filters": {
                    "title": "Registrant Filters",
                    "description": "Additional filters (e.g., is_group, disabled).",
                    "minOccurs": 0,
                    "schema": {"type": "object"},
                },
                "population_filter": self._build_population_filter_input(),
            },
            "outputs": {
                "result": {
                    "title": "Statistics Result",
                    "schema": {
                        "oneOf": [
                            {
                                "type": "object",
                                "description": "Single geometry result",
                                "properties": {
                                    "total_count": {"type": "integer"},
                                    "query_method": {"type": "string"},
                                    "areas_matched": {"type": "integer"},
                                    "statistics": {"type": "object"},
                                    "access_level": {"type": "string"},
                                    "computed_at": {"type": "string", "format": "date-time"},
                                },
                                "required": ["total_count", "query_method", "areas_matched", "statistics"],
                            },
                            {
                                "type": "object",
                                "description": "Batch result (when multiple geometries provided)",
                                "properties": {
                                    "results": {"type": "array"},
                                    "summary": {"type": "object"},
                                },
                                "required": ["results", "summary"],
                            },
                        ],
                    },
                },
            },
        }

    def _build_proximity_statistics_description(self):
        """Build full process description for proximity-statistics."""
        return {
            "id": PROXIMITY_STATISTICS,
            "title": "Proximity Statistics",
            "description": (
                "Compute aggregate registrant statistics within or beyond a given "
                "radius from reference points (e.g., health centers, schools)."
            ),
            "version": "1.0.0",
            "jobControlOptions": ["sync-execute", "async-execute", "dismiss"],
            "inputs": {
                "reference_points": {
                    "title": "Reference Points",
                    "description": (
                        f"Locations to measure proximity from. Maximum {DEFAULT_MAX_PROXIMITY_POINTS:,} points."
                    ),
                    "minOccurs": 1,
                    "maxOccurs": DEFAULT_MAX_PROXIMITY_POINTS,
                    "x-openspp-batch-limit": DEFAULT_MAX_PROXIMITY_POINTS,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                            "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                        },
                        "required": ["longitude", "latitude"],
                    },
                },
                "radius_km": {
                    "title": "Search Radius",
                    "description": "Search radius in kilometers.",
                    "schema": {"type": "number", "exclusiveMinimum": 0, "maximum": 500},
                },
                "relation": {
                    "title": "Spatial Relation",
                    "description": "'within' returns registrants inside the radius; 'beyond' returns those outside.",
                    "minOccurs": 0,
                    "schema": {"type": "string", "enum": ["within", "beyond"], "default": "within"},
                },
                "variables": self._build_variables_input(),
                "group_by": self._build_group_by_input(),
                "filters": {
                    "title": "Registrant Filters",
                    "minOccurs": 0,
                    "schema": {"type": "object"},
                },
                "population_filter": self._build_population_filter_input(),
            },
            "outputs": {
                "result": {
                    "title": "Proximity Statistics Result",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "total_count": {"type": "integer"},
                            "query_method": {"type": "string"},
                            "areas_matched": {"type": "integer"},
                            "reference_points_count": {"type": "integer"},
                            "radius_km": {"type": "number"},
                            "relation": {"type": "string"},
                            "statistics": {"type": "object"},
                            "access_level": {"type": "string"},
                            "computed_at": {"type": "string", "format": "date-time"},
                        },
                        "required": ["total_count", "query_method", "areas_matched", "statistics"],
                    },
                },
            },
        }
