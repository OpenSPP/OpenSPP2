# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Dashboard Data - Materialized snapshot of published statistics."""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class DashboardData(models.Model):
    """Pre-computed dashboard statistic values.

    Stores one row per (statistic, area, program) combination.
    Refreshed via queue_job (manual trigger or daily cron).
    """

    _name = "spp.dashboard.data"
    _description = "Dashboard Statistic Data"
    _order = "category_id, statistic_name"

    def init(self):
        """Create database indexes for dashboard query performance."""
        # Unique index using COALESCE to treat NULLs as 0 for uniqueness
        # (PostgreSQL UNIQUE considers NULLs as distinct by default)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_data_stat_area_prog
            ON spp_dashboard_data(
                statistic_id,
                COALESCE(area_id, 0),
                COALESCE(program_id, 0)
            )
        """)

        # Composite index for grouped list view (category + area filtering)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_data_category_area
            ON spp_dashboard_data(category_id, area_id)
        """)

        # Composite index for filtered queries (area + program)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_data_area_program
            ON spp_dashboard_data(area_id, program_id)
        """)

        # Index for area level filtering
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_data_area_level
            ON spp_dashboard_data(area_level)
        """)

        _logger.info("Dashboard data performance indexes created/verified")

    # ─── Relations ───────────────────────────────────────────────────────

    statistic_id = fields.Many2one(
        comodel_name="spp.statistic",
        string="Statistic",
        required=True,
        ondelete="cascade",
        index=True,
    )
    statistic_name = fields.Char(
        string="Statistic Name",
        related="statistic_id.name",
        store=True,
    )
    label = fields.Char(
        string="Label",
        help="Display label from statistic context config for dashboard",
    )

    category_id = fields.Many2one(
        comodel_name="spp.metric.category",
        string="Category",
        related="statistic_id.category_id",
        store=True,
        index=True,
    )
    category_code = fields.Char(
        string="Category Code",
        related="statistic_id.category_id.code",
        store=True,
    )

    area_id = fields.Many2one(
        comodel_name="spp.area",
        string="Area",
        ondelete="cascade",
        index=True,
        help="Area scope. Empty means system-wide.",
    )
    area_name = fields.Char(
        string="Area Name",
        related="area_id.name",
        store=True,
    )
    area_level = fields.Integer(
        string="Area Level",
        related="area_id.area_level",
        store=True,
    )

    program_id = fields.Many2one(
        comodel_name="spp.program",
        string="Program",
        ondelete="cascade",
        index=True,
        help="Program scope. Empty means all programs.",
    )
    program_name = fields.Char(
        string="Program Name",
        related="program_id.name",
        store=True,
    )

    # ─── Values ──────────────────────────────────────────────────────────

    value = fields.Float(
        string="Value",
        digits=(16, 4),
        help="Computed statistic value",
    )
    value_display = fields.Char(
        string="Display Value",
        help="Formatted display value (handles suppression: '<5', '*')",
    )
    is_suppressed = fields.Boolean(
        string="Suppressed",
        default=False,
        help="Whether k-anonymity suppression was applied",
    )
    underlying_count = fields.Integer(
        string="Underlying Count",
        help="Count before aggregation (for suppression check)",
    )

    # ─── Presentation (from statistic) ───────────────────────────────────

    format = fields.Selection(
        string="Format",
        related="statistic_id.format",
        store=True,
    )
    unit = fields.Char(
        string="Unit",
        related="statistic_id.unit",
        store=True,
    )

    # ─── Metadata ────────────────────────────────────────────────────────

    refreshed_at = fields.Datetime(
        string="Refreshed At",
        help="When this value was last computed",
    )

    # ─── Refresh Logic ───────────────────────────────────────────────────

    @api.model
    def action_refresh_all(self):
        """Enqueue refresh jobs for all dashboard statistics.

        Each statistic gets its own queue_job so failures are isolated.
        Returns a notification action to inform the user.
        """
        stats = self.env["spp.statistic"].get_published_for_context("dashboard")

        if not stats:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Dashboard Refresh"),
                    "message": _("No statistics are published for the dashboard."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Clean up stale data for un-published statistics
        self._cleanup_stale_data(stats)

        areas = self._get_dashboard_areas()

        for stat in stats:
            if hasattr(self, "with_delay"):
                self.with_delay(
                    priority=10,
                    description=f"Dashboard refresh: {stat.label}",
                )._refresh_statistic(stat.id, areas.ids)
            else:
                self._refresh_statistic(stat.id, areas.ids)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Dashboard Refresh"),
                "message": _("Statistics refresh has been queued. Data will update shortly."),
                "type": "success",
                "sticky": False,
            },
        }

    def _refresh_statistic(self, stat_id, area_ids):
        """Refresh one statistic across all scope combinations.

        Computes values for:
        - System-wide (no area, no program)
        - Per area (each configured area)
        - Per program (each active program with enrolled members)

        Called as a queue_job. Handles errors per-scope so one failure
        does not abort the entire statistic refresh.
        """
        stat = self.env["spp.statistic"].browse(stat_id)
        if not stat.exists():
            _logger.warning("Statistic ID %s no longer exists, skipping refresh", stat_id)
            return

        areas = self.env["spp.area"].browse(area_ids)
        programs = self._get_dashboard_programs()

        # Area dimension: system-wide + per-area
        for area in [False] + list(areas):
            self._refresh_scope(stat, area, False)

        # Program dimension: per-program (system-wide area)
        for program in programs:
            self._refresh_scope(stat, False, program)

    def _refresh_scope(self, stat, area, program):
        """Refresh a single (stat, area, program) combination.

        Args:
            stat: spp.statistic record
            area: spp.area record or False
            program: spp.program record or False
        """
        try:
            scope = self._build_scope(area, program)
            result = self.env["spp.aggregation.service"].compute_aggregation(
                scope=scope,
                statistics=[stat.name],
                context="dashboard",
            )
            self._upsert_data(stat, area, program, result)
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            area_label = area.code if area else "all"
            prog_label = program.name if program else "all"
            _logger.warning(
                "Dashboard refresh failed for stat=%s area=%s program=%s: %s",
                stat.name,
                area_label,
                prog_label,
                e,
            )

    @api.model
    def _get_dashboard_areas(self):
        """Get areas to include in dashboard refresh.

        Uses the system parameter 'spp_statistics_dashboard.area_levels' to filter
        by admin level (comma-separated integers). If not set, includes
        all areas.
        """
        param = self.env["ir.config_parameter"].sudo().get_param("spp_statistics_dashboard.area_levels", "")
        domain = []
        if param.strip():
            try:
                levels = [int(level.strip()) for level in param.split(",")]
                domain = [("area_level", "in", levels)]
            except ValueError:
                _logger.warning("Invalid spp_statistics_dashboard.area_levels parameter: %s", param)
        return self.env["spp.area"].search(domain)

    @api.model
    def _get_dashboard_programs(self):
        """Get active programs to include in dashboard refresh."""
        return self.env["spp.program"].search([("state", "=", "active")])

    @api.model
    def _build_scope(self, area, program):
        """Build aggregation scope dict for compute_aggregation.

        Args:
            area: spp.area record or False (system-wide)
            program: spp.program record or False (all programs)

        Returns:
            dict: scope definition for spp.aggregation.service
        """
        if program:
            # Program scope: use enrolled members as explicit partner IDs
            memberships = program.get_beneficiaries(state=["enrolled"])
            partner_ids = memberships.mapped("partner_id").ids
            return {
                "scope_type": "explicit",
                "explicit_partner_ids": partner_ids,
            }

        if area:
            return {
                "scope_type": "area",
                "area_id": area.id,
                "include_child_areas": True,
            }

        # System-wide scope: query all registrant IDs directly and use
        # explicit scope. We can't use CEL scope because the scope resolver's
        # env.get() check on the AbstractModel executor returns falsy.
        all_ids = self.env["res.partner"].sudo().search([("is_registrant", "=", True)]).ids
        return {
            "scope_type": "explicit",
            "explicit_partner_ids": all_ids,
        }

    def _upsert_data(self, stat, area, program, result):
        """Insert or update a dashboard data row from aggregation result.

        Args:
            stat: spp.statistic record
            area: spp.area record or False
            program: spp.program record or False
            result: dict from compute_aggregation()
        """
        stat_results = result.get("statistics", {})
        stat_data = stat_results.get(stat.name, {})

        raw_value = stat_data.get("value")
        is_suppressed = stat_data.get("suppressed", False)
        total_count = result.get("total_count", 0)

        # Get context config for label
        config = stat.get_context_config("dashboard")
        label = config.get("label", stat.label) if config else stat.label

        # The aggregation service already applies suppression.
        # If suppressed, the value is the suppression marker (e.g., "<5").
        # We store the raw numeric value for pivot/graph and a display string.
        if is_suppressed:
            # Value from service is the suppression display (string like "<5")
            value_display = str(raw_value) if raw_value is not None else ""
            numeric_value = 0.0
        elif raw_value is None:
            value_display = ""
            numeric_value = 0.0
        else:
            value_display = self._format_value(raw_value, stat)
            numeric_value = float(raw_value) if raw_value is not None else 0.0

        area_id = area.id if area else False
        program_id = program.id if program else False
        now = fields.Datetime.now()

        # Try to find existing record
        existing = self.search(
            [
                ("statistic_id", "=", stat.id),
                ("area_id", "=", area_id),
                ("program_id", "=", program_id),
            ],
            limit=1,
        )

        vals = {
            "value": numeric_value,
            "value_display": value_display,
            "is_suppressed": is_suppressed,
            "underlying_count": total_count,
            "label": label,
            "refreshed_at": now,
        }

        if existing:
            existing.write(vals)
        else:
            vals.update(
                {
                    "statistic_id": stat.id,
                    "area_id": area_id,
                    "program_id": program_id,
                }
            )
            self.create(vals)

    @api.model
    def _format_value(self, value, stat):
        """Format a numeric value for display based on statistic format.

        Args:
            value: numeric value
            stat: spp.statistic record

        Returns:
            str: formatted display string
        """
        if value is None:
            return ""

        fmt = stat.format
        decimal_places = stat.decimal_places or 0

        if fmt == "percent":
            return f"{value:.{decimal_places}f}%"
        elif fmt == "currency":
            return f"{value:,.{decimal_places}f}"
        elif fmt == "ratio":
            return f"{value:.{decimal_places}f}"
        elif fmt in ("count", "sum"):
            if decimal_places == 0:
                return f"{int(value):,}"
            return f"{value:,.{decimal_places}f}"
        else:
            # avg or unknown
            return f"{value:.{decimal_places}f}"

    @api.model
    def _cleanup_stale_data(self, published_stats):
        """Delete dashboard data rows for statistics no longer published.

        Args:
            published_stats: recordset of currently published spp.statistic
        """
        stale = self.search(
            [
                ("statistic_id", "not in", published_stats.ids),
            ]
        )
        if stale:
            _logger.info("Cleaning up %d stale dashboard data rows", len(stale))
            stale.unlink()
