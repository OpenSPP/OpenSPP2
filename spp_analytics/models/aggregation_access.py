# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AggregationAccessRule(models.Model):
    """
    Access control rules for aggregation queries.

    Determines what level of data access a user/group has:
    - aggregate: Can only see counts and statistics (no individual records)
    - individual: Can see individual record IDs in results

    Also controls k-anonymity thresholds and scope restrictions.
    """

    _name = "spp.analytics.access.rule"
    _description = "Aggregation Access Rule"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        help="Human-readable name for this access rule.",
    )
    description = fields.Text(
        help="Optional description of what this rule grants.",
    )
    sequence = fields.Integer(
        default=10,
        help="Lower sequence = higher priority when multiple rules match.",
    )
    active = fields.Boolean(
        default=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Who this rule applies to (one of user/group)
    # -------------------------------------------------------------------------
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        ondelete="cascade",
        help="Specific user this rule applies to.",
    )
    group_id = fields.Many2one(
        comodel_name="res.groups",
        string="Security Group",
        ondelete="cascade",
        help="Security group this rule applies to.",
    )

    # -------------------------------------------------------------------------
    # Access level
    # -------------------------------------------------------------------------
    access_level = fields.Selection(
        selection=[
            ("aggregate", "Aggregates Only"),
            ("individual", "Individual Records"),
        ],
        required=True,
        default="aggregate",
        help=(
            "Aggregates Only: User can see counts and statistics but NOT individual record IDs. "
            "Individual Records: User can see individual record IDs in results."
        ),
    )

    # -------------------------------------------------------------------------
    # Privacy settings
    # -------------------------------------------------------------------------
    minimum_k_anonymity = fields.Integer(
        default=5,
        help="Minimum count for a cell before it's suppressed (k-anonymity). Higher = more private.",
    )

    # -------------------------------------------------------------------------
    # Scope restrictions
    # -------------------------------------------------------------------------
    allowed_scope_types = fields.Selection(
        selection=[
            ("all", "All Scope Types"),
            ("area_only", "Area-based Only"),
            ("predefined", "Predefined Scopes Only"),
        ],
        default="all",
        help=(
            "Restrict which scope types this user can query. "
            "Predefined means they can only use saved scope IDs, not inline definitions."
        ),
    )
    allow_inline_scopes = fields.Boolean(
        default=False,
        help=(
            "If False, user can only query predefined scope IDs, not create inline scope definitions. "
            "This prevents ad-hoc queries that could be used to narrow down individuals."
        ),
    )
    allowed_scope_ids = fields.Many2many(
        comodel_name="spp.analytics.scope",
        relation="spp_aggregation_access_rule_scope_rel",
        column1="rule_id",
        column2="scope_id",
        string="Allowed Scopes",
        help="If set, user can only query these specific scopes (for predefined mode).",
    )

    # -------------------------------------------------------------------------
    # Area restrictions
    # -------------------------------------------------------------------------
    allowed_area_ids = fields.Many2many(
        comodel_name="spp.area",
        relation="spp_aggregation_access_rule_area_rel",
        column1="rule_id",
        column2="area_id",
        string="Allowed Areas",
        help="If set, user can only query data from these specific areas (and optionally their children).",
    )
    include_child_areas = fields.Boolean(
        default=True,
        help="If True, allowed_area_ids includes child areas. If False, only the exact areas are allowed.",
    )

    # -------------------------------------------------------------------------
    # Dimension restrictions
    # -------------------------------------------------------------------------
    max_group_by_dimensions = fields.Integer(
        default=3,
        help="Maximum number of dimensions allowed in group_by. More dimensions = more granular = less private.",
    )
    allowed_dimension_ids = fields.Many2many(
        comodel_name="spp.demographic.dimension",
        relation="spp_aggregation_access_rule_dimension_rel",
        column1="rule_id",
        column2="dimension_id",
        string="Allowed Dimensions",
        help="If set, user can only group by these dimensions.",
    )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    @api.constrains("user_id", "group_id")
    def _check_user_or_group(self):
        """Ensure exactly one of user_id or group_id is set."""
        for rule in self:
            if rule.user_id and rule.group_id:
                raise ValidationError(_("A rule cannot apply to both a specific user and a group."))
            if not rule.user_id and not rule.group_id:
                raise ValidationError(_("A rule must apply to either a user or a group."))

    @api.constrains("minimum_k_anonymity")
    def _check_k_anonymity(self):
        """Ensure k-anonymity threshold is reasonable."""
        for rule in self:
            if rule.minimum_k_anonymity < 1:
                raise ValidationError(_("Minimum k-anonymity must be at least 1."))
            if rule.minimum_k_anonymity > 100:
                raise ValidationError(_("Minimum k-anonymity should not exceed 100."))

    @api.constrains("max_group_by_dimensions")
    def _check_max_dimensions(self):
        """Ensure max dimensions is reasonable."""
        for rule in self:
            if rule.max_group_by_dimensions < 0:
                raise ValidationError(_("Maximum group_by dimensions cannot be negative."))
            if rule.max_group_by_dimensions > 10:
                raise ValidationError(_("Maximum group_by dimensions should not exceed 10."))

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    @api.model
    def get_effective_rule_for_user(self, user=None):
        """
        Get the most permissive applicable access rule for a user.

        Rules are evaluated in sequence order. User-specific rules take precedence
        over group-based rules.

        :param user: res.users record (defaults to current user)
        :returns: Access rule record or None if no rule matches
        :rtype: spp.analytics.access.rule or None
        """
        user = user or self.env.user

        # First check for user-specific rule
        user_rule = self.search(
            [("user_id", "=", user.id), ("active", "=", True)],
            limit=1,
            order="sequence",
        )
        if user_rule:
            return user_rule

        # Then check for group-based rules
        group_rule = self.search(
            [("group_id", "in", user.group_ids.ids), ("active", "=", True)],
            limit=1,
            order="sequence",
        )
        return group_rule

    def check_scope_allowed(self, scope):
        """
        Check if a scope is allowed under this rule.

        :param scope: spp.analytics.scope record or dict for inline scope
        :returns: True if allowed
        :raises: ValidationError if not allowed
        """
        self.ensure_one()

        # Check inline scope restriction
        if isinstance(scope, dict) and not self.allow_inline_scopes:
            raise ValidationError(_("Inline scope definitions are not allowed for your access level."))

        # Get scope type
        scope_type = scope.get("scope_type") if isinstance(scope, dict) else scope.scope_type

        # Check scope type restriction
        if self.allowed_scope_types == "predefined":
            if isinstance(scope, dict):
                raise ValidationError(_("Only predefined scopes are allowed for your access level."))
            if self.allowed_scope_ids and scope.id not in self.allowed_scope_ids.ids:
                raise ValidationError(_("This scope is not in your allowed scope list."))

        if self.allowed_scope_types == "area_only":
            if scope_type not in ("area", "area_tag"):
                raise ValidationError(_("Only area-based scopes are allowed for your access level."))

        # Check area restrictions for explicit scopes
        if scope_type == "explicit" and self.allowed_area_ids:
            partner_ids = (
                scope.get("explicit_partner_ids") if isinstance(scope, dict) else scope.explicit_partner_ids.ids
            )
            self._check_explicit_scope_area_compliance(partner_ids)

        return True

    def check_dimensions_allowed(self, dimension_names):
        """
        Check if the requested dimensions are allowed.

        :param dimension_names: List of dimension names
        :returns: True if allowed
        :raises: ValidationError if not allowed
        """
        self.ensure_one()

        if len(dimension_names) > self.max_group_by_dimensions:
            raise ValidationError(
                _("Too many dimensions: maximum %d allowed, %d requested.")
                % (self.max_group_by_dimensions, len(dimension_names))
            )

        if self.allowed_dimension_ids:
            allowed_names = set(self.allowed_dimension_ids.mapped("name"))
            requested = set(dimension_names)
            disallowed = requested - allowed_names
            if disallowed:
                raise ValidationError(_("Dimensions not allowed: %s") % ", ".join(disallowed))

        return True

    def _check_explicit_scope_area_compliance(self, partner_ids):
        """
        Check if explicit partner IDs are within allowed areas.

        :param partner_ids: List of partner IDs
        :returns: True if allowed
        :raises: ValidationError if any partner is outside allowed areas
        """
        self.ensure_one()

        if not self.allowed_area_ids:
            # No area restrictions
            return True

        if not partner_ids:
            # Empty list is always allowed
            return True

        # Build set of allowed area IDs
        allowed_area_ids = set(self.allowed_area_ids.ids)

        # If include_child_areas is True, expand to include all child areas
        if self.include_child_areas:
            # Collect all parent_path values first, then do a single search using
            # OR-chained domain conditions to avoid N+1 queries inside a loop.
            parent_paths = [area.parent_path for area in self.allowed_area_ids if area.parent_path]
            if parent_paths:
                domain = ["|"] * (len(parent_paths) - 1)
                for path in parent_paths:
                    domain.append(("parent_path", "like", f"{path}%"))
                child_areas = self.env["spp.area"].sudo().search(domain)  # nosemgrep: odoo-sudo-without-context
                allowed_area_ids.update(child_areas.ids)

        # Get area_ids for the partners
        partners = self.env["res.partner"].sudo().browse(partner_ids)  # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models  # noqa: E501  # fmt: skip
        partner_area_ids = set(partners.mapped("area_id").ids)

        # Check if all partner areas are in allowed areas
        disallowed_area_ids = partner_area_ids - allowed_area_ids

        if disallowed_area_ids:
            # Get area names for error message
            disallowed_areas = self.env["spp.area"].sudo().browse(list(disallowed_area_ids))  # nosemgrep: odoo-sudo-without-context  # noqa: E501  # fmt: skip
            area_names = ", ".join(disallowed_areas.mapped("draft_name"))
            raise ValidationError(
                _("Some registrants are outside your allowed areas. Disallowed areas: %s") % area_names
            )

        return True
