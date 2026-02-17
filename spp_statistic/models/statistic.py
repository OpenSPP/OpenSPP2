# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Statistic - Publishable statistics based on CEL variables."""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Statistic(models.Model):
    """A publishable statistic based on a CEL variable.

    Statistics separate concerns:
    - CEL Variable: "What data and how to compute it"
    - Statistic: "Where to publish and how to present it"

    A single CEL variable can be published as multiple statistics
    with different presentations for different contexts.

    Inherits from spp.metric.base for common metric fields
    (name, label, description, category_id, sequence, etc.)
    """

    _name = "spp.statistic"
    _description = "Publishable Statistic"
    _inherit = ["spp.metric.base"]
    _order = "category_id, sequence, name"

    # ─── Source ─────────────────────────────────────────────────────────
    variable_id = fields.Many2one(
        comodel_name="spp.cel.variable",
        string="CEL Variable",
        required=True,
        ondelete="restrict",
        domain="[('source_type', 'in', ['aggregate', 'computed', 'field']), " "('state', '=', 'active')]",
        help="The CEL variable that provides the computation for this statistic",
    )
    variable_accessor = fields.Char(
        string="Variable Accessor",
        related="variable_id.cel_accessor",
        store=True,
        help="CEL accessor for the underlying variable",
    )
    variable_source_type = fields.Selection(
        string="Variable Source",
        related="variable_id.source_type",
        store=True,
    )

    # ─── Presentation ───────────────────────────────────────────────────
    # Note: format is overridden here to provide statistic-specific selection values
    # that represent aggregation types rather than display formats
    format = fields.Selection(
        selection=[
            ("count", "Count"),
            ("sum", "Sum"),
            ("avg", "Average"),
            ("percent", "Percentage"),
            ("ratio", "Ratio"),
            ("currency", "Currency"),
        ],
        string="Format",
        default="count",
        help="How to format/aggregate this statistic in displays",
    )
    # unit and decimal_places inherited from spp.metric.base

    # ─── Privacy / Small Cell Suppression ───────────────────────────────
    # Based on k-anonymity principles used in healthcare/census data
    minimum_count = fields.Integer(
        string="Minimum Count (k)",
        default=5,
        help="Suppress values when the underlying count is below this threshold. "
        "This prevents re-identification of individuals in small groups. "
        "Common values: 5 (basic), 10 (moderate), 20+ (sensitive data).",
    )
    suppression_display = fields.Selection(
        selection=[
            ("null", "Null/Empty"),
            ("asterisk", "* (Suppressed)"),
            ("less_than", "< [threshold]"),
        ],
        string="Suppression Display",
        default="less_than",
        help="How to display suppressed values in outputs.",
    )
    is_sensitive = fields.Boolean(
        string="Sensitive Data",
        default=False,
        help="Mark statistics involving sensitive attributes (disability, health, etc.) "
        "which may warrant higher suppression thresholds.",
    )

    # ─── Organization ───────────────────────────────────────────────────
    # category_id and sequence inherited from spp.metric.base
    # Note: category_id points to spp.metric.category (migrated from spp.statistic.category)

    # ─── Publication Flags ──────────────────────────────────────────────
    is_published_gis = fields.Boolean(
        string="Publish to GIS",
        default=False,
        help="Make this statistic available in GIS/QGIS spatial queries",
    )
    is_published_dashboard = fields.Boolean(
        string="Publish to Dashboard",
        default=False,
        help="Make this statistic available in dashboard widgets",
    )
    is_published_api = fields.Boolean(
        string="Publish to API",
        default=False,
        help="Make this statistic available in external API responses",
    )
    is_published_report = fields.Boolean(
        string="Publish to Reports",
        default=False,
        help="Make this statistic available in reports and exports",
    )

    # ─── Context-specific Configuration ─────────────────────────────────
    context_ids = fields.One2many(
        comodel_name="spp.statistic.context",
        inverse_name="statistic_id",
        string="Context Configurations",
        help="Context-specific presentation overrides",
    )

    # ─── State ──────────────────────────────────────────────────────────
    # active inherited from spp.metric.base

    # ─── Constraints ────────────────────────────────────────────────────
    _name_unique = models.Constraint("UNIQUE(name)", "Statistic name must be unique.")

    @api.constrains("name")
    def _check_name_format(self):
        """Ensure name follows snake_case convention."""
        for rec in self:
            if not re.match(r"^[a-z][a-z0-9_]*$", rec.name):
                raise ValidationError(
                    _("Statistic name '%(name)s' must be lowercase with underscores " "(e.g., 'children_under_5').")
                    % {"name": rec.name}
                )

    # ─── Query Methods ──────────────────────────────────────────────────

    @api.model
    def get_published_for_context(self, context):
        """Get all statistics published for a specific context.

        Args:
            context: One of 'gis', 'dashboard', 'api', 'report'

        Returns:
            recordset: Statistics published for that context
        """
        field_map = {
            "gis": "is_published_gis",
            "dashboard": "is_published_dashboard",
            "api": "is_published_api",
            "report": "is_published_report",
        }

        field = field_map.get(context)
        if not field:
            _logger.warning("Unknown statistic context: %s", context)
            return self.browse()

        return self.search(
            [
                (field, "=", True),
                ("active", "=", True),
            ]
        )

    @api.model
    def get_published_by_category(self, context):
        """Get published statistics grouped by category.

        Args:
            context: One of 'gis', 'dashboard', 'api', 'report'

        Returns:
            dict: {category_code: [statistics], ...}
        """
        stats = self.get_published_for_context(context)

        result = {}
        for stat in stats:
            cat_code = stat.category_id.code if stat.category_id else "uncategorized"
            if cat_code not in result:
                result[cat_code] = []
            result[cat_code].append(stat)

        return result

    def get_context_config(self, context):
        """Get context-specific configuration for this statistic.

        Falls back to default values if no context-specific config exists.

        Args:
            context: One of 'gis', 'dashboard', 'api', 'report'

        Returns:
            dict: Configuration with label, format, group, etc.
        """
        self.ensure_one()

        # Look for context-specific override
        ctx_config = self.context_ids.filtered(lambda c: c.context == context)

        if ctx_config:
            ctx_config = ctx_config[0]
            return {
                "label": ctx_config.label or self.label,
                "format": ctx_config.format or self.format,
                "group": ctx_config.group or (self.category_id.code if self.category_id else None),
                "icon": ctx_config.icon,
                "color": ctx_config.color,
                "minimum_count": ctx_config.minimum_count or self.minimum_count,
                "suppression_display": self.suppression_display,
            }

        # Fall back to defaults
        return {
            "label": self.label,
            "format": self.format,
            "group": self.category_id.code if self.category_id else None,
            "icon": None,
            "color": None,
            "minimum_count": self.minimum_count,
            "suppression_display": self.suppression_display,
        }

    def apply_suppression(self, value, count=None, context=None):
        """Apply small cell suppression to protect privacy.

        Based on k-anonymity principles: if the underlying count is below
        the minimum threshold, the value is suppressed to prevent
        re-identification of individuals in small groups.

        Args:
            value: The computed statistic value
            count: The underlying count (if different from value).
                   For count statistics, this equals value.
                   For averages/percentages, this is the denominator.
            context: Optional context for context-specific thresholds

        Returns:
            tuple: (display_value, is_suppressed)
                - display_value: The value to show (may be suppressed indicator)
                - is_suppressed: Boolean indicating if suppression was applied
        """
        self.ensure_one()

        # Get context-specific config
        config = self.get_context_config(context) if context else {}
        min_count = config.get("minimum_count", self.minimum_count) or 5
        display_mode = config.get("suppression_display", self.suppression_display)

        # Use value as count if not specified (for count-type statistics)
        if count is None:
            count = value if isinstance(value, int) else 0

        # Delegate to unified privacy service
        privacy_service = self.env.get("spp.metrics.privacy")
        if privacy_service:
            stat_config = {"minimum_count": min_count, "suppression_display": display_mode}
            return privacy_service.suppress_value(value, count, stat_config=stat_config)

        # Fallback: inline suppression if service unavailable
        if count < min_count:
            if display_mode == "null":
                return None, True
            elif display_mode == "asterisk":
                return "*", True
            elif display_mode == "less_than":
                return f"<{min_count}", True
            else:
                return None, True

        return value, False

    def to_dict(self, context=None):
        """Convert statistic to dictionary for API/UI consumption.

        Args:
            context: Optional context for context-specific config

        Returns:
            dict: Statistic data
        """
        self.ensure_one()

        config = self.get_context_config(context) if context else {}

        return {
            "name": self.name,
            "label": config.get("label", self.label),
            "description": self.description,
            "format": config.get("format", self.format),
            "unit": self.unit,
            "decimal_places": self.decimal_places,
            "category": self.category_id.code if self.category_id else None,
            "group": config.get("group"),
            "variable_accessor": self.variable_accessor,
            "minimum_count": config.get("minimum_count", self.minimum_count),
        }
