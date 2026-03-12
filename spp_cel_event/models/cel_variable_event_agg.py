# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""CEL Variable Event Aggregation Extension.

This module extends spp.cel.variable to support event-based aggregations,
allowing users to create variables that aggregate over event data.

Example use cases:
- Count of visits in last 90 days
- Sum of payments this year
- Average assessment score
- Check if any health screening exists
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CELVariableEventAggregation(models.Model):
    """Extension to CEL Variable for event aggregation support.

    Adds the ability to aggregate over event data records, with support for:
    - Event type selection
    - Temporal filtering (this year, last N days, etc.)
    - Field aggregation (sum, avg, min, max)
    - Custom CEL filters
    """

    _inherit = "spp.cel.variable"

    # Extend aggregate_target with events option
    aggregate_target = fields.Selection(
        selection_add=[
            ("events", "Events"),
        ],
        ondelete={"events": "set default"},
    )

    # ─── Event Aggregation Configuration ─────────────────────────────────
    event_agg_type_id = fields.Many2one(
        "spp.event.type",
        string="Event Type",
        help="Event type to aggregate over",
        ondelete="set null",
    )

    event_agg_temporal = fields.Selection(
        [
            ("all", "All Time"),
            ("this_year", "This Year"),
            ("this_quarter", "This Quarter"),
            ("this_month", "This Month"),
            ("within_days", "Within N Days"),
            ("within_months", "Within N Months"),
        ],
        string="Time Range",
        default="all",
        help="Time range for event aggregation",
    )

    event_agg_temporal_value = fields.Integer(
        string="N (Days/Months)",
        help="Number of days or months for 'within' temporal filters",
    )

    event_agg_field = fields.Char(
        string="Event Field",
        help="JSON field name in event data (e.g., 'amount', 'score'). Required for sum/avg/min/max aggregations.",
    )

    event_agg_states = fields.Selection(
        [
            ("active", "Active Only"),
            ("all", "All States"),
        ],
        string="Event States",
        default="active",
        help="Which event states to include in aggregation",
    )

    @api.depends(
        "event_agg_type_id",
        "event_agg_temporal",
        "event_agg_temporal_value",
        "event_agg_field",
        "event_agg_states",
    )
    def _compute_cel_expression(self):
        """Override to handle event aggregations."""
        super()._compute_cel_expression()
        for var in self:
            if var.source_type == "aggregate" and var.aggregate_target == "events":
                var.cel_expression = var._build_event_aggregate_cel()

    def _build_event_aggregate_cel(self):
        """Build CEL expression for event aggregations.

        Generates expressions for event data aggregation:
        - events_count('event_type') - count events
        - events_exists('event_type') - check if any exist
        - events_sum('event_type', 'field') - sum of field values
        - events_avg('event_type', 'field') - average of field values
        - events_min('event_type', 'field') - minimum field value
        - events_max('event_type', 'field') - maximum field value

        With optional temporal filters:
        - period=this_year()
        - within_days=90
        - within_months=6
        """
        self.ensure_one()

        if not self.event_agg_type_id:
            _logger.warning(
                "Variable '%s' uses event aggregation without event type. Please specify event_agg_type_id.",
                self.name,
            )
            return self.cel_accessor

        event_type_code = self.event_agg_type_id.code
        agg_type = self.aggregate_type or "count"

        # Build function name
        func = f"events_{agg_type}"

        parts = [f"'{event_type_code}'"]

        # Field for sum/avg/min/max
        if agg_type in ("sum", "avg", "min", "max"):
            field = self.event_agg_field or self.aggregate_field
            if not field:
                _logger.warning(
                    "Variable '%s' uses %s aggregation without field. Please specify event_agg_field.",
                    self.name,
                    agg_type,
                )
                return self.cel_accessor
            parts.append(f"'{field}'")

        # Temporal filter
        temporal_part = None
        if self.event_agg_temporal == "this_year":
            temporal_part = "period=this_year()"
        elif self.event_agg_temporal == "this_quarter":
            temporal_part = "period=this_quarter()"
        elif self.event_agg_temporal == "this_month":
            temporal_part = "period=this_month()"
        elif self.event_agg_temporal == "within_days" and self.event_agg_temporal_value:
            temporal_part = f"within_days={self.event_agg_temporal_value}"
        elif self.event_agg_temporal == "within_months" and self.event_agg_temporal_value:
            temporal_part = f"within_months={self.event_agg_temporal_value}"

        if temporal_part:
            parts.append(temporal_part)

        # States filter
        if self.event_agg_states == "all":
            parts.append("states=['active', 'superseded', 'expired']")

        # Custom filter (where predicate)
        if self.aggregate_filter and self.aggregate_filter.strip() != "true":
            parts.append(f"where='{self.aggregate_filter}'")

        return f"{func}({', '.join(parts)})"

    @api.onchange("aggregate_target")
    def _onchange_aggregate_target_event(self):
        """Clear event-specific fields when switching away from events."""
        if self.aggregate_target != "events":
            self.event_agg_type_id = False
            self.event_agg_temporal = "all"
            self.event_agg_temporal_value = 0
            self.event_agg_field = False
            self.event_agg_states = "active"

    @api.constrains("aggregate_target", "event_agg_type_id")
    def _check_event_aggregation_config(self):
        """Ensure event aggregations have required configuration."""
        for rec in self:
            if rec.source_type == "aggregate" and rec.aggregate_target == "events":
                if not rec.event_agg_type_id:
                    # Log warning but don't block - may be set later
                    _logger.warning(
                        "Variable '%s' is configured for event aggregation but no event type is selected.",
                        rec.name,
                    )

    @api.constrains("event_agg_temporal", "event_agg_temporal_value")
    def _check_temporal_value(self):
        """Ensure temporal value is set when using within_days/months."""
        for rec in self:
            if rec.event_agg_temporal in ("within_days", "within_months"):
                if not rec.event_agg_temporal_value or rec.event_agg_temporal_value < 1:
                    raise ValidationError(
                        _(
                            "Variable '%(name)s' uses '%(temporal)s' time range but "
                            "no value is specified. Please set a positive value for N.",
                            name=rec.name,
                            temporal=rec.event_agg_temporal,
                        )
                    )
