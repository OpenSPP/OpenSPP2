# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Logic Variable - UI extension for CEL Variable.

This module extends spp.cel.variable with UI-specific features:
- Labels and descriptions for user-friendly display
- Governance workflow (draft/active/inactive lifecycle)
- Source references (indicators, scoring, vocabulary)
- Field creation wizard integration
- Usage tracking
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# System parameter key for governance mode
GOVERNANCE_PARAM = "spp_studio.governance_enabled"


class LogicVariable(models.Model):
    """UI Extension for CEL Variable.

    Extends spp.cel.variable with Studio-specific features while
    keeping the same database table. This allows the CEL resolver
    to work with a single variable model.
    """

    _inherit = [
        "spp.cel.variable",
        "spp.studio.mixin",
        "mail.thread",
        "mail.activity.mixin",
    ]
    _name = "spp.cel.variable"  # Keep same table
    _description = "Logic Variable"
    _order = "category_id, sequence, name"

    # ═══════════════════════════════════════════════════════════════════════
    # GOVERNANCE
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def _is_governance_enabled(self):
        """Check if governance mode is enabled via system parameter."""
        return self.env["ir.config_parameter"].sudo().get_param(GOVERNANCE_PARAM, "False").lower() == "true"

    def _check_governance_edit(self, vals):
        """Check if edit is allowed based on governance settings.

        When governance is enabled, active variables cannot be edited
        (except for state changes).
        """
        if not self._is_governance_enabled():
            return  # Governance disabled, allow all edits

        allowed_fields = {"state", "deactivated_by_id", "deactivated_date"}
        for record in self:
            if record.state == "active" and not self.env.context.get("force_write"):
                if set(vals.keys()) - allowed_fields:
                    raise UserError(
                        _(
                            "Cannot modify '%(name)s' while it is Active.\n\n"
                            "Active variables are locked to ensure data consistency.\n"
                            "To edit: Click 'Deactivate' first, make your changes, then 'Reactivate'.",
                            name=record.label or record.name,
                        )
                    )

    # ═══════════════════════════════════════════════════════════════════════
    # UI FIELDS (not in core spp.cel.variable)
    # ═══════════════════════════════════════════════════════════════════════

    label = fields.Char(
        string="Label",
        help="User-friendly label (e.g., 'Household Income')",
    )
    description = fields.Text(
        string="Description",
        help="What this variable represents",
    )
    unit = fields.Char(
        string="Unit",
        help="Unit of measurement (e.g., 'USD', 'years', '%')",
    )
    placement_zone_code = fields.Selection(
        selection="_get_placement_zone_selection",
        string="Default Placement Zone",
        help="Default registry form zone to suggest when creating a custom field from this variable.",
    )

    # ─── Discoverability ────────────────────────────────────────────────
    synonyms = fields.Char(
        string="Synonyms",
        help="Comma-separated search terms: 'family size, household members'",
    )
    example_values = fields.Char(
        string="Example Values",
        help="Example values (e.g., '1000, 5000, 10000')",
    )

    # ─── Data Availability ──────────────────────────────────────────────
    data_source = fields.Selection(
        selection=[
            ("local", "Local Data"),
            ("computed", "Computed on Demand"),
            ("external", "External API"),
        ],
        string="Data Source",
        default="local",
        help="How this data is obtained",
    )
    coverage_percent = fields.Float(
        string="Coverage %",
        readonly=True,
        help="Percentage of registrants with data for this variable. Click 'Calculate Coverage' to update.",
    )

    # ─── Metadata ───────────────────────────────────────────────────────
    is_system = fields.Boolean(
        string="System Variable",
        default=False,
        help="System variables are auto-discovered, not user-created",
    )

    # ─── UI State (global user preference) ─────────────────────────────────
    show_advanced = fields.Boolean(
        string="Show Advanced Options",
        compute="_compute_show_advanced",
        inverse="_inverse_show_advanced",
        store=False,
        help="Toggle to show advanced configuration options (caching, historical data, etc.). "
        "This preference is saved per user.",
    )

    # ─── Source References (Studio-specific) ────────────────────────────
    # NOTE: source_scoring_id moved to spp_studio_scoring bridge module
    # NOTE: source_indicator_id removed - spp.indicator.definition deprecated
    # External data now uses source_type='external' with external_provider_id
    source_concept_id = fields.Many2one(
        comodel_name="spp.vocabulary.concept.group",
        string="Source Concept Group",
        help="For vocabulary type: concept group",
    )

    # ─── Usage Tracking ─────────────────────────────────────────────────
    logic_usage_count = fields.Integer(
        string="Logic Usage Count",
        compute="_compute_logic_usage_count",
        store=True,
        compute_sudo=True,
        help="Number of logic records using this variable (click refresh button to update)",
    )

    # ─── Field Existence (for source_type='field') ─────────────────────
    field_exists = fields.Selection(
        selection=[
            ("exists", "Field Exists"),
            ("missing", "Field Missing"),
            ("unknown", "Unknown"),
            ("na", "Not Applicable"),
        ],
        string="Field Status",
        compute="_compute_field_exists",
        store=True,
        help="Whether the source field exists on the source model (click refresh button to update).",
    )
    field_exists_message = fields.Char(
        string="Field Status Message",
        compute="_compute_field_exists",
        store=True,
        help="Detailed message about field existence status.",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED METHODS
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def _get_placement_zone_selection(self):
        """Return available Studio placement zones as (code, label).

        Uses spp.studio.placement.zone when the Studio Fields module is installed.
        Returns an empty list otherwise.
        """
        Zone = self.env.get("spp.studio.placement.zone")
        if not Zone:
            return []

        zones = Zone.search([], order="target_type, tab_sequence, sequence")
        result = []
        for zone in zones:
            label = f"{zone.tab_name} > {zone.name}"
            # Show target type prefix for clarity
            if zone.target_type:
                label = f"[{zone.target_type}] {label}"
            result.append((zone.code, label))
        return result

    def _guess_default_placement(self):
        """Heuristic to pick a sensible default placement zone.

        Uses variable category + applies_to to choose between:
        - individual_profile_demographics / contact / financial / participation
        - group_profile_contact / financial / participation
        """
        self.ensure_one()

        category_code = self.category_id.code if self.category_id and self.category_id.code else ""
        applies = self.applies_to or "both"

        # Determine target registry
        target = "individual"
        if applies == "group":
            target = "group"

        if target == "individual":
            if category_code in (
                "demographics",
                "household",
                "characteristics",
                "location",
            ):
                return "individual_profile_demographics"
            if category_code == "economic":
                return "individual_profile_financial"
            if category_code in ("program", "indicators", "scoring"):
                return "individual_participation"
            # Fallback
            return "individual_profile_demographics"
        else:
            # Group registry
            if category_code == "economic":
                return "group_profile_financial"
            if category_code in (
                "demographics",
                "household",
                "characteristics",
                "location",
            ):
                return "group_profile_contact"
            if category_code in ("program", "indicators", "scoring"):
                return "group_participation"
            # Fallback
            return "group_profile_contact"

    def _compute_logic_usage_count(self):
        """Count logic records that reference this variable.

        Searches CEL expressions for the variable's cel_accessor.
        This is computed on-demand (not stored) since it's a text search.
        """
        # Check if spp.cel.expression model exists (may not be installed)
        if "spp.cel.expression" not in self.env:
            for record in self:
                record.logic_usage_count = 0
            return

        Logic = self.env["spp.cel.expression"]
        for record in self:
            if record.cel_accessor:
                # Search for variable name in CEL expressions
                record.logic_usage_count = Logic.search_count(
                    [
                        "|",
                        ("cel_expression", "ilike", record.cel_accessor),
                        ("compiled_expression", "ilike", record.cel_accessor),
                    ]
                )
            else:
                record.logic_usage_count = 0

    def _compute_show_advanced(self):
        """Read show_advanced preference from current user."""
        show_advanced = self.env.user.spp_studio_show_advanced
        for rec in self:
            rec.show_advanced = show_advanced

    def _inverse_show_advanced(self):
        """Save show_advanced preference to current user."""
        # Get the value from any record (they all compute from the same source)
        if self:
            new_value = self[0].show_advanced
            if self.env.user.spp_studio_show_advanced != new_value:
                self.env.user.sudo().write({"spp_studio_show_advanced": new_value})

    @api.depends("source_type", "source_model", "source_field")
    def _compute_field_exists(self):
        """Check if source_field exists on source_model."""
        for rec in self:
            if rec.source_type != "field":
                rec.field_exists = "na"
                rec.field_exists_message = ""
                continue

            if not rec.source_model or not rec.source_field:
                rec.field_exists = "unknown"
                rec.field_exists_message = _("Model or field not specified")
                continue

            try:
                # Check if model exists
                if rec.source_model not in self.env:
                    rec.field_exists = "missing"
                    rec.field_exists_message = _("Model '%s' not found") % rec.source_model
                    continue

                # Check if field exists on model
                model = self.env[rec.source_model]
                if hasattr(model, rec.source_field):
                    rec.field_exists = "exists"
                    # Get field description for friendly message
                    field_info = model.fields_get([rec.source_field])
                    if field_info and rec.source_field in field_info:
                        field_label = field_info[rec.source_field].get("string", rec.source_field)
                        rec.field_exists_message = _("Field '%s' exists on %s") % (
                            field_label,
                            rec.source_model,
                        )
                    else:
                        rec.field_exists_message = _("Field exists")
                else:
                    rec.field_exists = "missing"
                    rec.field_exists_message = _("Field '%s' not found on model '%s'") % (
                        rec.source_field,
                        rec.source_model,
                    )

            except Exception as e:
                _logger.warning(
                    "Error checking field existence for variable %s: %s",
                    rec.name,
                    str(e),
                )
                rec.field_exists = "unknown"
                rec.field_exists_message = _("Could not verify: %s") % str(e)

    # ═══════════════════════════════════════════════════════════════════════
    # CRUD OVERRIDES
    # ═══════════════════════════════════════════════════════════════════════

    def write(self, vals):
        """Override write to enforce governance edit protection."""
        self._check_governance_edit(vals)
        return super().write(vals)

    def unlink(self):
        """Override unlink to respect governance settings."""
        # Allow module uninstalls/updates (called via ir.model.data with
        # context['module']) to delete variables by first deactivating them.
        if self.env.context.get("module"):
            active_records = self.filtered(lambda r: getattr(r, "state", False) == "active")
            if active_records:
                active_records.write({"state": "inactive"})

        if self._is_governance_enabled():
            for record in self:
                if record.state == "active":
                    raise UserError(
                        _(
                            "Cannot delete active variable '%(name)s'. " "Deactivate it first.",
                            name=record.label or record.name,
                        )
                    )

        return super().unlink()

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE HOOKS (from spp.studio.mixin)
    # ═══════════════════════════════════════════════════════════════════════

    def action_activate(self):
        """Activate variable.

        For field-based variables with a missing field, redirect the user
        straight into the "Create Field" flow instead of just raising an
        error. Once the field is created or mapped, they can activate again.
        """
        self.ensure_one()

        if self.source_type == "field" and self.field_exists == "missing":
            # Open Studio Fields wizard with this variable prefilled
            return self.action_create_field()

        return super().action_activate()

    def _pre_activate(self):
        """Validate that variable is usable before activation.

        - Field-based variables must point to an existing field.
        - Computed/aggregate variables must have a valid CEL expression with no
          missing variables (according to the variable resolver).
        """
        for rec in self:
            errors = []

            # For model field variables, require the field to exist
            if rec.source_type == "field" and rec.field_exists == "missing":
                field_name = rec.source_field or ""
                model_name = rec.source_model or ""
                errors.append(
                    _(
                        "Missing Field: '%(field)s' does not exist on %(model)s\n\n"
                        "This variable needs a database field to store its data.\n"
                        "Choose one of these options:\n"
                        "  1. Click 'Create Field' to create a new field\n"
                        "  2. Click 'Map to Existing Field' to use an existing one",
                        field=field_name,
                        model=model_name,
                    )
                )

            # For computed / aggregate variables, validate the CEL expression
            if rec.source_type in ("computed", "aggregate"):
                expr = rec.get_cel_expression()
                if expr:
                    resolver = self.env["spp.cel.variable.resolver"]

                    # Derive a reasonable context from applies_to
                    context_type = "group"
                    if rec.applies_to == "individual":
                        context_type = "individual"

                    result = resolver.validate_expression(
                        expr,
                        program_id=None,
                        context_type=context_type,
                    )
                    if not result.get("valid"):
                        errors.extend(result.get("errors") or [])

            if errors:
                raise UserError(
                    _(
                        "Cannot Activate: %(name)s\n\n%(errors)s",
                        name=rec.label or rec.name,
                        errors="\n".join(errors),
                    )
                )

    # ═══════════════════════════════════════════════════════════════════════
    # DISPLAY METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def name_get(self):
        """Return label if set, otherwise fall back to name.

        Returns:
            list: List of (id, name) tuples
        """
        result = []
        for rec in self:
            display = rec.label or rec.name
            if rec.unit:
                display = f"{display} ({rec.unit})"
            result.append((rec.id, display))
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════════════

    def action_view_logic_usage(self):
        """View logic records using this variable.

        Searches for logic records that reference this variable's cel_accessor
        in their CEL expression.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Logic Using '%s'") % (self.label or self.cel_accessor),
            "res_model": "spp.cel.expression",
            "view_mode": "list,form",
            "domain": [
                "|",
                ("cel_expression", "ilike", self.cel_accessor),
                ("compiled_expression", "ilike", self.cel_accessor),
            ],
            "context": {"create": False},
        }

    def action_calculate_coverage(self):
        """Calculate percentage of registrants with data for this variable.

        This is an on-demand action to avoid performance issues with large datasets.
        """
        for rec in self:
            coverage = 0.0

            # For field-based variables, query res.partner
            if rec.source_type == "field" and rec.source_model == "res.partner":
                try:
                    Partner = self.env["res.partner"]
                    total_partners = Partner.search_count([("is_registrant", "=", True)])

                    if total_partners > 0 and rec.source_field:
                        field_name = rec.source_field
                        if field_name and hasattr(Partner, field_name):
                            partners_with_data = Partner.search_count(
                                [
                                    ("is_registrant", "=", True),
                                    (field_name, "!=", False),
                                ]
                            )
                            coverage = (partners_with_data / total_partners) * 100.0
                except Exception as e:
                    _logger.warning(
                        "Could not compute coverage for variable %s: %s",
                        rec.name,
                        str(e),
                    )

            # For other types, assume 100% coverage if source exists
            elif rec.source_type in ("indicator", "scoring", "vocabulary", "computed"):
                coverage = 100.0

            rec.coverage_percent = coverage

        # Return notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Coverage Calculated"),
                "message": _("Coverage percentage has been updated for %d variable(s).") % len(self),
                "type": "success",
                "sticky": False,
            },
        }

    def action_refresh_usage_count(self):
        """Manually refresh the logic_usage_count field.

        This is an on-demand action to update the stored usage count without
        triggering automatic recomputation on every variable access.
        """
        for rec in self:
            # Trigger recomputation by calling the compute method directly
            rec._compute_logic_usage_count()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Usage Count Refreshed"),
                "message": _("Logic usage count has been updated for %d variable(s).") % len(self),
                "type": "success",
                "sticky": False,
            },
        }

    def action_refresh_field_status(self):
        """Manually refresh the field_exists and field_exists_message fields.

        This is an on-demand action to update the stored field existence status
        without triggering automatic recomputation on every variable access.
        """
        for rec in self:
            # Trigger recomputation by calling the compute method directly
            rec._compute_field_exists()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Field Status Refreshed"),
                "message": _("Field existence status has been updated for %d variable(s).") % len(self),
                "type": "success",
                "sticky": False,
            },
        }

    def action_view_source(self):
        """Open the source record for this variable.

        Returns:
            dict: Action to open source record
        """
        self.ensure_one()

        if self.source_type == "external" and self.external_provider_id:
            # External source - show the provider configuration
            return {
                "type": "ir.actions.act_window",
                "name": _("External Data Provider"),
                "res_model": "spp.data.provider",
                "res_id": self.external_provider_id.id,
                "view_mode": "form",
            }
        elif hasattr(self, "source_scoring_id") and self.source_scoring_id:
            # source_scoring_id field provided by spp_studio_scoring bridge module
            return {
                "type": "ir.actions.act_window",
                "name": _("Source Scoring Model"),
                "res_model": "spp.scoring.model",
                "res_id": self.source_scoring_id.id,
                "view_mode": "form",
            }
        elif self.source_type == "vocabulary" and self.source_concept_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Source Concept Group"),
                "res_model": "spp.vocabulary.concept.group",
                "res_id": self.source_concept_id.id,
                "view_mode": "form",
            }
        else:
            raise ValidationError(_("No source record available for this variable."))

    def action_create_field(self):
        """Open the guided Studio Field Builder wizard.

        This is used when a field-based variable points to a missing field.
        The wizard will:
        - Prefill label/target/type/placement based on the variable
        - Create the Studio Field
        - Activate it (which in turn creates the actual model field)
        - Link back to this variable and attempt to activate it
        """
        self.ensure_one()

        if self.source_type != "field":
            raise ValidationError(_("This action is only available for Model Field type variables."))

        if self.field_exists == "exists":
            raise ValidationError(
                _("Field '%s' already exists on '%s'.")
                % (
                    self.source_field,
                    self.source_model,
                )
            )

        # Check if Studio Fields feature is available
        if "spp.studio.field" not in self.env or "spp.studio.field.builder.wizard" not in self.env:
            raise ValidationError(
                _("The Custom Fields feature is not available. " "Please ensure spp_studio is properly installed.")
            )

        # Determine target registry from variable scope
        target_type = "individual"
        if self.applies_to == "group":
            target_type = "group"

        # Map variable value_type to Studio field type
        field_type_map = {
            "number": "integer",
            "boolean": "boolean",
            "string": "text",
            "date": "date",
            "money": "decimal",
            "list": "multi_select",
        }
        field_type = field_type_map.get(self.value_type, "text")

        # Determine placement: explicit preference or heuristic default
        placement_code = self.placement_zone_code or self._guess_default_placement()

        # Open field builder wizard with pre-filled values
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Field: %s") % (self.label or self.name),
            "res_model": "spp.studio.field.builder.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_label": self.label or self.name.replace("_", " ").title(),
                "default_target_type": target_type,
                "default_field_type": field_type,
                "default_help_text": self.description or "",
                "default_placement_zone_code": placement_code,
                # Link back so StudioField can update and activate this variable
                "from_logic_variable_id": self.id,
            },
        }

    def action_remap_field(self):
        """Open field selection dialog to remap to an existing field.

        This allows users to:
        1. Map a 'field' type variable to a different field name
        2. Switch a 'computed' or 'aggregate' variable to use an existing field instead

        Returns:
            dict: Action to open field selection wizard
        """
        self.ensure_one()

        # Allow remapping for field, computed, and aggregate types
        allowed_types = ("field", "computed", "aggregate")
        if self.source_type not in allowed_types:
            raise ValidationError(
                _("This action is available for Model Field, Computed, and Aggregate type variables.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Map to Field: %s") % (self.label or self.name),
            "res_model": "spp.studio.variable.remap.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_variable_id": self.id,
            },
        }

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def _upsert_variable(self, vals):
        """Create or update variable by name.

        This is used by the sync process to create/update variables idempotently.

        Args:
            vals (dict): Variable field values

        Returns:
            recordset: Created or updated variable record
        """
        if not vals.get("name"):
            _logger.warning("Cannot upsert variable without name: %s", vals)
            return self.browse()

        # Check if variable already exists
        variable = self.search([("name", "=", vals["name"])], limit=1)

        if variable:
            # Update existing variable (but preserve user changes)
            update_vals = {}
            # Only update system variables automatically
            if variable.is_system:
                # Update fields that should be kept in sync
                for key in [
                    "label",
                    "description",
                    "category_id",
                    "value_type",
                    "source_type",
                    "cel_accessor",
                    "is_system",
                ]:
                    if key in vals:
                        update_vals[key] = vals[key]

                # Update source references
                # Note: source_scoring_id only exists when spp_studio_scoring bridge is installed
                source_fields = [
                    "source_model",
                    "source_field",
                    "source_concept_id",
                    "external_provider_id",
                ]
                if hasattr(self, "source_scoring_id"):
                    source_fields.append("source_scoring_id")
                for key in source_fields:
                    if key in vals:
                        update_vals[key] = vals[key]

                if update_vals:
                    variable.write(update_vals)
                    _logger.debug("Updated system variable: %s", vals["name"])
            else:
                _logger.debug("Skipping update of user-created variable: %s", vals["name"])
        else:
            # Create new variable
            variable = self.create(vals)
            _logger.info("Created new variable: %s", vals["name"])

        return variable

    @api.model
    def _cleanup_legacy_income_variable(self):
        """Migration helper to remove legacy 'income' variable.

        Earlier versions defined a single field-based variable:
            - name: income
            - cel_accessor: income
            - source_type: field
            - applies_to: group

        We now provide context-aware implementations (individual + group)
        and need to avoid duplicate CEL accessors during upgrade on
        existing databases. This method removes the legacy record so the
        new standard variables can be created cleanly.
        """
        legacy_domain = [
            ("name", "=", "income"),
            ("cel_accessor", "=", "income"),
            ("source_type", "=", "field"),
            ("is_system", "=", True),
        ]
        legacy_vars = self.search(legacy_domain)
        if legacy_vars:
            # Deactivate first to avoid studio_mixin preventing deletion
            active_legacy = legacy_vars.filtered(lambda r: getattr(r, "state", False) == "active")
            if active_legacy:
                active_legacy.write({"state": "inactive"})
            _logger.info(
                "Removing legacy 'income' logic variable(s) for migration: %s",
                legacy_vars.ids,
            )
            legacy_vars.unlink()

    # ═══════════════════════════════════════════════════════════════════════
    # REAL-TIME VARIABLE DISCOVERY
    # ═══════════════════════════════════════════════════════════════════════

    # Allowlist of res.partner fields to expose as variables
    _ALLOWED_PARTNER_FIELDS = [
        "name",
        "birthdate",
        "age",
        "gender",
        "marital_status",
        "income",
        "phone",
        "email",
        "is_group",
        "is_registrant",
        "registration_date",
        "address",
        "city",
        "state_id",
        "country_id",
        "zip",
    ]

    @api.model
    def get_all_variables(self, context_type=None):
        """Get all available variables from all sources at runtime.

        Discovers variables directly from sources instead of relying on
        synced records. This eliminates the need for manual sync.

        Sources:
        1. res.partner fields (allowlist + x_* custom fields)
        2. spp.vocabulary.concept.group with cel_function
        3. spp.scoring.model (active)
        4. User-defined variables (computed, constant, aggregate)

        User customizations (label, description overrides) are applied
        to discovered variables.

        Args:
            context_type (str, optional): Filter by 'individual', 'group',
                or None for all

        Returns:
            list: Variable dicts in format expected by VariablePicker
        """
        variables = {}

        # Get category lookup for discovered variables
        categories = self._get_discovery_categories()

        # Discover from each source
        self._discover_field_variables(variables, categories)
        self._discover_vocabulary_variables(variables, categories)
        self._discover_scoring_variables(variables, categories)

        # Single query to get all DB variables, then process them
        all_db_vars = self.search([("active", "=", True)])
        self._add_user_defined_variables(variables, all_db_vars)
        self._apply_user_customizations(variables, all_db_vars)

        # Convert to list and apply filters
        result = list(variables.values())

        # Filter by context_type if specified
        if context_type:
            result = [v for v in result if v.get("applies_to") in (context_type, "both")]

        # Sort by category_id, sequence, name
        result.sort(
            key=lambda v: (
                v.get("category_id", [0, ""])[0] if v.get("category_id") else 0,
                v.get("sequence", 10),
                v.get("name", ""),
            )
        )

        return result

    @api.model
    def _get_discovery_categories(self):
        """Get or create categories for discovered variables.

        Returns:
            dict: Map of category code to (id, name) tuple
        """
        Category = self.env["spp.cel.variable.category"]
        categories = {}

        # Demographics for field variables
        demo_cat = Category._get_or_create("demographics", "Demographics", icon="fa-user")
        categories["demographics"] = (demo_cat.id, demo_cat.name)

        # Characteristics for vocabulary variables
        char_cat = Category._get_or_create("characteristics", "Characteristics", icon="fa-tags")
        categories["characteristics"] = (char_cat.id, char_cat.name)

        # Scoring for scoring model variables
        score_cat = Category._get_or_create("scoring", "Scoring", icon="fa-calculator")
        categories["scoring"] = (score_cat.id, score_cat.name)

        return categories

    @api.model
    def _discover_field_variables(self, variables, categories):
        """Discover variables from res.partner fields.

        Args:
            variables (dict): Dict to populate, keyed by cel_accessor
            categories (dict): Category lookup
        """
        Partner = self.env["res.partner"]
        partner_fields = Partner.fields_get()
        category_id = categories.get("demographics")

        for field_name, field_info in partner_fields.items():
            # Skip if not in allowlist and not a custom field (x_* prefix)
            if field_name not in self._ALLOWED_PARTNER_FIELDS and not field_name.startswith("x_"):
                continue

            # Skip technical field types
            if field_info.get("type") in ["one2many", "many2many", "binary"]:
                continue

            # Map Odoo field type to variable value type
            value_type = self._map_field_type_to_variable(field_info.get("type"))

            # Prepare variable dict
            label = field_info.get("string") or field_name.replace("_", " ").title()
            description = field_info.get("help") or f"Field: {field_name} from res.partner"

            # Generate stable negative ID for virtual variable
            # Note: Apply negation after modulo to ensure negative result
            virtual_id = -(abs(hash(f"field_{field_name}")) % (10**9))

            variables[field_name] = {
                "id": virtual_id,
                "name": field_name,
                "label": label,
                "description": description,
                "category_id": category_id,
                "value_type": value_type,
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": field_name,
                "cel_accessor": field_name,
                "data_source": "local",
                "applies_to": "both",
                "is_system": True,
                "is_virtual": True,
                "sequence": 10,
            }

    @api.model
    def _discover_vocabulary_variables(self, variables, categories):
        """Discover variables from vocabulary concept groups.

        Args:
            variables (dict): Dict to populate, keyed by cel_accessor
            categories (dict): Category lookup
        """
        # Check if vocabulary module is installed
        if "spp.vocabulary.concept.group" not in self.env:
            return

        ConceptGroup = self.env["spp.vocabulary.concept.group"]
        category_id = categories.get("characteristics")

        for group in ConceptGroup.search([("cel_function", "!=", False)]):
            cel_accessor = group.cel_function
            label = group.label or group.name
            description = group.description or f"True if registrant belongs to: {group.name}"

            # Generate stable negative ID for virtual variable
            # Note: Apply negation after modulo to ensure negative result
            virtual_id = -(abs(hash(f"vocabulary_{cel_accessor}")) % (10**9))

            variables[cel_accessor] = {
                "id": virtual_id,
                "name": cel_accessor,
                "label": label,
                "description": description,
                "category_id": category_id,
                "value_type": "boolean",
                "source_type": "vocabulary",
                "source_concept_id": group.id,
                "cel_accessor": cel_accessor,
                "data_source": "local",
                "applies_to": "both",
                "is_system": True,
                "is_virtual": True,
                "sequence": 10,
            }

    @api.model
    def _discover_scoring_variables(self, variables, categories):
        """Discover variables from active scoring models.

        Args:
            variables (dict): Dict to populate, keyed by cel_accessor
            categories (dict): Category lookup
        """
        # Check if scoring module is installed
        if "spp.scoring.model" not in self.env:
            return

        ScoringModel = self.env["spp.scoring.model"]
        category_id = categories.get("scoring")

        # Check if source_scoring_id field exists (from spp_studio_scoring bridge)
        has_scoring_field = "source_scoring_id" in self._fields

        for model in ScoringModel.search([("is_active", "=", True)]):
            # Score variable
            score_accessor = f'score("{model.code}")'
            score_name = f"{model.code}_score"
            # Note: Apply negation after modulo to ensure negative result
            virtual_id_score = -(abs(hash(f"scoring_{score_name}")) % (10**9))

            score_var = {
                "id": virtual_id_score,
                "name": score_name,
                "label": f"{model.name} - Score",
                "description": f"Numeric score from {model.name}",
                "category_id": category_id,
                "value_type": "number",
                "source_type": "scoring",
                "cel_accessor": score_accessor,
                "data_source": "computed",
                "applies_to": "individual",
                "is_system": True,
                "is_virtual": True,
                "sequence": 10,
            }
            if has_scoring_field:
                score_var["source_scoring_id"] = model.id
            variables[score_accessor] = score_var

            # Classification variable
            class_accessor = f'classification("{model.code}")'
            class_name = f"{model.code}_classification"
            # Note: Apply negation after modulo to ensure negative result
            virtual_id_class = -(abs(hash(f"scoring_{class_name}")) % (10**9))

            class_var = {
                "id": virtual_id_class,
                "name": class_name,
                "label": f"{model.name} - Classification",
                "description": f"Classification label from {model.name}",
                "category_id": category_id,
                "value_type": "string",
                "source_type": "scoring",
                "cel_accessor": class_accessor,
                "data_source": "computed",
                "applies_to": "individual",
                "is_system": True,
                "is_virtual": True,
                "sequence": 10,
            }
            if has_scoring_field:
                class_var["source_scoring_id"] = model.id
            variables[class_accessor] = class_var

    @api.model
    def _add_user_defined_variables(self, variables, all_db_vars):
        """Add user-defined variables from database.

        User-defined variables are those with source_type in
        (computed, constant, aggregate) or is_system=False.

        Args:
            variables (dict): Dict to populate, keyed by cel_accessor
            all_db_vars (recordset): Pre-fetched database variables
        """
        # Filter for user-defined: computed, constant, aggregate, or not system
        user_vars = all_db_vars.filtered(
            lambda v: not v.is_system or v.source_type in ["computed", "constant", "aggregate"]
        )

        for var in user_vars:
            # Use cel_accessor as key, real variables override virtual ones
            key = var.cel_accessor or var.name
            variables[key] = {
                "id": var.id,
                "name": var.name,
                "label": var.label or var.name,
                "description": var.description or "",
                "category_id": (var.category_id.id, var.category_id.name) if var.category_id else False,
                "value_type": var.value_type,
                "source_type": var.source_type,
                "cel_accessor": var.cel_accessor,
                "data_source": var.data_source,
                "applies_to": var.applies_to,
                "is_system": var.is_system,
                "is_virtual": False,
                "sequence": var.sequence,
                "synonyms": var.synonyms or "",
            }

    @api.model
    def _apply_user_customizations(self, variables, all_db_vars):
        """Apply user customizations to discovered variables.

        Users can create spp.cel.variable records with is_system=True
        to customize labels, descriptions, categories for discovered
        variables.

        Args:
            variables (dict): Dict to update with customizations
            all_db_vars (recordset): Pre-fetched database variables
        """
        # Filter for system variables that match discovered ones
        system_vars = all_db_vars.filtered(lambda v: v.is_system)

        for var in system_vars:
            key = var.cel_accessor or var.name
            if key in variables and variables[key].get("is_virtual"):
                # Apply customizations from database record
                if var.label:
                    variables[key]["label"] = var.label
                if var.description:
                    variables[key]["description"] = var.description
                if var.category_id:
                    variables[key]["category_id"] = (
                        var.category_id.id,
                        var.category_id.name,
                    )
                if var.synonyms:
                    variables[key]["synonyms"] = var.synonyms
                # Use real ID if customization exists
                variables[key]["id"] = var.id
                variables[key]["is_virtual"] = False

    @staticmethod
    def _map_field_type_to_variable(odoo_type):
        """Map Odoo field type to variable value type.

        Args:
            odoo_type (str): Odoo field type

        Returns:
            str: Variable value type
        """
        type_mapping = {
            "integer": "number",
            "float": "number",
            "monetary": "money",
            "boolean": "boolean",
            "char": "string",
            "text": "string",
            "html": "string",
            "date": "date",
            "datetime": "date",
            "selection": "string",
            "many2one": "string",
        }
        return type_mapping.get(odoo_type, "string")
