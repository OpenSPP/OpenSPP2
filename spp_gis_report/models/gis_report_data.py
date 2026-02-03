import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class GISReportData(models.Model):
    """Computed Data Cache for GIS Reports.

    Stores pre-computed aggregated values for each area to enable
    fast map rendering and API responses. Data is refreshed based
    on the report's refresh settings.
    """

    _name = "spp.gis.report.data"
    _description = "GIS Report Computed Data"
    _order = "area_id"

    def init(self):
        """Create database indexes for optimal query performance.

        These indexes are critical for million-record scale:
        - Composite index on (report_id, area_level) for API filtering
        - Partial index on res_partner for registrant aggregation
        """
        # Index for GIS report data queries (filtering by report and level)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_gis_report_data_report_level
            ON spp_gis_report_data(report_id, area_level)
        """)

        # Partial index on res_partner for efficient registrant aggregation
        # This dramatically speeds up COUNT queries with is_registrant filter
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_partner_area_registrant
            ON res_partner(area_id)
            WHERE is_registrant = true AND active = true
        """)

        # Index for area hierarchy lookups during rollup
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_area_parent_level
            ON spp_area(parent_id, area_level)
        """)

        _logger.info("GIS Report performance indexes created/verified")

    # ===== Primary Relations =====
    report_id = fields.Many2one(
        "spp.gis.report",
        "Report",
        required=True,
        ondelete="cascade",
        index=True,
        help="The report this data belongs to",
    )
    area_id = fields.Many2one(
        "spp.area",
        "Area",
        required=True,
        ondelete="cascade",
        index=True,
        help="The area this data is for",
    )

    # ===== Area Metadata (denormalized for performance) =====
    area_code = fields.Char(
        "Area Code",
        related="area_id.code",
        store=True,
        help="Area code for quick filtering",
    )
    area_name = fields.Char(
        "Area Name",
        related="area_id.name",
        store=True,
        help="Area name for display",
    )
    area_level = fields.Integer(
        "Area Level",
        related="area_id.area_level",
        store=True,
        index=True,
        help="Administrative level",
    )
    parent_area_id = fields.Many2one(
        "spp.area",
        "Parent Area",
        related="area_id.parent_id",
        store=True,
        help="Parent area in hierarchy",
    )

    # ===== Computed Values =====
    raw_value = fields.Float(
        "Raw Value",
        digits=(16, 4),
        help="Aggregated raw value before normalization",
    )
    normalized_value = fields.Float(
        "Normalized Value",
        digits=(16, 4),
        help="Normalized value for visualization",
    )
    display_value = fields.Char(
        "Display Value",
        compute="_compute_display_value",
        help="Formatted value for display",
    )

    # For weighted averages and percentage calculations
    weight = fields.Float(
        "Weight/Denominator",
        help="Used for rollup calculations and percentages",
    )
    record_count = fields.Integer(
        "Source Record Count",
        help="Number of source records aggregated",
    )

    # ===== Rollup Metadata =====
    is_rollup = fields.Boolean(
        "Is Rollup",
        default=False,
        index=True,
        help="True if this is a rolled-up parent value",
    )
    source_area_count = fields.Integer(
        "Child Areas Included",
        help="Number of child areas included in rollup",
    )

    # ===== Threshold Bucket =====
    bucket_index = fields.Integer(
        "Bucket Index",
        help="0-based index into threshold_ids",
    )
    bucket_color = fields.Char(
        "Bucket Color",
        help="Hex color for this bucket",
    )
    bucket_label = fields.Char(
        "Bucket Label",
        help="Human-readable label for this bucket",
    )

    # ===== Disaggregation Data =====
    disaggregation = fields.Json(
        "Disaggregation Data",
        help="Breakdown by gender, age, disability, etc. "
        'Example: {"gender": {"male": 580, "female": 670}}',
    )

    # ===== Cache Metadata =====
    computed_at = fields.Datetime(
        "Computed At",
        required=True,
        default=fields.Datetime.now,
        help="When this data was computed",
    )
    is_stale = fields.Boolean(
        "Is Stale",
        compute="_compute_is_stale",
        store=True,
        help="Whether this data needs refreshing",
    )

    _report_area_unique = models.Constraint(
        "UNIQUE(report_id, area_id)",
        "One data record per report/area combination",
    )

    @api.depends("raw_value", "normalized_value", "report_id.normalization_method")
    def _compute_display_value(self):
        """Format the value for display with appropriate units."""
        for data in self:
            if not data.report_id:
                data.display_value = ""
                continue

            # Handle None values (no data for this area)
            value = data.normalized_value if data.normalized_value is not None else data.raw_value
            if value is None:
                data.display_value = "No Data"
                continue

            method = data.report_id.normalization_method

            if method == "raw":
                data.display_value = f"{value:,.0f}"
            elif method == "per_area_sqkm":
                data.display_value = f"{value:.2f} per km²"
            elif method == "per_population":
                data.display_value = f"{value:.1f} per 1,000"
            elif method == "per_household":
                data.display_value = f"{value:.1f} per 100"
            elif method == "per_reference":
                data.display_value = f"{value:.1f}%"
            elif method in ("index", "percentile"):
                data.display_value = f"{value:.1f}"
            elif method == "zscore":
                data.display_value = f"{value:+.2f}σ"
            else:
                data.display_value = f"{value:.2f}"

    @api.depends("computed_at", "report_id.refresh_interval")
    def _compute_is_stale(self):
        """Determine if this data is stale based on report refresh interval."""
        for data in self:
            if not data.computed_at or not data.report_id:
                data.is_stale = True
                continue

            now = fields.Datetime.now()
            time_diff = now - data.computed_at

            interval = data.report_id.refresh_interval
            if interval == "hourly":
                data.is_stale = time_diff.total_seconds() > 3600
            elif interval == "daily":
                data.is_stale = time_diff.total_seconds() > 86400
            elif interval == "weekly":
                data.is_stale = time_diff.total_seconds() > 604800
            else:
                data.is_stale = False
