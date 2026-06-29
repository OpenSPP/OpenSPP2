# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CEL Variable - Core variable model for CEL expressions.

This module provides the core variable definition model used by the CEL engine.
Variables can represent:
- Model fields (res.partner.income)
- Constants (poverty_line = 2500)
- Computed values (age_years(r.birthdate))
- Aggregations (members.count(m, age_years(m.birthdate) < 18))
- External data sources (education.attendance from external APIs)

UI extensions (labels, descriptions, registry display) are provided by spp_studio.

Caching and Period Support (Unified Variable System):
- Variables can define caching strategies (none, session, ttl, manual)
- Variables can define period granularity for historical data support
- Cached values are stored in spp.data.value
"""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Valid period_key formats per granularity
PERIOD_KEY_PATTERNS = {
    "daily": re.compile(r"^\d{4}-\d{2}-\d{2}$"),  # 2024-12-15
    "monthly": re.compile(r"^\d{4}-\d{2}$"),  # 2024-12
    "quarterly": re.compile(r"^\d{4}-Q[1-4]$"),  # 2024-Q4
    "yearly": re.compile(r"^\d{4}$"),  # 2024
    "snapshot": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),  # ISO datetime
}


class CELVariable(models.Model):
    """CEL Variable - Core variable definitions for the CEL engine.

    Variables provide a named abstraction over data sources:
    - `r.income` - field from current record
    - `poverty_line` - global constant
    - `r.child_count` - aggregate over members

    Expression syntax follows ADR-008:
    - `r.field` - Field on current record
    - `r.variable` - Variable for current record
    - `constant` - Global constant (no prefix)
    - `m.field` - Member field (inside members.* only)
    """

    _name = "spp.cel.variable"
    _description = "CEL Variable"
    _order = "category_id, sequence, name"

    # Database-level constraints for uniqueness and performance
    _unique_name = models.Constraint(
        "UNIQUE(name)",
        "Variable name must be unique.",
    )
    _unique_accessor_context = models.Constraint(
        "UNIQUE(cel_accessor, applies_to)",
        "CEL accessor must be unique per context (applies_to).",
    )

    # ─── Identity ───────────────────────────────────────────────────────
    name = fields.Char(
        string="Name",
        required=True,
        index=True,
        help="Technical name (e.g., 'income', 'hh_size', 'is_female')",
    )

    # ─── CEL Access ─────────────────────────────────────────────────────
    cel_accessor = fields.Char(
        string="CEL Accessor",
        required=True,
        index=True,
        help="How to reference in CEL expressions: 'income', 'hh_size', 'is_female'",
    )

    # ─── Source (polymorphic) ───────────────────────────────────────────
    source_type = fields.Selection(
        selection=[
            ("field", "Model Field"),
            ("external", "External Source"),
            ("scoring", "Scoring Result"),
            ("vocabulary", "Vocabulary Concept"),
            ("computed", "Computed (CEL)"),
            ("constant", "Constant/Parameter"),
            ("aggregate", "Member Aggregate"),
        ],
        string="Source Type",
        required=True,
        help="Where this variable's data comes from",
    )

    # Source references (based on source_type)
    source_model = fields.Char(
        string="Source Model",
        help="For field type: model name (e.g., 'res.partner')",
    )
    source_field = fields.Char(
        string="Source Field",
        help="For field type: field name (e.g., 'income')",
    )
    external_provider_id = fields.Many2one(
        comodel_name="spp.data.provider",
        string="External Provider",
        help="For external type: the data provider configuration",
        ondelete="set null",
    )
    # Note: scoring_model_id is added by spp_scoring module via inheritance

    # ─── Computed Variables ─────────────────────────────────────────────
    cel_expression = fields.Text(
        string="CEL Expression",
        compute="_compute_cel_expression",
        store=True,
        readonly=False,
        help="CEL expression for this variable. Auto-computed for aggregates.",
    )

    # ─── Constants ──────────────────────────────────────────────────────
    default_value = fields.Char(
        string="Default Value",
        help="Default value for constants. Can be overridden at program level.",
    )
    is_program_configurable = fields.Boolean(
        string="Program Configurable",
        default=False,
        help="If true, programs can override this constant's value.",
    )

    # ─── Aggregates ─────────────────────────────────────────────────────
    aggregate_type = fields.Selection(
        selection=[
            ("count", "Count"),
            ("sum", "Sum"),
            ("avg", "Average"),
            ("min", "Minimum"),
            ("max", "Maximum"),
            ("exists", "Exists (any match)"),
        ],
        string="Aggregate Type",
        help="Type of aggregation to perform over members.",
    )
    aggregate_target = fields.Selection(
        selection=[
            ("members", "Household Members"),
            ("enrollments", "Program Enrollments"),
            ("entitlements", "Entitlements"),
        ],
        string="Aggregate Target",
        default="members",
        help="What to aggregate over.",
    )
    aggregate_filter = fields.Text(
        string="Aggregate Filter",
        help=(
            "CEL filter expression for aggregation (e.g., 'age_years(m.birthdate) < 18'). "
            "Use 'm.' prefix for member fields."
        ),
    )
    aggregate_field = fields.Char(
        string="Aggregate Field",
        help="Field to aggregate for sum/avg/min/max (e.g., 'income'). Not needed for count/exists.",
    )

    # ─── Classification ─────────────────────────────────────────────────
    category_id = fields.Many2one(
        comodel_name="spp.cel.variable.category",
        string="Category",
        help="Variable category for organization",
    )
    value_type = fields.Selection(
        selection=[
            ("number", "Number"),
            ("boolean", "Yes/No"),
            ("string", "Text"),
            ("date", "Date"),
            ("money", "Money"),
            ("list", "List"),
        ],
        string="Value Type",
        required=True,
        default="number",
        help="Type of value this variable contains",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Display order within category",
    )

    # ─── Context ────────────────────────────────────────────────────────
    applies_to = fields.Selection(
        selection=[
            ("individual", "Individual"),
            ("group", "Group/Household"),
            ("both", "Both"),
        ],
        string="Applies To",
        default="both",
        help="Context where this variable can be used.",
    )

    # ─── Lifecycle ──────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        string="Status",
        default="draft",
        help="Variable lifecycle state",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive variables are hidden from the variable picker",
    )
    is_system = fields.Boolean(
        string="System Variable",
        default=False,
        help="System-generated variables (e.g., from scoring models) cannot be manually edited.",
    )

    # ─── Caching Capability ──────────────────────────────────────────────
    cache_strategy = fields.Selection(
        selection=[
            ("none", "No Caching"),
            ("session", "Session/Request Cache"),
            ("ttl", "TTL-based Cache"),
            ("manual", "Manual Refresh Only"),
        ],
        string="Cache Strategy",
        default="none",
        help=(
            "How this variable's values should be cached:\n"
            "- No Caching: Always compute/fetch fresh\n"
            "- Session: Cache per request/batch operation\n"
            "- TTL: Cache in database with expiration time\n"
            "- Manual: Only refresh on explicit trigger"
        ),
    )
    cache_ttl_seconds = fields.Integer(
        string="Cache TTL (seconds)",
        default=86400,
        help="Time-to-live for cached values. Only used when cache_strategy is 'ttl'.",
    )
    invalidate_on_member_change = fields.Boolean(
        string="Invalidate on Member Change",
        default=True,
        help="For aggregates: invalidate cache when group membership changes.",
    )
    invalidate_on_field_change = fields.Char(
        string="Invalidate on Field Change",
        help="Comma-separated field names that trigger cache invalidation when changed.",
    )

    # ─── Period Capability ───────────────────────────────────────────────
    period_granularity = fields.Selection(
        selection=[
            ("current", "Current Value Only"),
            ("daily", "Daily"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
            ("snapshot", "Point-in-time Snapshot"),
        ],
        string="Period Granularity",
        default="current",
        help=(
            "How this variable handles time-based data:\n"
            "- Current: Always latest value, no history\n"
            "- Daily/Monthly/Quarterly/Yearly: Values stored per period\n"
            "- Snapshot: Point-in-time freeze (e.g., at enrollment)"
        ),
    )
    supports_historical = fields.Boolean(
        string="Supports Historical Queries",
        compute="_compute_supports_historical",
        store=True,
        help="Whether this variable can be queried for historical periods.",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED METHODS
    # ═══════════════════════════════════════════════════════════════════════

    @api.depends("period_granularity")
    def _compute_supports_historical(self):
        """Compute whether this variable supports historical queries.

        Variables with period_granularity other than 'current' can be
        queried for historical periods (e.g., "what was the value in Dec 2024?").
        """
        for var in self:
            var.supports_historical = var.period_granularity != "current"

    @api.depends(
        "source_type",
        "aggregate_type",
        "aggregate_target",
        "aggregate_field",
        "aggregate_filter",
    )
    def _compute_cel_expression(self):
        """Auto-compute cel_expression for aggregate variables.

        For aggregate source_type, generates CEL expressions like:
        - members.count(age_years(m.birthdate) < 18)
        - members.sum(m.income, true)
        - members.exists(m.is_disabled)

        Other source_types keep their manually-set cel_expression.
        """
        for var in self:
            if var.source_type == "aggregate":
                var.cel_expression = var._build_aggregate_cel()
            # Other source_types: preserve manually-set value (readonly=False)

    def _build_aggregate_cel(self):
        """Build CEL expression for aggregate variables.

        Generates expressions following ADR-008 syntax:
        - count: members.count(filter) - count matching members
        - exists: members.exists(filter) - true if any match
        - sum: members.sum(m.field, filter) - sum of field values
        - avg: members.avg(m.field, filter) - average of field values
        - min: members.min(m.field, filter) - minimum field value
        - max: members.max(m.field, filter) - maximum field value

        Note: The m. prefix is used inside aggregation expressions to
        reference member fields, following the standardized syntax.
        """
        self.ensure_one()

        target = self.aggregate_target or "members"
        agg_type = self.aggregate_type or "count"
        filter_expr = self.aggregate_filter or "true"
        field_expr = self.aggregate_field

        if agg_type == "count":
            return f"{target}.count({filter_expr})"
        elif agg_type == "exists":
            return f"{target}.exists({filter_expr})"
        elif agg_type in ("sum", "avg", "min", "max"):
            if field_expr:
                # Field should use m. prefix if referencing member
                field_ref = f"m.{field_expr}" if not field_expr.startswith("m.") else field_expr
                return f"{target}.{agg_type}(m, {field_ref}, {filter_expr})"
            _logger.warning(
                "Variable '%s' uses %s aggregation without field. Please specify aggregate_field.",
                self.name,
                agg_type,
            )
            return self.cel_accessor

        return self.cel_accessor

    # ═══════════════════════════════════════════════════════════════════════
    # RESOLUTION METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def get_cel_expression(self, program_id=None):
        """Generate the CEL expression for this variable.

        This is the primary method used by the variable resolver to
        expand variable references into their actual CEL expressions.

        Args:
            program_id: Optional program ID for constant overrides

        Returns:
            str: CEL expression string
        """
        self.ensure_one()

        if self.source_type == "field":
            # Direct field access with r. prefix
            return f"r.{self.source_field}" if self.source_field else self.cel_accessor

        elif self.source_type == "computed":
            return self.cel_expression or self.cel_accessor

        elif self.source_type == "constant":
            # Check for program override first
            if program_id and self.is_program_configurable:
                # Check if spp_programs is installed (provides spp.program)
                if "spp.cel.program.parameter" in self.env:
                    param = self.env["spp.cel.program.parameter"].search(
                        [
                            ("program_id", "=", program_id),
                            ("variable_id", "=", self.id),
                        ],
                        limit=1,
                    )
                    if param:
                        return param.value
            return self.default_value or self.cel_accessor

        elif self.source_type == "aggregate":
            return self.cel_expression or self._build_aggregate_cel()

        elif self.source_type == "vocabulary":
            return self.cel_expression or self.cel_accessor

        elif self.source_type == "external":
            # External variables are evaluated via cache lookup
            # The cel_expression can contain fallback logic
            return self.cel_expression or self.cel_accessor

        elif self.source_type == "scoring":
            # Scoring variables are evaluated via cache lookup
            return self.cel_expression or self.cel_accessor

        return self.cel_accessor

    def is_data_api_pullable(self):
        """Whether this variable's cached values may be exposed through the
        generic external Data API (``/Data/pull`` and ``/Data/variables``).

        The Data API is the push/pull channel for ordinary external-provider
        data, so only variables backed by an external provider are pullable.
        Computed/scoring/aggregate variables (e.g. PMT scores) are internal and
        must not be retrievable through this channel. The DCI indicators module
        further excludes DCI-backed providers (inter-registry data has its own
        consent/provider boundary) by overriding this method. Callers default to
        deny when a requested name resolves to no variable (fail closed).
        """
        self.ensure_one()
        return bool(self.source_type == "external" and self.external_provider_id)

    @api.model
    def _get_data_api_pullable_domain(self):
        """Search domain selecting variables pullable through the Data API.

        The DB-level counterpart of ``is_data_api_pullable`` (kept in sync with
        it), so ``/Data/variables`` can filter, count and paginate correctly in
        a single query. The DCI indicators module extends this to also exclude
        DCI-backed providers.
        """
        return [
            ("active", "=", True),
            ("source_type", "=", "external"),
            ("external_provider_id", "!=", False),
        ]

    # ═══════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═══════════════════════════════════════════════════════════════════════

    @api.constrains("name")
    def _check_name_unique(self):
        """Ensure variable name is unique."""
        for rec in self:
            duplicate = self.search_count(
                [
                    ("name", "=", rec.name),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(_("Variable name '%s' already exists.") % rec.name)

    @api.constrains("cel_accessor")
    def _check_cel_accessor_unique(self):
        """Ensure CEL accessor is unique per context.

        We allow the same CEL accessor to exist for different contexts
        (e.g., 'income' for individual vs group) so that expressions
        can stay simple while implementations differ by applies_to.
        """
        for rec in self:
            duplicate = self.search_count(
                [
                    ("cel_accessor", "=", rec.cel_accessor),
                    ("applies_to", "=", rec.applies_to or "both"),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _("CEL accessor '%(accessor)s' already exists for context '%(ctx)s'.")
                    % {
                        "accessor": rec.cel_accessor,
                        "ctx": rec.applies_to or "both",
                    }
                )

    @api.constrains("cache_strategy", "cache_ttl_seconds")
    def _check_cache_ttl(self):
        """Ensure cache_ttl_seconds is positive when cache_strategy is 'ttl'."""
        for rec in self:
            if rec.cache_strategy == "ttl" and rec.cache_ttl_seconds <= 0:
                raise ValidationError(_("Cache TTL must be positive when using TTL-based caching."))

    @api.constrains("source_type", "external_provider_id")
    def _check_external_provider(self):
        """Warn if external source type has no provider configured."""
        for rec in self:
            if rec.source_type == "external" and not rec.external_provider_id:
                _logger.warning(
                    "Variable '%s' has external source type but no provider configured. "
                    "Values can only be pushed via API or set manually.",
                    rec.name,
                )

    # ═══════════════════════════════════════════════════════════════════════
    # CRUD OVERRIDES
    # ═══════════════════════════════════════════════════════════════════════

    def write(self, vals):
        """Override write to invalidate resolver cache on relevant changes."""
        result = super().write(vals)

        # Invalidate variable resolution cache if relevant fields changed
        cache_invalidating_fields = {
            "cel_expression",
            "default_value",
            "cel_accessor",
            "source_type",
            "source_field",
            "aggregate_type",
            "aggregate_filter",
            "aggregate_field",
            "aggregate_target",
            "applies_to",
            "active",
            "state",
            "name",
            "cache_strategy",
            "period_granularity",
            "external_provider_id",
        }
        if cache_invalidating_fields & set(vals.keys()):
            self._invalidate_resolver_cache()

        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to invalidate resolver cache."""
        records = super().create(vals_list)

        # Invalidate cache when new variables are created
        if records:
            records[0]._invalidate_resolver_cache()

        return records

    def unlink(self):
        """Override unlink to invalidate resolver cache."""
        # Invalidate cache before delete
        self._invalidate_resolver_cache()
        return super().unlink()

    def _invalidate_resolver_cache(self):
        """Invalidate all CEL caches.

        Called when variable definitions change to ensure:
        - Variable resolver cache uses updated variable definitions
        - Translation cache rebuilds with new variable expansions
        - Profile cache reflects any configuration changes

        This prevents stale cache issues where expressions continue to
        use old variable definitions after modifications.
        """
        try:
            # Invalidate all CEL caches via the service facade
            # This ensures profile cache, translation cache, and resolver cache
            # are all cleared in a coordinated manner
            cel_service = self.env["spp.cel.service"]
            cel_service.invalidate_caches()
            _logger.debug("CEL caches invalidated after variable change")
        except Exception as e:
            _logger.warning("Could not invalidate CEL caches: %s", e)

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def get_by_cel_accessor(self, accessor, context_type=None):
        """Find variable by CEL accessor.

        Args:
            accessor (str): CEL accessor string
            context_type (str): Optional context filter ('individual', 'group', 'both')

        Returns:
            recordset: Variable record or empty recordset
        """
        domain = [("cel_accessor", "=", accessor), ("active", "=", True)]
        if context_type and context_type != "both":
            domain.append(("applies_to", "in", [context_type, "both"]))
        return self.search(domain, limit=1)

    def action_activate(self):
        """Activate the variable."""
        for rec in self:
            if rec.state != "active":
                rec.state = "active"

    def action_deactivate(self):
        """Deactivate the variable."""
        for rec in self:
            if rec.state != "inactive":
                rec.state = "inactive"

    def action_reactivate(self):
        """Reactivate an inactive variable (returns it to active state)."""
        for rec in self:
            if rec.state == "inactive":
                rec.state = "active"

    def action_set_draft(self):
        """Return variable to draft state (only from inactive)."""
        for rec in self:
            if rec.state == "inactive":
                rec.state = "draft"

    def action_view_source(self):
        """View the source of this variable (stub - overridden in spp_studio)."""
        return True

    def validate_period_key(self, period_key):
        """Validate that a period_key matches this variable's granularity.

        Args:
            period_key: The period key string to validate

        Returns:
            bool: True if valid, False otherwise

        Raises:
            ValidationError: If period_key format is invalid
        """
        self.ensure_one()

        if self.period_granularity == "current":
            # Current variables don't use period keys
            if period_key and period_key != "current":
                raise ValidationError(
                    _("Variable '%(var)s' does not support period keys (granularity is 'current').")
                    % {"var": self.name}
                )
            return True

        if not period_key:
            raise ValidationError(
                _("Period key is required for variable '%(var)s' (granularity: %(gran)s).")
                % {"var": self.name, "gran": self.period_granularity}
            )

        pattern = PERIOD_KEY_PATTERNS.get(self.period_granularity)
        if pattern and not pattern.match(period_key):
            raise ValidationError(
                _("Invalid period key '%(key)s' for variable '%(var)s'. Expected format for %(gran)s granularity.")
                % {"key": period_key, "var": self.name, "gran": self.period_granularity}
            )

        return True

    def uses_cache(self):
        """Check if this variable uses any form of caching.

        Returns:
            bool: True if variable values may be cached
        """
        self.ensure_one()
        return self.cache_strategy != "none"

    def uses_persistent_cache(self):
        """Check if this variable uses persistent (database) caching.

        Returns:
            bool: True if variable values are stored in spp.data.value
        """
        self.ensure_one()
        return self.cache_strategy in ("ttl", "manual")
