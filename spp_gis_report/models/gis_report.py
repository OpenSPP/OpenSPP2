import logging
import statistics
from ast import literal_eval

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools.sql import SQL

_logger = logging.getLogger(__name__)


class GISReport(models.Model):
    """GIS Report Configuration Model.

    Main configuration model where users define what data to visualize
    on a geographic map. Supports various aggregation methods, normalization
    techniques, and hierarchical rollup.
    """

    _name = "spp.gis.report"
    _description = "GIS Report Configuration"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    # ===== Identity Fields =====
    name = fields.Char(
        "Report Name",
        required=True,
        tracking=True,
        help="Descriptive name for the report",
    )
    code = fields.Char(
        "Code",
        required=True,
        index=True,
        help="Unique code identifier for the report",
    )
    description = fields.Text(
        "Description",
        help="Detailed description of the report purpose",
    )
    category_id = fields.Many2one(
        "spp.gis.report.category",
        "Category",
        help="Category for organizing reports",
    )
    sequence = fields.Integer(
        "Sequence",
        default=10,
        help="Display order of the report",
    )
    active = fields.Boolean(
        "Active",
        default=True,
        help="Inactive reports are hidden from views",
    )

    # Template reference (if created from template)
    template_id = fields.Many2one(
        "spp.gis.report.template",
        "Source Template",
        readonly=True,
        help="The template this report was created from",
    )

    # ===== Data Source Configuration =====
    source_model_id = fields.Many2one(
        "ir.model",
        "Source Model",
        required=True,
        ondelete="cascade",
        help="The model to aggregate data from",
    )
    source_model = fields.Char(
        "Source Model Name",
        related="source_model_id.model",
        store=True,
        help="Technical name of the source model",
    )

    @api.model
    def _get_gis_report_source_models(self):
        """Return list of models that can be GIS report data sources.

        Override this method in other modules to add their models.
        For example, spp_drims would override to add 'spp.drims.request':

            def _get_gis_report_source_models(self):
                models = super()._get_gis_report_source_models()
                return models + ['spp.drims.request']

        Returns:
            list: Model technical names (e.g., ['res.partner'])
        """
        return ["res.partner"]

    @api.model
    def _get_source_model_domain(self):
        """Get domain for source_model_id field filtering."""
        models = self._get_gis_report_source_models()
        return [("model", "in", models)]

    area_field_path = fields.Char(
        "Area Field Path",
        required=True,
        default="area_id",
        help="Dot-notation path to the area field (e.g., 'area_id', 'destination_area_id')",
    )

    # ===== Filtering =====
    filter_mode = fields.Selection(
        [
            ("domain", "Simple Domain"),
            ("cel", "CEL Expression"),
        ],
        "Filter Mode",
        default="domain",
        required=True,
        help="How to filter source records",
    )
    filter_domain = fields.Char(
        "Filter Domain",
        default="[]",
        help="Odoo domain for filtering records",
    )
    filter_cel_id = fields.Many2one(
        "spp.cel.expression",
        "Filter Expression",
        domain="[('output_type', '=', 'boolean')]",
        help="CEL expression for advanced filtering",
    )

    # Context filters - extended by other modules (spp_programs, spp_hazard)
    # Override _get_context_domain() to add module-specific context filtering

    # ===== Aggregation Configuration =====
    aggregation_method = fields.Selection(
        [
            ("count", "Count Records"),
            ("sum", "Sum Field"),
            ("avg", "Average Field"),
            ("min", "Minimum"),
            ("max", "Maximum"),
            ("cel", "CEL Expression"),
        ],
        "Aggregation Method",
        default="count",
        required=True,
        help="How to aggregate the data",
    )
    aggregation_field = fields.Char(
        "Aggregation Field",
        help="Field to sum/average (e.g., 'benefit_amount')",
    )
    aggregation_cel_id = fields.Many2one(
        "spp.cel.expression",
        "Aggregation Expression",
        help="Custom CEL formula for complex metrics",
    )

    # Area Level
    base_area_level = fields.Integer(
        "Base Calculation Level",
        required=True,
        default=2,
        help="Administrative level where base calculation occurs (e.g., 2=District)",
    )

    # ===== Normalization Configuration =====
    normalization_method = fields.Selection(
        [
            ("raw", "Raw Value (No Normalization)"),
            ("per_area_sqkm", "Per Square Kilometer"),
            ("per_population", "Per 1,000 Population"),
            ("per_household", "Per 100 Households"),
            ("per_reference", "Percentage of Reference"),
            ("index", "Normalized Index (0-100)"),
            ("percentile", "Percentile Rank"),
            ("zscore", "Z-Score (Standard Deviations)"),
        ],
        "Normalization Method",
        default="raw",
        required=True,
        help="How to normalize the aggregated values",
    )
    reference_indicator_id = fields.Many2one(
        "spp.gis.report",
        "Reference Report",
        help="For 'percentage of reference', the denominator report",
    )
    reference_area_field = fields.Char(
        "Reference Area Field",
        help="Field on spp.area for normalization (e.g., 'population')",
    )

    # ===== Hierarchy Rollup Configuration =====
    enable_rollup = fields.Boolean(
        "Enable Hierarchy Rollup",
        default=True,
        help="Automatically compute values for parent areas",
    )
    rollup_method = fields.Selection(
        [
            ("sum", "Sum"),
            ("weighted_avg", "Weighted Average"),
            ("avg", "Simple Average"),
            ("min", "Minimum"),
            ("max", "Maximum"),
        ],
        "Rollup Method",
        default="sum",
        help="How to aggregate child values to parent levels",
    )
    rollup_weight_source = fields.Selection(
        [
            ("count", "Record Count"),
            ("area_sqkm", "Area Size (km²)"),
            ("population", "Population"),
            ("custom", "Custom Field"),
        ],
        "Rollup Weight Source",
        default="count",
        help="What to use as weight for weighted averages",
    )
    rollup_weight_field = fields.Char(
        "Custom Weight Field",
        help="Custom field to use for rollup weights",
    )

    # ===== Visualization Configuration =====
    color_scheme_id = fields.Many2one(
        "spp.gis.color.scheme",
        "Color Scheme",
        default=lambda self: self.env["spp.gis.color.scheme"].get_default_scheme(),
        required=True,
        help="Color scheme for visualizing thresholds. Color-blind safe schemes are recommended.",
    )
    threshold_ids = fields.One2many(
        "spp.gis.report.threshold",
        "report_id",
        "Thresholds",
        help="Manual threshold definitions",
    )
    threshold_mode = fields.Selection(
        [
            ("auto_quartile", "Auto: Quartiles"),
            ("auto_equal", "Auto: Equal Intervals"),
            ("auto_jenks", "Auto: Natural Breaks"),
            ("auto_stddev", "Auto: Standard Deviation"),
            ("manual", "Manual Thresholds"),
        ],
        "Threshold Mode",
        default="auto_quartile",
        help="How to calculate color thresholds",
    )
    bucket_count = fields.Integer(
        "Number of Buckets",
        default=4,
        help="Number of color buckets for auto thresholds",
    )

    # ===== Geometry & Layer Configuration =====
    geometry_type = fields.Selection(
        [
            ("polygon", "Polygon (Choropleth)"),
            ("point", "Point Markers"),
            ("cluster", "Clustered Points"),
            ("heatmap", "Heatmap"),
        ],
        "Geometry Type",
        default="polygon",
        required=True,
        help="How to visualize the data on the map. "
        "Polygon: Fill areas with colors based on values. "
        "Point: Show markers at area centroids. "
        "Cluster: Group nearby points. "
        "Heatmap: Show density visualization.",
    )
    auto_create_layer = fields.Boolean(
        "Auto-Create Map Layer",
        default=True,
        help="Automatically create and sync a GIS data layer for this report",
    )
    layer_id = fields.Many2one(
        "spp.gis.data.layer",
        "Map Layer",
        readonly=True,
        ondelete="set null",
        help="The auto-created map layer for this report",
    )
    layer_active_on_startup = fields.Boolean(
        "Show Layer on Map Load",
        default=False,
        help="Whether the layer is visible when the map first loads",
    )

    # ===== Disaggregation Configuration =====
    dimension_ids = fields.Many2many(
        "spp.demographic.dimension",
        string="Disaggregation Dimensions",
        help="Demographic dimensions to compute disaggregation for (e.g., gender, age group)",
    )
    member_expansion = fields.Selection(
        [("none", "No Expansion"), ("expand", "Expand to Members")],
        "Member Expansion",
        default="none",
        help=(
            "For group-filtered reports, expand to individual members "
            "for demographic breakdown (e.g., gender, age). "
            "Use 'Expand to Members' when dimensions should be evaluated "
            "on individuals inside groups, not on the groups themselves."
        ),
    )

    disaggregate_by_tag_ids = fields.Many2many(
        "spp.vocabulary",
        string="Disaggregate by Tags",
        domain="[('namespace_uri', '=like', 'urn:openspp:vocab:registrant-tags%')]",
        help="Tag vocabularies to show breakdown for in disaggregation",
    )

    # ===== Refresh Settings =====
    refresh_mode = fields.Selection(
        [
            ("manual", "Manual Only"),
            ("scheduled", "Scheduled"),
            ("on_change", "On Data Change"),
        ],
        "Refresh Mode",
        default="scheduled",
        required=True,
        help="When to refresh the computed data",
    )
    refresh_interval = fields.Selection(
        [
            ("hourly", "Every Hour"),
            ("daily", "Daily (Overnight)"),
            ("weekly", "Weekly"),
        ],
        "Refresh Interval",
        default="daily",
        help="How often to refresh on schedule",
    )
    cron_id = fields.Many2one(
        "ir.cron",
        "Scheduled Job",
        readonly=True,
        help="The cron job for scheduled refreshes",
    )
    last_refresh = fields.Datetime(
        "Last Refreshed",
        readonly=True,
        help="Timestamp of last data refresh",
    )
    next_refresh = fields.Datetime(
        "Next Scheduled Refresh",
        compute="_compute_next_refresh",
        help="When the next scheduled refresh will occur",
    )
    is_stale = fields.Boolean(
        "Data is Stale",
        compute="_compute_is_stale",
        help="Whether the data needs refreshing",
    )

    # ===== Access Control =====
    access_group_ids = fields.Many2many(
        "res.groups",
        "spp_gis_report_access_groups_rel",
        "report_id",
        "group_id",
        string="Viewer Groups",
        help="Groups that can view this report. Empty = all users.",
    )
    editor_group_ids = fields.Many2many(
        "res.groups",
        "spp_gis_report_editor_groups_rel",
        "report_id",
        "group_id",
        string="Editor Groups",
        help="Groups that can modify this report.",
    )

    # ===== Computed Data Relations =====
    data_ids = fields.One2many(
        "spp.gis.report.data",
        "report_id",
        "Computed Data",
        help="Cached computed data for this report",
    )
    data_count = fields.Integer(
        "Data Count",
        compute="_compute_data_count",
        help="Number of computed data records",
    )
    is_syncing = fields.Boolean(
        "Sync In Progress",
        readonly=True,
        copy=False,
        help="Set when a background sync job is queued, cleared when it completes",
    )

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "Report code must be unique",
    )

    @api.depends("data_ids")
    def _compute_data_count(self):
        """Compute the number of data records for this report."""
        for report in self:
            report.data_count = len(report.data_ids)

    @api.depends("cron_id", "refresh_interval")
    def _compute_next_refresh(self):
        """Compute the next scheduled refresh time."""
        for report in self:
            if report.cron_id and report.cron_id.nextcall:
                report.next_refresh = report.cron_id.nextcall
            else:
                report.next_refresh = False

    @api.depends("last_refresh", "refresh_interval")
    def _compute_is_stale(self):
        """Determine if the data is stale based on refresh interval."""
        for report in self:
            if not report.last_refresh:
                report.is_stale = True
                continue

            # Check if data is older than the refresh interval
            now = fields.Datetime.now()
            time_diff = now - report.last_refresh

            if report.refresh_interval == "hourly":
                report.is_stale = time_diff.total_seconds() > 3600
            elif report.refresh_interval == "daily":
                report.is_stale = time_diff.total_seconds() > 86400
            elif report.refresh_interval == "weekly":
                report.is_stale = time_diff.total_seconds() > 604800
            else:
                report.is_stale = False

    @api.constrains("member_expansion", "source_model")
    def _check_member_expansion(self):
        """Validate member_expansion is only used with res.partner source model."""
        for report in self:
            if report.member_expansion == "expand" and report.source_model != "res.partner":
                raise ValidationError(
                    _("Member expansion is only supported for reports with 'Contact' (res.partner) source model.")
                )

    def _prepare_area_context(self):
        """Build shared area context for aggregation and disaggregation.

        Computes the filter domain, area field, base areas, and the
        child_to_base mapping that maps descendant areas to their
        base-level ancestor. Both _compute_base_aggregation and
        _compute_disaggregation use this context.

        Returns:
            dict: Area context with keys:
                - domain: list, the filter domain including area filter
                - child_to_base: dict, mapping area_id -> base_area_id
                - base_areas: recordset, areas at base_area_level
                - area_field: str, first part of area_field_path
            Returns None if no source model or no base areas exist.
        """
        self.ensure_one()

        if not self.source_model:
            _logger.warning("No source model configured for report ID %s", self.id)
            return None

        domain = self._build_filter_domain()
        area_field = self.area_field_path.split(".")[0]

        base_areas = self.env["spp.area"].search([("area_level", "=", self.base_area_level)])
        if not base_areas:
            _logger.info("No areas at level %s found", self.base_area_level)
            return None

        # Build mapping from descendant areas to their base-level ancestor.
        # Registrants may be assigned to areas more granular than base_area_level
        # (e.g., barangays when base level is municipality). We include all
        # descendant areas in the query and aggregate results back to the
        # base-level parent.
        child_to_base = {base_area.id: base_area.id for base_area in base_areas}
        all_descendants = self.env["spp.area"].search(
            [
                ("id", "child_of", base_areas.ids),
                ("id", "not in", base_areas.ids),
            ]
        )
        for desc in all_descendants:
            ancestor = desc.parent_id
            while ancestor and ancestor.id not in child_to_base:
                ancestor = ancestor.parent_id
            if ancestor:
                child_to_base[desc.id] = child_to_base[ancestor.id]

        # Add area filter to domain
        domain.append((area_field, "in", list(child_to_base.keys())))

        return {
            "domain": domain,
            "child_to_base": child_to_base,
            "base_areas": base_areas,
            "area_field": area_field,
        }

    def _compute_base_aggregation(self, area_context=None):
        """Compute aggregated values at the base area level.

        Uses Odoo's read_group for efficient aggregation. For very large
        datasets (1M+ records), consider using PostGIS-optimized SQL queries.

        Args:
            area_context: Optional pre-computed area context from _prepare_area_context().
                If not provided, it will be computed internally.

        Returns:
            dict: {area_id: {'raw': float, 'count': int, 'weight': float}}
        """
        self.ensure_one()
        _logger.info("Computing base aggregation for report ID %s", self.id)

        if area_context is None:
            area_context = self._prepare_area_context()

        if area_context is None:
            return {}

        Model = self.env[self.source_model]
        domain = list(area_context["domain"])
        area_field = area_context["area_field"]
        base_areas = area_context["base_areas"]
        child_to_base = area_context["child_to_base"]

        # Initialize results for all base areas with 0
        # This ensures areas with no matching records get 0 instead of being missing
        results = {area.id: {"raw": 0, "count": 0, "weight": 0} for area in base_areas}

        if self.aggregation_method == "count":
            # Efficient count using read_group
            groups = Model.read_group(
                domain,
                [area_field],
                [area_field],
            )
            for group in groups:
                if group[area_field]:
                    area_id = group[area_field][0]
                    base_id = child_to_base.get(area_id, area_id)
                    count = group[f"{area_field}_count"]
                    results[base_id]["raw"] += count
                    results[base_id]["count"] += count
                    results[base_id]["weight"] += count

        elif self.aggregation_method in ("sum", "avg", "min", "max"):
            if not self.aggregation_field:
                _logger.warning("No aggregation_field set for %s method", self.aggregation_method)
                return {}

            # Aggregate with specific field
            agg_func = self.aggregation_method
            groups = Model.read_group(
                domain,
                [area_field, f"{self.aggregation_field}:{agg_func}"],
                [area_field],
            )
            for group in groups:
                if group[area_field]:
                    area_id = group[area_field][0]
                    base_id = child_to_base.get(area_id, area_id)
                    value = group.get(self.aggregation_field) or 0
                    count = group[f"{area_field}_count"]
                    if agg_func == "avg":
                        # Accumulate weighted sum so we can compute a proper
                        # weighted average across subgroups when rolling up.
                        results[base_id]["raw"] += value * count
                    elif agg_func == "sum":
                        # read_group already returns the sum for the subgroup;
                        # multiplying by count would inflate the total.
                        results[base_id]["raw"] += value
                    elif agg_func == "min":
                        # Keep the lowest value seen across subgroups.
                        if results[base_id]["count"] == 0:
                            results[base_id]["raw"] = value
                        else:
                            results[base_id]["raw"] = min(results[base_id]["raw"], value)
                    elif agg_func == "max":
                        # Keep the highest value seen across subgroups.
                        if results[base_id]["count"] == 0:
                            results[base_id]["raw"] = value
                        else:
                            results[base_id]["raw"] = max(results[base_id]["raw"], value)
                    results[base_id]["count"] += count
                    results[base_id]["weight"] += count

            # For avg: convert accumulated weighted sum back to weighted average
            if agg_func == "avg":
                for data in results.values():
                    if data["count"] > 0:
                        data["raw"] = data["raw"] / data["count"]

        # Fill in None for areas with no data (distinguishes "no data" from "zero count")
        for area in base_areas:
            if area.id not in results:
                results[area.id] = {
                    "raw": None,  # None = no data, 0 = actual zero count
                    "count": 0,
                    "weight": 0,
                    "has_data": False,
                }

        return results

    def _compute_disaggregation(self, area_context):
        """Compute disaggregation counts per area for configured dimensions.

        Uses SQL for performance when possible, with Python fallback for
        dimensions that cannot compile to SQL. When member_expansion is
        "expand", drills into group members to evaluate individual-level
        demographics (gender, age) with area inheritance from the group.

        Args:
            area_context: Area context from _prepare_area_context()

        Returns:
            dict: {area_id: {dim_name: {raw_value: count}}}
                  Empty dict if no dimensions or non-partner source model.
        """
        self.ensure_one()

        if not self.dimension_ids:
            return {}

        if self.source_model != "res.partner":
            return {}

        if area_context is None:
            return {}

        child_to_base = area_context["child_to_base"]
        area_field = area_context["area_field"]

        # Compile dimensions to SQL, separating compilable from fallback
        sql_dims = []  # [(dimension, SQLColumnResult)]
        fallback_dims = []  # [dimension]
        alias_counter = 0
        partner_alias = "ind" if self.member_expansion == "expand" else "reg"

        for dimension in self.dimension_ids:
            result = dimension.to_sql_column(partner_alias, alias_counter)
            if result is not None:
                sql_dims.append((dimension, result))
                alias_counter = result.alias_counter
            else:
                fallback_dims.append(dimension)

        results = {}

        if sql_dims:
            results = self._disaggregation_sql(area_context, sql_dims, child_to_base, area_field, partner_alias)

        if fallback_dims:
            fallback_results = self._disaggregation_python(area_context, fallback_dims, child_to_base, area_field)
            # Merge fallback results into main results
            for area_id, dim_data in fallback_results.items():
                results.setdefault(area_id, {}).update(dim_data)

        return results

    def _disaggregation_sql(self, area_context, sql_dims, child_to_base, area_field, partner_alias):
        """Execute SQL-based disaggregation query.

        Builds a single SQL query that:
        1. Maps descendant areas to base-level areas via CTE
        2. Optionally expands group membership to individuals (DISTINCT)
        3. Computes all dimension values as SQL expressions
        4. Unpivots dimensions via CROSS JOIN LATERAL VALUES
        5. Groups by area + dimension + value
        """
        domain = list(area_context["domain"])

        # Get matching registrant IDs (respects record rules via search())
        Partner = self.env["res.partner"]
        registrant_ids = Partner.search(domain, order="id").ids
        if not registrant_ids:
            return {}

        # Build area_mapping CTE from child_to_base dict
        area_mapping_values = SQL(", ").join(
            SQL("(%s, %s)", child_id, base_id) for child_id, base_id in child_to_base.items()
        )
        area_mapping_cte = SQL(
            "area_mapping(child_id, base_id) AS (VALUES %s)",
            area_mapping_values,
        )

        # Collect all JOINs from dimension compilations
        all_joins = []
        for _dim, col_result in sql_dims:
            all_joins.extend(col_result.joins)

        # Build the dimension SELECT columns and VALUES entries
        dim_select_parts = []
        dim_values_entries = []
        for dim, col_result in sql_dims:
            col_alias = f"dim_{dim.name}"
            dim_select_parts.append(SQL("%s AS %s", col_result.expression, SQL.identifier(col_alias)))
            dim_values_entries.append(SQL("(%s, %s)", dim.name, SQL.identifier(col_alias)))

        dim_select_sql = SQL(", ").join(dim_select_parts)
        dim_values_sql = SQL(", ").join(dim_values_entries)

        if self.member_expansion == "expand":
            query = self._build_expand_query(
                registrant_ids, area_mapping_cte, area_field, all_joins, dim_select_sql, dim_values_sql
            )
        else:
            query = self._build_direct_query(
                registrant_ids,
                area_mapping_cte,
                area_field,
                all_joins,
                dim_select_sql,
                dim_values_sql,
                partner_alias,
            )

        self.env.cr.execute(query)
        rows = self.env.cr.fetchall()

        # Parse results: (base_area_id, dim_name, dim_value, count)
        results = {}
        for base_area_id, dim_name, dim_value, cnt in rows:
            area_disagg = results.setdefault(base_area_id, {})
            dim_counts = area_disagg.setdefault(dim_name, {})
            dim_counts[dim_value] = cnt

        return results

    def _build_expand_query(
        self, registrant_ids, area_mapping_cte, area_field, all_joins, dim_select_sql, dim_values_sql
    ):
        """Build SQL query with member expansion (groups -> individuals)."""
        area_field_col = SQL.identifier(area_field)

        # Build JOINs string
        joins_sql = SQL(" ").join(all_joins) if all_joins else SQL("")

        return SQL(
            """
            WITH %s,
            expanded AS (
                SELECT DISTINCT ON (ind.id)
                    am.base_id AS resolved_area_id,
                    ind.id AS individual_id,
                    %s
                FROM res_partner grp
                JOIN spp_group_membership gm ON gm.%s = grp.id AND NOT gm.%s
                JOIN res_partner ind ON ind.id = gm.%s
                %s
                JOIN area_mapping am ON am.child_id = COALESCE(ind.%s, grp.%s)
                WHERE grp.id IN %s
                ORDER BY ind.id, grp.id
            )
            SELECT resolved_area_id, dim_name, dim_value, COUNT(*) AS cnt
            FROM expanded
            CROSS JOIN LATERAL (VALUES %s) AS dims(dim_name, dim_value)
            GROUP BY resolved_area_id, dim_name, dim_value
            """,
            area_mapping_cte,
            dim_select_sql,
            SQL.identifier("group"),
            SQL.identifier("is_ended"),
            SQL.identifier("individual"),
            joins_sql,
            area_field_col,
            area_field_col,
            tuple(registrant_ids),
            dim_values_sql,
        )

    def _build_direct_query(
        self, registrant_ids, area_mapping_cte, area_field, all_joins, dim_select_sql, dim_values_sql, partner_alias
    ):
        """Build SQL query for direct registrant disaggregation (no expansion)."""
        area_field_col = SQL.identifier(area_field)
        alias_id = SQL.identifier(partner_alias)

        # Build JOINs string
        joins_sql = SQL(" ").join(all_joins) if all_joins else SQL("")

        return SQL(
            """
            WITH %s,
            registrants AS (
                SELECT
                    am.base_id AS resolved_area_id,
                    %s.id AS registrant_id,
                    %s
                FROM res_partner %s
                %s
                JOIN area_mapping am ON am.child_id = %s.%s
                WHERE %s.id IN %s
            )
            SELECT resolved_area_id, dim_name, dim_value, COUNT(*) AS cnt
            FROM registrants
            CROSS JOIN LATERAL (VALUES %s) AS dims(dim_name, dim_value)
            GROUP BY resolved_area_id, dim_name, dim_value
            """,
            area_mapping_cte,
            alias_id,
            dim_select_sql,
            alias_id,
            joins_sql,
            alias_id,
            area_field_col,
            alias_id,
            tuple(registrant_ids),
            dim_values_sql,
        )

    def _disaggregation_python(self, area_context, fallback_dims, child_to_base, area_field):
        """Python fallback for dimensions that couldn't compile to SQL.

        Uses the existing ORM-based evaluation path via the dimension cache.
        When member_expansion is "expand", fetches individual members first.
        """
        domain = list(area_context["domain"])
        base_areas = area_context["base_areas"]

        Partner = self.env["res.partner"]
        registrants = Partner.search_read(domain, [area_field], order="id")
        if not registrants:
            return {}

        if self.member_expansion == "expand":
            return self._disaggregation_python_expanded(registrants, fallback_dims, child_to_base, area_field)

        # Direct mode: evaluate on the matching registrants
        area_registrant_ids = {}
        all_registrant_ids = []
        for reg in registrants:
            area_val = reg[area_field]
            if not area_val:
                continue
            area_id = area_val[0] if isinstance(area_val, (list, tuple)) else area_val
            base_id = child_to_base.get(area_id)
            if base_id is None:
                continue
            area_registrant_ids.setdefault(base_id, []).append(reg["id"])
            all_registrant_ids.append(reg["id"])

        if not all_registrant_ids:
            return {}

        cache_service = self.env["spp.metrics.dimension.cache"]
        dim_evaluations = {}
        for dimension in fallback_dims:
            dim_evaluations[dimension.name] = cache_service.evaluate_dimension_batch(dimension, all_registrant_ids)

        results = {}
        for area_id in base_areas.ids:
            reg_ids = area_registrant_ids.get(area_id, [])
            if not reg_ids:
                continue
            area_disagg = {}
            for dimension in fallback_dims:
                evals = dim_evaluations[dimension.name]
                value_counts = {}
                for rid in reg_ids:
                    value = evals.get(rid, dimension.default_value or "unknown")
                    value_counts[value] = value_counts.get(value, 0) + 1
                area_disagg[dimension.name] = value_counts
            results[area_id] = area_disagg

        return results

    def _disaggregation_python_expanded(self, group_registrants, fallback_dims, child_to_base, area_field):
        """Python fallback with member expansion for group-filtered reports."""
        group_ids = [r["id"] for r in group_registrants]
        if not group_ids:
            return {}

        # Build group area mapping
        group_area = {}
        for reg in group_registrants:
            area_val = reg[area_field]
            if area_val:
                area_id = area_val[0] if isinstance(area_val, (list, tuple)) else area_val
                group_area[reg["id"]] = area_id

        # Find individual members of these groups
        Membership = self.env["spp.group.membership"]
        memberships = Membership.search_read(
            [("group", "in", group_ids), ("is_ended", "=", False)],
            ["individual", "group"],
        )

        if not memberships:
            return {}

        # Build individual -> base_area mapping, inheriting from group
        seen_individuals = set()
        individual_area = {}
        all_individual_ids = []

        for mem in memberships:
            ind_id = mem["individual"][0] if isinstance(mem["individual"], (list, tuple)) else mem["individual"]
            if ind_id in seen_individuals:
                continue
            seen_individuals.add(ind_id)
            all_individual_ids.append(ind_id)

            grp_id = mem["group"][0] if isinstance(mem["group"], (list, tuple)) else mem["group"]
            # Individual's area or inherited from group
            grp_area_id = group_area.get(grp_id)
            if grp_area_id:
                base_id = child_to_base.get(grp_area_id)
                if base_id:
                    individual_area[ind_id] = base_id

        if not all_individual_ids:
            return {}

        cache_service = self.env["spp.metrics.dimension.cache"]
        dim_evaluations = {}
        for dimension in fallback_dims:
            dim_evaluations[dimension.name] = cache_service.evaluate_dimension_batch(dimension, all_individual_ids)

        results = {}
        for ind_id in all_individual_ids:
            base_id = individual_area.get(ind_id)
            if base_id is None:
                continue
            area_disagg = results.setdefault(base_id, {})
            for dimension in fallback_dims:
                evals = dim_evaluations[dimension.name]
                value = evals.get(ind_id, dimension.default_value or "unknown")
                dim_counts = area_disagg.setdefault(dimension.name, {})
                dim_counts[value] = dim_counts.get(value, 0) + 1

        return results

    def _build_filter_domain(self):
        """Build the complete filter domain including context filters.

        Returns:
            list: Odoo domain expression
        """
        self.ensure_one()
        domain = []

        # Parse filter domain
        if self.filter_mode == "domain" and self.filter_domain:
            try:
                parsed = literal_eval(self.filter_domain)
                if parsed:
                    domain = expression.AND([domain, parsed])
            except (ValueError, SyntaxError) as e:
                _logger.warning("Invalid filter domain: %s - %s", self.filter_domain, e)

        # Apply context filters (extended by other modules)
        domain = self._apply_context_filters(domain)

        return domain

    def _apply_context_filters(self, domain):
        """Apply module-specific context filters to the domain.

        Override this method in other modules to add context filtering.
        For example, spp_programs could add program context filtering.

        Args:
            domain: Current domain list

        Returns:
            Modified domain list
        """
        return domain

    def _normalize_value(self, raw_value, area, weight=None):
        """Apply normalization to a raw value.

        Args:
            raw_value: The aggregated raw value (can be None for no-data areas)
            area: spp.area record
            weight: Optional weight/denominator for percentage calculations

        Returns:
            Normalized float value, or None if raw_value is None (no data)
        """
        self.ensure_one()

        # Preserve None for areas with no data
        if raw_value is None:
            return None

        if self.normalization_method == "raw":
            return raw_value

        elif self.normalization_method == "per_area_sqkm":
            if area.area_sqkm:
                return raw_value / area.area_sqkm
            return None  # Can't normalize without area size

        elif self.normalization_method == "per_population":
            if area.population:
                return (raw_value / area.population) * 1000  # Per 1,000
            return None  # Can't normalize without population

        elif self.normalization_method == "per_household":
            if area.household_count:
                return (raw_value / area.household_count) * 100  # Per 100
            return None  # Can't normalize without household count

        elif self.normalization_method == "per_reference":
            if weight:
                return (raw_value / weight) * 100  # Percentage
            return None  # Can't normalize without reference

        # Statistical methods require all values - handled in post-processing
        elif self.normalization_method in ("index", "percentile", "zscore"):
            return None

        return raw_value

    def _compute_hierarchy_rollup(self, base_results):  # noqa: C901
        """Roll up values from base level to all parent levels.

        Starting from base_area_level, aggregates values upward through
        the area hierarchy to all parent levels (e.g., district → region → country).

        Optimized for large datasets - uses batch queries instead of N+1 pattern.

        Args:
            base_results: dict {area_id: {'raw': float, 'count': int, 'weight': float}}

        Returns:
            dict: {area_id: {'raw': float, 'count': int, 'weight': float, 'is_rollup': bool}}
        """
        self.ensure_one()
        _logger.info("Computing hierarchy rollup for report ID %s", self.id)

        if not self.enable_rollup:
            # Mark base results as non-rollup and return
            for area_id in base_results:
                base_results[area_id]["is_rollup"] = False
                base_results[area_id]["source_area_count"] = 1
            return base_results

        # Start with base results marked as non-rollup
        all_results = {}
        for area_id, data in base_results.items():
            all_results[area_id] = {
                **data,
                "is_rollup": False,
                "source_area_count": 1,
            }

        # Get all areas we have data for
        area_ids = list(base_results.keys())
        if not area_ids:
            return all_results

        # OPTIMIZATION: Batch load all areas with their parent_id, area_sqkm, population
        # This avoids N+1 queries in the loop below
        all_area_ids_in_results = set(area_ids)
        areas_data = {}  # {area_id: {'parent_id': int, 'area_sqkm': float, 'population': int}}

        # Build parent chain - process level by level going up
        base_level = self.base_area_level
        current_level = base_level - 1
        current_level_area_ids = area_ids

        while current_level >= 0:
            # Get parent IDs from child areas at current level
            child_areas = self.env["spp.area"].browse(current_level_area_ids)
            parent_ids = child_areas.mapped("parent_id.id")
            parent_ids = [pid for pid in parent_ids if pid]  # Filter out None

            if not parent_ids:
                break

            # Get parent areas at the current level
            parent_areas = self.env["spp.area"].search(
                [
                    ("area_level", "=", current_level),
                    ("id", "in", parent_ids),
                ]
            )

            if not parent_areas:
                break

            # OPTIMIZATION: Batch load area metadata for all areas in current results
            # Only load areas we haven't loaded yet
            areas_to_load = [aid for aid in all_area_ids_in_results if aid not in areas_data]
            if areas_to_load:
                loaded_areas = self.env["spp.area"].browse(areas_to_load)
                # Prefetch all fields we need in one query
                loaded_areas.read(["parent_id", "area_sqkm", "population"])
                for area in loaded_areas:
                    areas_data[area.id] = {
                        "parent_id": area.parent_id.id if area.parent_id else None,
                        "area_sqkm": area.area_sqkm or 0.0,
                        "population": area.population or 0,
                    }

            # Build parent -> children mapping using cached data
            parent_children_map = {}  # {parent_id: [child_ids]}
            for aid in all_results.keys():
                if aid not in areas_data:
                    # Load if not yet loaded (shouldn't happen but safety check)
                    area = self.env["spp.area"].browse(aid)
                    areas_data[aid] = {
                        "parent_id": area.parent_id.id if area.parent_id else None,
                        "area_sqkm": area.area_sqkm or 0.0,
                        "population": area.population or 0,
                    }
                parent_id = areas_data[aid]["parent_id"]
                if parent_id in parent_areas.ids:
                    if parent_id not in parent_children_map:
                        parent_children_map[parent_id] = []
                    parent_children_map[parent_id].append(aid)

            # For each parent, aggregate its children
            for parent in parent_areas:
                child_ids = parent_children_map.get(parent.id, [])
                if not child_ids:
                    continue

                # Aggregate based on rollup method
                # Filter out children with None raw values (no data) for aggregation
                all_child_data = [all_results[cid] for cid in child_ids]
                child_data_with_values = [
                    (cid, d) for cid, d in zip(child_ids, all_child_data, strict=False) if d.get("raw") is not None
                ]

                # If all children have no data, parent has no data
                if not child_data_with_values:
                    all_results[parent.id] = {
                        "raw": None,
                        "count": 0,
                        "weight": 0,
                        "is_rollup": True,
                        "source_area_count": len(child_ids),
                        "has_data": False,
                    }
                    all_area_ids_in_results.add(parent.id)
                    continue

                valid_child_ids = [cid for cid, _ in child_data_with_values]
                child_data = [d for _, d in child_data_with_values]

                if self.rollup_method == "sum":
                    raw = sum(d["raw"] for d in child_data)
                    count = sum(d["count"] for d in child_data)
                    weight = sum(d["weight"] for d in child_data)

                elif self.rollup_method == "weighted_avg":
                    # Get weights based on configured source (using cached data)
                    if self.rollup_weight_source == "count":
                        weights = [d["count"] for d in child_data]
                    elif self.rollup_weight_source == "area_sqkm":
                        weights = [areas_data[cid]["area_sqkm"] for cid in valid_child_ids]
                    elif self.rollup_weight_source == "population":
                        weights = [areas_data[cid]["population"] for cid in valid_child_ids]
                    else:
                        weights = [d["count"] for d in child_data]

                    total_weight = sum(weights)
                    if total_weight > 0:
                        raw = sum(d["raw"] * w for d, w in zip(child_data, weights, strict=False)) / total_weight
                    else:
                        raw = 0
                    count = sum(d["count"] for d in child_data)
                    weight = total_weight

                elif self.rollup_method == "avg":
                    raw = sum(d["raw"] for d in child_data) / len(child_data) if child_data else 0
                    count = sum(d["count"] for d in child_data)
                    weight = len(child_data)

                elif self.rollup_method == "min":
                    raw = min(d["raw"] for d in child_data) if child_data else 0
                    count = sum(d["count"] for d in child_data)
                    weight = len(child_data)

                elif self.rollup_method == "max":
                    raw = max(d["raw"] for d in child_data) if child_data else 0
                    count = sum(d["count"] for d in child_data)
                    weight = len(child_data)

                else:  # Default to sum
                    raw = sum(d["raw"] for d in child_data)
                    count = sum(d["count"] for d in child_data)
                    weight = sum(d["weight"] for d in child_data)

                # Count source areas (sum of all children's source counts, including no-data)
                source_count = sum(d.get("source_area_count", 1) for d in all_child_data)

                all_results[parent.id] = {
                    "raw": raw,
                    "count": count,
                    "weight": weight,
                    "is_rollup": True,
                    "source_area_count": source_count,
                }

                # Add parent to tracking set for next iteration
                all_area_ids_in_results.add(parent.id)

            # Move to next parent level
            current_level_area_ids = parent_areas.ids
            current_level -= 1

        return all_results

    def _compute_auto_thresholds(self, values):
        """Calculate automatic thresholds based on configuration.

        Args:
            values: List of normalized values to classify

        Returns:
            list: List of threshold dicts with min_value, max_value, color, label
        """
        self.ensure_one()
        if not values:
            return []

        # Filter out None/NaN values
        clean_values = [v for v in values if v is not None and v == v]  # v == v filters NaN
        if not clean_values:
            return []

        sorted_values = sorted(clean_values)
        num_buckets = max(2, min(self.bucket_count, len(sorted_values)))

        # Get color scheme
        colors = self._get_color_palette(num_buckets)
        labels = self._get_bucket_labels(num_buckets)

        thresholds = []

        if self.threshold_mode == "auto_quartile":
            # Quartile-based thresholds
            breakpoints = self._calculate_quantiles(sorted_values, num_buckets)

        elif self.threshold_mode == "auto_equal":
            # Equal interval thresholds
            min_val = min(sorted_values)
            max_val = max(sorted_values)
            interval = (max_val - min_val) / num_buckets
            breakpoints = [min_val + i * interval for i in range(num_buckets + 1)]

        elif self.threshold_mode == "auto_jenks":
            # Natural breaks (Jenks) - simplified implementation
            breakpoints = self._calculate_jenks_breaks(sorted_values, num_buckets)

        elif self.threshold_mode == "auto_stddev":
            # Standard deviation thresholds
            mean = statistics.mean(sorted_values)
            std = statistics.stdev(sorted_values) if len(sorted_values) > 1 else 0

            # Create buckets based on standard deviations from mean
            breakpoints = [
                mean - 2 * std,
                mean - std,
                mean,
                mean + std,
                mean + 2 * std,
            ]
            # Extend to cover all values
            breakpoints = [min(sorted_values)] + breakpoints + [max(sorted_values)]
            breakpoints = sorted(set(breakpoints))[: num_buckets + 1]

        else:
            # Default to quartiles
            breakpoints = self._calculate_quantiles(sorted_values, num_buckets)

        # Ensure we have correct number of breakpoints
        while len(breakpoints) < num_buckets + 1:
            breakpoints.append(breakpoints[-1] if breakpoints else 0)

        # Create threshold records
        for i in range(num_buckets):
            thresholds.append(
                {
                    "sequence": (i + 1) * 10,
                    "min_value": breakpoints[i],
                    "max_value": breakpoints[i + 1] if i < len(breakpoints) - 1 else None,
                    "color": colors[i] if i < len(colors) else colors[-1],
                    "label": labels[i] if i < len(labels) else f"Bucket {i + 1}",
                }
            )

        return thresholds

    def _calculate_quantiles(self, sorted_values, num_buckets):
        """Calculate quantile breakpoints.

        Args:
            sorted_values: Sorted list of values
            num_buckets: Number of buckets

        Returns:
            list: Breakpoint values (len = num_buckets + 1)
        """
        n = len(sorted_values)
        if n == 0:
            return [0, 1]

        breakpoints = []
        for i in range(num_buckets + 1):
            idx = int(i * (n - 1) / num_buckets)
            breakpoints.append(sorted_values[idx])

        return breakpoints

    def _calculate_jenks_breaks(self, sorted_values, num_buckets):
        """Calculate Jenks natural breaks (simplified implementation).

        Uses a simplified approach for performance. For exact Jenks,
        use external library like jenkspy.

        Args:
            sorted_values: Sorted list of values
            num_buckets: Number of buckets

        Returns:
            list: Breakpoint values
        """
        # Simplified: use quantiles with adjustment for natural gaps
        n = len(sorted_values)
        if n <= num_buckets:
            return sorted_values + [sorted_values[-1]]

        # Calculate gaps between consecutive values
        gaps = []
        for i in range(1, n):
            gaps.append((sorted_values[i] - sorted_values[i - 1], i))

        # Sort by gap size descending
        gaps.sort(reverse=True)

        # Take top (num_buckets - 1) gaps as break points
        break_indices = sorted([g[1] for g in gaps[: num_buckets - 1]])

        # Build breakpoints
        breakpoints = [sorted_values[0]]
        for idx in break_indices:
            breakpoints.append(sorted_values[idx])
        breakpoints.append(sorted_values[-1])

        return breakpoints

    def _get_color_palette(self, num_colors):
        """Get color palette based on configured color scheme.

        Uses the spp.gis.color.scheme model for centralized color management.

        Args:
            num_colors: Number of colors needed

        Returns:
            list: List of hex color strings
        """
        self.ensure_one()

        if self.color_scheme_id:
            return self.color_scheme_id.get_discrete_colors(num_colors)

        # Fallback to viridis if no scheme configured
        fallback = self.env["spp.gis.color.scheme"].get_default_scheme()
        if fallback:
            return fallback.get_discrete_colors(num_colors)

        # Ultimate fallback - simple grayscale
        return [f"#{hex(int(255 * i / max(num_colors - 1, 1)))[2:].zfill(2) * 3}" for i in range(num_colors)]

    def _get_bucket_labels(self, num_buckets):
        """Generate bucket labels.

        Args:
            num_buckets: Number of buckets

        Returns:
            list: List of label strings
        """
        if num_buckets == 2:
            return ["Low", "High"]
        elif num_buckets == 3:
            return ["Low", "Medium", "High"]
        elif num_buckets == 4:
            return ["Very Low", "Low", "High", "Very High"]
        elif num_buckets == 5:
            return ["Very Low", "Low", "Medium", "High", "Very High"]
        else:
            return [f"Level {i + 1}" for i in range(num_buckets)]

    def _assign_thresholds(self, results, thresholds):
        """Assign bucket index and color to each result based on thresholds.

        Args:
            results: dict {area_id: {... 'normalized': float ...}}
            thresholds: list of threshold dicts or spp.gis.report.threshold records

        Returns:
            dict: Updated results with bucket_index, bucket_color, bucket_label
        """
        self.ensure_one()

        if not thresholds:
            # No thresholds - assign all to default bucket
            for _area_id, data in results.items():
                value = data.get("normalized", data.get("raw"))
                if value is None:
                    # No data - special bucket
                    data["bucket_index"] = None
                    data["bucket_color"] = "#CCCCCC"  # Light gray for no data
                    data["bucket_label"] = "No Data"
                else:
                    data["bucket_index"] = 0
                    data["bucket_color"] = "#808080"  # Gray
                    data["bucket_label"] = "No Classification"
            return results

        # Convert threshold records to list of dicts if needed
        if hasattr(thresholds, "sorted"):  # Odoo recordset
            threshold_list = []
            for t in thresholds.sorted("sequence"):
                threshold_list.append(
                    {
                        "min_value": t.min_value,
                        "max_value": t.max_value,
                        "color": t.color,
                        "label": t.label,
                    }
                )
            thresholds = threshold_list

        # Sort by min_value
        thresholds = sorted(thresholds, key=lambda t: t.get("min_value") or float("-inf"))

        for _area_id, data in results.items():
            value = data.get("normalized", data.get("raw"))

            # Handle None values (no data) - assign to special "No Data" bucket
            if value is None:
                data["bucket_index"] = None
                data["bucket_color"] = "#CCCCCC"  # Light gray for no data
                data["bucket_label"] = "No Data"
                continue

            # Find matching bucket
            assigned = False
            for i, threshold in enumerate(thresholds):
                min_val = threshold.get("min_value")
                max_val = threshold.get("max_value")

                # Check if value falls in this bucket
                in_min = min_val is None or value >= min_val
                in_max = max_val is None or value < max_val

                if in_min and in_max:
                    data["bucket_index"] = i
                    data["bucket_color"] = threshold.get("color", "#808080")
                    data["bucket_label"] = threshold.get("label", f"Bucket {i + 1}")
                    assigned = True
                    break

            if not assigned:
                # Assign to last bucket if no match found
                last_idx = len(thresholds) - 1
                data["bucket_index"] = last_idx
                data["bucket_color"] = thresholds[last_idx].get("color", "#808080")
                data["bucket_label"] = thresholds[last_idx].get("label", "Unknown")

        return results

    def _apply_statistical_normalization(self, results):
        """Apply statistical normalization methods that require all values.

        Handles: index, percentile, zscore

        Args:
            results: dict {area_id: {... 'raw': float ...}}

        Returns:
            dict: Updated results with normalized values
        """
        self.ensure_one()

        if self.normalization_method not in ("index", "percentile", "zscore"):
            return results

        raw_values = [d["raw"] for d in results.values() if d["raw"] is not None]
        if not raw_values:
            return results

        if self.normalization_method == "index":
            # Normalize to 0-100 scale
            min_val = min(raw_values)
            max_val = max(raw_values)
            range_val = max_val - min_val

            for _area_id, data in results.items():
                # Preserve None for no-data areas
                if data["raw"] is None:
                    data["normalized"] = None
                elif range_val > 0:
                    data["normalized"] = ((data["raw"] - min_val) / range_val) * 100
                else:
                    data["normalized"] = 50  # Middle if all same

        elif self.normalization_method == "percentile":
            # Assign percentile rank
            sorted_values = sorted(raw_values)
            n = len(sorted_values)

            for _area_id, data in results.items():
                # Preserve None for no-data areas
                if data["raw"] is None:
                    data["normalized"] = None
                else:
                    # Find percentile rank
                    count_below = sum(1 for v in sorted_values if v < data["raw"])
                    data["normalized"] = (count_below / n) * 100 if n > 0 else 50

        elif self.normalization_method == "zscore":
            # Calculate z-scores
            mean = statistics.mean(raw_values)
            std = statistics.stdev(raw_values) if len(raw_values) > 1 else 1

            for _area_id, data in results.items():
                # Preserve None for no-data areas
                if data["raw"] is None:
                    data["normalized"] = None
                elif std > 0:
                    data["normalized"] = (data["raw"] - mean) / std
                else:
                    data["normalized"] = 0

        return results

    def _refresh_data(self):
        """Main refresh workflow - compute and store all report data.

        This is the core computation that:
        1. Aggregates data at base level
        2. Normalizes values
        3. Rolls up to parent levels
        4. Assigns threshold buckets
        5. Stores results in spp.gis.report.data

        Optimized for large datasets with batch queries.
        """
        self.ensure_one()
        _logger.info("Starting full refresh for report ID %s", self.id)

        # Step 0: Build shared area context
        area_context = self._prepare_area_context()

        # Step 1: Compute base aggregation
        base_results = self._compute_base_aggregation(area_context)

        if not base_results:
            _logger.info("No data found for report ID %s", self.id)
            # Clear existing data
            self.data_ids.unlink()
            self.last_refresh = fields.Datetime.now()
            self.is_syncing = False
            return

        # OPTIMIZATION: Batch load area data for normalization
        # Load all areas we'll need (base areas + their parents for rollup)
        area_ids = list(base_results.keys())
        areas = self.env["spp.area"].browse(area_ids)
        # Prefetch normalization fields in single query
        areas.read(["area_sqkm", "population", "household_count"])
        area_cache = {a.id: a for a in areas}

        # Step 2: Apply normalization to base results (using cached areas)
        for area_id, data in base_results.items():
            area = area_cache.get(area_id) or self.env["spp.area"].browse(area_id)
            normalized = self._normalize_value(data["raw"], area, data.get("weight"))
            data["normalized"] = normalized if normalized is not None else data["raw"]

        # Step 3: Roll up to parent levels
        all_results = self._compute_hierarchy_rollup(base_results)

        # OPTIMIZATION: Batch load rolled-up areas for normalization
        rollup_area_ids = [aid for aid, data in all_results.items() if data.get("is_rollup") and aid not in area_cache]
        if rollup_area_ids:
            rollup_areas = self.env["spp.area"].browse(rollup_area_ids)
            rollup_areas.read(["area_sqkm", "population", "household_count"])
            for area in rollup_areas:
                area_cache[area.id] = area

        # For rolled-up areas, also normalize (using cached areas)
        for area_id, data in all_results.items():
            if data.get("is_rollup") and data.get("normalized") is None:
                area = area_cache.get(area_id) or self.env["spp.area"].browse(area_id)
                normalized = self._normalize_value(data["raw"], area, data.get("weight"))
                data["normalized"] = normalized if normalized is not None else data["raw"]

        # Step 4: Apply statistical normalization (if applicable)
        all_results = self._apply_statistical_normalization(all_results)

        # Step 5: Compute or get thresholds
        if self.threshold_mode.startswith("auto_"):
            # Compute automatic thresholds
            normalized_values = [d.get("normalized", d["raw"]) for d in all_results.values()]
            thresholds = self._compute_auto_thresholds(normalized_values)
        else:
            # Use manual thresholds
            thresholds = self.threshold_ids

        # Step 6: Assign threshold buckets
        all_results = self._assign_thresholds(all_results, thresholds)

        # Step 7: Save auto-computed thresholds to the report
        if self.threshold_mode.startswith("auto_") and thresholds:
            # Clear existing auto thresholds
            self.threshold_ids.filtered(lambda t: not t.description).unlink()
            # Create new ones
            for t in thresholds:
                self.env["spp.gis.report.threshold"].create(
                    {
                        "report_id": self.id,
                        "sequence": t["sequence"],
                        "min_value": t["min_value"],
                        "max_value": t["max_value"],
                        "color": t["color"],
                        "label": t["label"],
                    }
                )

        # Step 7b: Compute disaggregation (if dimensions configured)
        disaggregation_by_area = self._compute_disaggregation(area_context)

        # Step 8: Store results in spp.gis.report.data
        now = fields.Datetime.now()

        # Get existing data records for update
        existing_data = {d.area_id.id: d for d in self.data_ids}

        for area_id, data in all_results.items():
            # Preserve None for raw/normalized values (no data vs zero)
            raw_val = data.get("raw")
            normalized_val = data.get("normalized")
            if normalized_val is None:
                normalized_val = raw_val  # Use raw if normalized not set

            vals = {
                "report_id": self.id,
                "area_id": area_id,
                "raw_value": raw_val,  # Can be None for no-data areas
                "normalized_value": normalized_val,  # Can be None for no-data areas
                "weight": data.get("weight", 0),
                "record_count": data.get("count", 0),
                "is_rollup": data.get("is_rollup", False),
                "source_area_count": data.get("source_area_count", 1),
                "bucket_index": data.get("bucket_index"),  # None for no-data areas
                "bucket_color": data.get("bucket_color", "#CCCCCC"),
                "bucket_label": data.get("bucket_label", "No Data"),
                "computed_at": now,
                "disaggregation": disaggregation_by_area.get(area_id) or False,
            }

            if area_id in existing_data:
                # Update existing record
                existing_data[area_id].write(vals)
                del existing_data[area_id]
            else:
                # Create new record
                self.env["spp.gis.report.data"].create(vals)

        # Remove obsolete data records
        for old_data in existing_data.values():
            old_data.unlink()

        # Update last refresh timestamp and clear syncing flag
        self.last_refresh = now
        self.is_syncing = False

        _logger.info(
            "Completed refresh for report %s: %d areas",
            self.name,
            len(all_results),
        )

    def action_refresh(self):
        """Refresh report data.

        Uses job_worker for background processing if available,
        otherwise runs synchronously.

        Returns:
            dict: A notification action to display to the user.
        """
        self.ensure_one()
        _logger.info("Scheduling refresh for report ID %s", self.id)

        # Use job_worker if available, otherwise run synchronously
        if hasattr(self, "with_delay"):
            self.is_syncing = True
            self.with_delay(priority=10, description=f"Re-sync GIS Report: {self.name}")._refresh_data()
            message = _("Report data refresh has been scheduled.")
        else:
            self._refresh_data()
            message = _("Report data has been refreshed.")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Report Refresh"),
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

    def action_reload_page(self):
        """Re-read the form to check if sync has completed."""
        return {"type": "ir.actions.act_window_close"}

    def action_refresh_now(self):
        """Immediately refresh report data (alias for action_refresh)."""
        return self.action_refresh()

    @api.model
    def _cron_refresh_scheduled_reports(self):
        """Cron job to refresh all scheduled reports that are due.

        Called by ir.cron to refresh reports with refresh_mode='scheduled'
        that have passed their next_refresh time.
        """
        now = fields.Datetime.now()
        reports_to_refresh = self.search(
            [
                ("refresh_mode", "=", "scheduled"),
                ("active", "=", True),
                "|",
                ("next_refresh", "=", False),
                ("next_refresh", "<=", now),
            ]
        )

        _logger.info("GIS Report cron: Found %d reports to refresh", len(reports_to_refresh))

        for report in reports_to_refresh:
            try:
                report._refresh_data()
                _logger.info("GIS Report cron: Refreshed report ID %s", report.id)
            except Exception:
                _logger.exception("GIS Report cron: Failed to refresh '%s'", report.name)

    def action_view_map(self):
        """Open the map view for this report.

        Returns an action that displays the GIS map view with this report's data.
        Opens the spp.area GIS view where the report's layer is displayed.
        """
        self.ensure_one()

        # Find the GIS view for spp.area
        gis_view = self.env["ir.ui.view"].search(
            [("model", "=", "spp.area"), ("type", "=", "gis")],
            limit=1,
        )

        if not gis_view:
            # Fall back to data view if no GIS view available
            return self.action_view_data()

        return {
            "type": "ir.actions.act_window",
            "name": _("Map: %s", self.name),
            "res_model": "spp.area",
            "view_mode": "gis",
            "view_id": gis_view.id,
            "limit": 100000,  # High limit to load all areas for complete map display
            "context": {
                "gis_report_id": self.id,
                "gis_report_layer_id": self.layer_id.id if self.layer_id else False,
            },
            "target": "current",
        }

    def action_view_data(self):
        """Open the data view for this report."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Report Data: %s", self.name),
            "res_model": "spp.gis.report.data",
            "view_mode": "list,form",
            "domain": [("report_id", "=", self.id)],
            "context": {
                "default_report_id": self.id,
            },
        }

    def _to_geojson(
        self,
        admin_level=None,
        area_ids=None,
        parent_area_id=None,
        include_geometry=True,
        include_disaggregation=False,
        crs="EPSG:4326",
    ):
        """Generate GeoJSON output for this report.

        Args:
            admin_level: Filter to specific admin level
            area_ids: List of area IDs to include
            parent_area_id: Only include children of this area
            include_geometry: Include polygon geometry
            include_disaggregation: Include disaggregation data
            crs: Coordinate reference system

        Returns:
            dict: GeoJSON FeatureCollection

        TODO: Implement using PostGIS ST_AsGeoJSON for performance
        """
        self.ensure_one()
        _logger.info("Generating GeoJSON for report ID %s", self.id)

        # Build domain for filtering data
        domain = [("report_id", "=", self.id)]

        if admin_level is not None:
            domain.append(("area_level", "=", admin_level))

        if area_ids:
            domain.append(("area_id", "in", area_ids))

        if parent_area_id:
            parent_area = self.env["spp.area"].browse(parent_area_id)
            if parent_area.exists():
                child_areas = self.env["spp.area"].search([("parent_id", "=", parent_area_id)])
                domain.append(("area_id", "in", child_areas.ids))

        # Get filtered data records
        data_records = self.env["spp.gis.report.data"].search(domain)

        # Build features
        features = []
        for data in data_records:
            # Build properties
            # has_data is True if raw_value is not None (distinguishes no-data from zero)
            has_data = data.raw_value is not None
            properties = {
                "area_id": data.area_id.id,
                "area_code": data.area_code,
                "area_name": data.area_name,
                "area_level": data.area_level,
                "area_level_name": f"Level {data.area_level}",
                "parent_area_id": data.parent_area_id.id if data.parent_area_id else None,
                "parent_area_code": (data.parent_area_id.code if data.parent_area_id else None),
                "parent_area_name": (data.parent_area_id.name if data.parent_area_id else None),
                "has_data": has_data,  # False if no source data for this area
                "raw_value": data.raw_value,  # null if no data
                "normalized_value": data.normalized_value,  # null if no data
                "display_value": data.display_value if has_data else "No Data",
                "bucket": {
                    "index": data.bucket_index,  # null if no data
                    "color": data.bucket_color,
                    "label": data.bucket_label,
                },
                "weight": data.weight,
                "record_count": data.record_count,
                "is_rollup": data.is_rollup,
                "computed_at": data.computed_at.isoformat() if data.computed_at else None,
            }

            # Add reference data if available
            if data.area_id:
                properties["reference_data"] = {
                    "area_sqkm": data.area_id.area_sqkm,
                    "population": data.area_id.population,
                    "household_count": data.area_id.household_count,
                }

            # Add disaggregation as flat disagg_* properties for QGIS compatibility
            if include_disaggregation and data.disaggregation:
                for dim_name, value_counts in data.disaggregation.items():
                    for raw_value, count in value_counts.items():
                        properties[f"disagg_{dim_name}_{raw_value}"] = count

            # Build feature
            feature = {
                "type": "Feature",
                "id": data.area_code,
                "properties": properties,
            }

            # Add geometry if requested
            if include_geometry and data.area_id.geo_polygon:
                try:
                    geo = data.area_id.geo_polygon
                    # GeoPolygonField may return a Shapely geometry object
                    # or a WKT/WKB string depending on the spp_gis version.
                    if hasattr(geo, "__geo_interface__"):
                        feature["geometry"] = geo.__geo_interface__
                    else:
                        from shapely import wkt

                        shape = wkt.loads(geo)
                        feature["geometry"] = shape.__geo_interface__
                except ImportError:
                    _logger.warning(
                        "shapely not available, geometry export limited. Install shapely for full geometry support."
                    )
                    feature["geometry"] = None
                except Exception as e:
                    _logger.warning(
                        "Failed to parse geometry for area %s: %s",
                        data.area_code,
                        str(e),
                    )
                    feature["geometry"] = None
            else:
                feature["geometry"] = None

            features.append(feature)

        # Build metadata
        metadata = {
            "report": {
                "id": self.id,
                "code": self.code,
                "name": self.name,
                "description": self.description,
            },
            "generated_at": fields.Datetime.now().isoformat(),
            "admin_level": admin_level,
            "total_features": len(features),
            "normalization": {
                "method": self.normalization_method,
                "label": dict(self._fields["normalization_method"].selection).get(self.normalization_method),
                "reference": (self.reference_indicator_id.code if self.reference_indicator_id else None),
            },
            "data_freshness": {
                "last_refresh": (self.last_refresh.isoformat() if self.last_refresh else None),
                "next_refresh": (self.next_refresh.isoformat() if self.next_refresh else None),
                "is_stale": self.is_stale,
            },
        }

        # Add thresholds to metadata
        thresholds = []
        for threshold in self.threshold_ids.sorted("sequence"):
            thresholds.append(
                {
                    "min": threshold.min_value,
                    "max": threshold.max_value,
                    "color": threshold.color,
                    "label": threshold.label,
                }
            )
        metadata["thresholds"] = thresholds

        # Add disaggregation dimension metadata (for interpreting disagg_* properties)
        if include_disaggregation and self.dimension_ids:
            disagg_metadata = []
            for dim in self.dimension_ids:
                dim_info = {
                    "name": dim.name,
                    "label": dim.label,
                    "property_prefix": f"disagg_{dim.name}_",
                }
                if dim.value_labels_json:
                    labels = dim.value_labels_json
                    if isinstance(labels, str):
                        import json

                        try:
                            labels = json.loads(labels)
                        except (json.JSONDecodeError, TypeError):
                            labels = {}
                    dim_info["value_labels"] = labels
                disagg_metadata.append(dim_info)
            metadata["disaggregation"] = disagg_metadata

        # Add summary statistics if we have data
        if data_records:
            summary = self._get_summary(
                admin_level=admin_level,
                parent_area_id=parent_area_id,
            )
            metadata["summary"] = summary.get("summary", {})
            metadata["summary"]["by_bucket"] = summary.get("distribution", [])

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": metadata,
        }

    def _get_summary(self, admin_level=None, parent_area_id=None):
        """Return aggregate statistics for this report.

        Args:
            admin_level: Level to summarize
            parent_area_id: Scope to children of area

        Returns:
            dict: Summary statistics
        """
        self.ensure_one()
        _logger.info("Generating summary for report ID %s", self.id)

        # Build domain for filtering data
        domain = [("report_id", "=", self.id)]

        if admin_level is not None:
            domain.append(("area_level", "=", admin_level))

        if parent_area_id:
            parent_area = self.env["spp.area"].browse(parent_area_id)
            if parent_area.exists():
                child_areas = self.env["spp.area"].search([("parent_id", "=", parent_area_id)])
                domain.append(("area_id", "in", child_areas.ids))

        # Get filtered data records
        data_records = self.env["spp.gis.report.data"].search(domain)

        if not data_records:
            return {
                "report_id": self.id,
                "admin_level": admin_level,
                "area_count": 0,
                "summary": {},
                "distribution": [],
            }

        # Calculate statistics - filter out None values (no-data areas)
        raw_values = [v for v in data_records.mapped("raw_value") if v is not None]
        normalized_values = [v for v in data_records.mapped("normalized_value") if v is not None]

        # Count areas with and without data
        areas_with_data = len(raw_values)
        areas_without_data = len(data_records) - areas_with_data

        summary = {
            "areas_with_data": areas_with_data,
            "areas_without_data": areas_without_data,
            "total_raw_value": sum(raw_values) if raw_values else 0,
            "min_raw": min(raw_values) if raw_values else None,
            "max_raw": max(raw_values) if raw_values else None,
        }

        if normalized_values:
            summary.update(
                {
                    "min_normalized": min(normalized_values),
                    "max_normalized": max(normalized_values),
                    "mean_normalized": statistics.mean(normalized_values),
                    "median_normalized": statistics.median(normalized_values),
                    "stddev_normalized": (statistics.stdev(normalized_values) if len(normalized_values) > 1 else 0),
                }
            )

        # Calculate distribution by bucket
        distribution = []
        bucket_data = {}

        for data in data_records:
            label = data.bucket_label or "Unknown"
            if label not in bucket_data:
                bucket_data[label] = {
                    "bucket": label,
                    "count": 0,
                    "total_raw": 0,
                }
            bucket_data[label]["count"] += 1
            # Only add to total_raw if not None
            if data.raw_value is not None:
                bucket_data[label]["total_raw"] += data.raw_value

        total_count = len(data_records)
        for _label, bucket_info in bucket_data.items():
            bucket_info["percentage"] = (bucket_info["count"] / total_count * 100) if total_count else 0
            distribution.append(bucket_info)

        return {
            "report_id": self.id,
            "admin_level": admin_level,
            "area_count": len(data_records),
            "summary": summary,
            "distribution": distribution,
        }

    # ===== Layer Auto-Sync Methods =====

    @api.model_create_multi
    def create(self, vals_list):
        """Create reports and auto-create layers if enabled."""
        reports = super().create(vals_list)
        for report in reports:
            if report.auto_create_layer:
                report._sync_data_layer()
        return reports

    def write(self, vals):
        """Update reports and sync layers if needed."""
        res = super().write(vals)

        # Sync layer if relevant fields changed
        layer_sync_fields = {
            "name",
            "geometry_type",
            "color_scheme_id",
            "auto_create_layer",
            "layer_active_on_startup",
            "active",
        }
        if layer_sync_fields & set(vals.keys()):
            for report in self:
                if report.auto_create_layer:
                    report._sync_data_layer()
                elif "auto_create_layer" in vals and not vals["auto_create_layer"]:
                    # Auto-create was disabled, unlink the layer
                    if report.layer_id:
                        report.layer_id.unlink()

        return res

    def unlink(self):
        """Delete reports and their auto-created layers."""
        # Layers will be deleted via ondelete="cascade" on report_id
        return super().unlink()

    def _sync_data_layer(self):
        """Create or update the auto-created data layer for this report.

        Creates a spp.gis.data.layer record that references this report,
        allowing the report data to be visualized on GIS maps.
        """
        self.ensure_one()

        if not self.auto_create_layer:
            return

        # Get or find the area model's geo field for the layer
        area_model = self.env["ir.model"].search([("model", "=", "spp.area")], limit=1)
        if not area_model:
            _logger.warning("spp.area model not found, cannot create layer")
            return

        # Find the geo_polygon field on spp.area
        geo_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", area_model.id),
                ("name", "=", "geo_polygon"),
            ],
            limit=1,
        )

        if not geo_field:
            _logger.warning("geo_polygon field not found on spp.area")
            return

        # Find or create a GIS view for spp.area
        gis_view = self.env["ir.ui.view"].search(
            [
                ("model", "=", "spp.area"),
                ("type", "=", "gis"),
            ],
            limit=1,
        )

        if not gis_view:
            _logger.warning("No GIS view found for spp.area")
            return

        layer_vals = {
            "name": self.name,
            "source_type": "report",
            "report_id": self.id,
            "geometry_type": self.geometry_type,
            "color_scheme_id": self.color_scheme_id.id,
            "geo_field_id": geo_field.id,
            "view_id": gis_view.id,
            "active_on_startup": self.layer_active_on_startup,
            "sequence": 10 + self.sequence,
            "layer_opacity": 0.7,
        }

        if self.layer_id:
            # Update existing layer
            self.layer_id.write(layer_vals)
            _logger.info("Updated data layer for report ID %s", self.id)
        else:
            # Create new layer
            layer = self.env["spp.gis.data.layer"].create(layer_vals)
            self.layer_id = layer
            _logger.info("Created data layer for report ID %s", self.id)

    def action_sync_layer(self):
        """Manual action to sync the data layer."""
        self.ensure_one()
        self._sync_data_layer()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Layer Synced"),
                "message": _("The map layer has been synchronized."),
                "type": "success",
                "sticky": False,
            },
        }
