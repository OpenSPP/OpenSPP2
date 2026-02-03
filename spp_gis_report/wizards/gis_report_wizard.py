"""GIS Report Creation Wizard.

Three-step wizard for creating GIS reports from templates:
- Step 1: Template Selection - Choose a pre-built template
- Step 2: Configuration - Configure report parameters
- Step 3: Thresholds - Set color thresholds and refresh schedule
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class GISReportWizard(models.TransientModel):
    """Wizard to create a GIS report from a template."""

    _name = "spp.gis.report.wizard"
    _description = "GIS Report Creation Wizard"

    # ===== Wizard State =====
    step = fields.Selection(
        [
            ("template", "Template Selection"),
            ("config", "Configuration"),
            ("thresholds", "Thresholds"),
        ],
        string="Step",
        default="template",
        required=True,
    )

    # ===== Step 1: Template Selection =====
    template_id = fields.Many2one(
        "spp.gis.report.template",
        string="Template",
        domain=[("active", "=", True)],
        help="Select a pre-built report template",
    )

    # Template info (for display)
    template_name = fields.Char(
        related="template_id.name",
        readonly=True,
    )
    template_description = fields.Text(
        related="template_id.description",
        readonly=True,
    )
    template_category_id = fields.Many2one(
        related="template_id.category_id",
        readonly=True,
    )

    # Template requirements
    template_requires_program = fields.Boolean(
        related="template_id.requires_program",
        readonly=True,
    )
    template_requires_incident = fields.Boolean(
        related="template_id.requires_incident",
        readonly=True,
    )

    # ===== Step 2: Configuration =====
    name = fields.Char(
        string="Report Name",
        help="Name for this report",
    )
    description = fields.Text(
        string="Description",
        help="Optional description of the report",
    )

    # Area level
    base_area_level = fields.Integer(
        string="Administrative Level",
        required=True,
        default=2,
        help="Level at which to calculate base values (e.g., 2=District)",
    )

    # Normalization
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
        string="Display Values As",
        default="raw",
        required=True,
        help="How to normalize the aggregated values",
    )

    # Disaggregation options
    disaggregate_by_gender = fields.Boolean(
        string="Include Gender Disaggregation",
        default=False,
        help="Show gender breakdown in map popups",
    )
    disaggregate_by_age = fields.Boolean(
        string="Include Age Group Disaggregation",
        default=False,
        help="Show age group breakdown in map popups",
    )

    # Rollup
    enable_rollup = fields.Boolean(
        string="Enable Hierarchy Rollup",
        default=True,
        help="Show totals at region/country level (parent areas)",
    )

    # ===== Step 3: Thresholds =====
    threshold_mode = fields.Selection(
        [
            ("auto_quartile", "Auto: Quartiles (Recommended)"),
            ("auto_equal", "Auto: Equal Intervals"),
            ("manual", "Manual Thresholds"),
        ],
        string="Threshold Mode",
        default="auto_quartile",
        required=True,
        help="How to calculate color thresholds",
    )
    color_scheme_id = fields.Many2one(
        "spp.gis.color.scheme",
        string="Color Scheme",
        default=lambda self: self.env["spp.gis.color.scheme"].get_default_scheme(),
        required=True,
        help="Color scheme for visualizing thresholds",
    )

    # Refresh settings
    refresh_mode = fields.Selection(
        [
            ("manual", "Manual Only"),
            ("scheduled", "Scheduled"),
        ],
        string="Refresh Mode",
        default="scheduled",
        required=True,
        help="When to refresh the report data",
    )
    refresh_interval = fields.Selection(
        [
            ("hourly", "Every Hour"),
            ("daily", "Daily (Overnight)"),
            ("weekly", "Weekly"),
        ],
        string="Refresh Schedule",
        default="daily",
        help="How often to refresh on schedule",
    )

    # ===== Computed/Helper Fields =====
    show_step_1 = fields.Boolean(
        compute="_compute_show_steps",
        help="Whether to show step 1",
    )
    show_step_2 = fields.Boolean(
        compute="_compute_show_steps",
        help="Whether to show step 2",
    )
    show_step_3 = fields.Boolean(
        compute="_compute_show_steps",
        help="Whether to show step 3",
    )

    @api.depends("step")
    def _compute_show_steps(self):
        """Compute which step to show."""
        for wizard in self:
            wizard.show_step_1 = wizard.step == "template"
            wizard.show_step_2 = wizard.step == "config"
            wizard.show_step_3 = wizard.step == "thresholds"

    @api.model
    def default_get(self, fields_list):
        """Apply defaults from context.

        When wizard is opened from a template, the template_id is passed
        in context and we apply the template defaults.
        """
        res = super().default_get(fields_list)

        # If template_id is in context, apply template defaults
        template_id = self.env.context.get("default_template_id")
        if template_id:
            template = self.env["spp.gis.report.template"].browse(template_id)
            if template.exists():
                res.update(self._get_template_defaults(template))

        return res

    def _get_template_defaults(self, template):
        """Extract default values from template configuration.

        Args:
            template: spp.gis.report.template record

        Returns:
            dict: Default field values
        """
        config = template.config or {}
        if isinstance(config, str):
            config = json.loads(config)

        defaults = {
            "template_id": template.id,
            "name": template.name,
            "description": template.description,
        }

        # Extract values from config JSON
        if "base_area_level" in config:
            defaults["base_area_level"] = config["base_area_level"]
        if "normalization_method" in config:
            defaults["normalization_method"] = config["normalization_method"]
        if "color_scheme" in config:
            # Look up color scheme by code from template
            scheme = self.env["spp.gis.color.scheme"].search(
                [("code", "=", config["color_scheme"])], limit=1
            )
            if scheme:
                defaults["color_scheme_id"] = scheme.id
        if "threshold_mode" in config:
            defaults["threshold_mode"] = config["threshold_mode"]
        if "enable_rollup" in config:
            defaults["enable_rollup"] = config["enable_rollup"]

        return defaults

    @api.onchange("template_id")
    def _onchange_template_id(self):
        """When template changes, apply template defaults."""
        if self.template_id:
            defaults = self._get_template_defaults(self.template_id)
            for field, value in defaults.items():
                if hasattr(self, field):
                    setattr(self, field, value)

    def _validate_context_requirements(self):
        """Validate context-specific requirements.

        Override this method in glue modules to add validation for
        context-specific fields like program_id or incident_id.
        """

    def action_next(self):
        """Move to the next step with validation."""
        self.ensure_one()

        if self.step == "template":
            # Validate template selection
            if not self.template_id:
                raise ValidationError(_("Please select a template."))
            self.step = "config"

        elif self.step == "config":
            # Validate configuration
            if not self.name:
                raise ValidationError(_("Please enter a report name."))
            self._validate_context_requirements()
            if not self.base_area_level or self.base_area_level < 0:
                raise ValidationError(
                    _("Please select a valid administrative level.")
                )
            self.step = "thresholds"

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_back(self):
        """Move to the previous step."""
        self.ensure_one()

        if self.step == "thresholds":
            self.step = "config"
        elif self.step == "config":
            self.step = "template"

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_create_report(self):
        """Create the GIS report from wizard configuration.

        Returns:
            dict: Window action to view the created report
        """
        self.ensure_one()

        if not self.template_id:
            raise UserError(_("Please select a template."))

        # Build report values from template config and wizard inputs
        vals = self._prepare_report_vals()

        # Create the report
        report = self.env["spp.gis.report"].create(vals)

        _logger.info(
            "Created GIS report '%s' (ID: %s) from template '%s'",
            report.name,
            report.id,
            self.template_id.name,
        )

        # Return action to view the created report
        return {
            "type": "ir.actions.act_window",
            "name": _("GIS Report"),
            "res_model": "spp.gis.report",
            "res_id": report.id,
            "view_mode": "form",
            "target": "current",
        }

    def _prepare_report_vals(self):
        """Prepare values for creating the spp.gis.report record.

        Combines template configuration with wizard inputs.

        Returns:
            dict: Values for spp.gis.report.create()
        """
        self.ensure_one()

        config = self.template_id.config or {}
        if isinstance(config, str):
            config = json.loads(config)

        # Generate unique code
        code = self._generate_report_code()

        # Base values
        vals = {
            "name": self.name,
            "code": code,
            "description": self.description or self.template_description,
            "category_id": self.template_category_id.id,
            "template_id": self.template_id.id,
            # Configuration from wizard
            "base_area_level": self.base_area_level,
            "normalization_method": self.normalization_method,
            "enable_rollup": self.enable_rollup,
            "disaggregate_by_gender": self.disaggregate_by_gender,
            "disaggregate_by_age": self.disaggregate_by_age,
            # Thresholds
            "threshold_mode": self.threshold_mode,
            "color_scheme_id": self.color_scheme_id.id,
            # Refresh
            "refresh_mode": self.refresh_mode,
            "refresh_interval": self.refresh_interval,
        }

        # Allow glue modules to add context filter values
        vals.update(self._get_context_filter_vals())

        # Extract required fields from template config
        if "source_model" in config:
            # Find ir.model by model name
            model = self.env["ir.model"].search(
                [("model", "=", config["source_model"])], limit=1
            )
            if model:
                vals["source_model_id"] = model.id

        if "area_field_path" in config:
            vals["area_field_path"] = config["area_field_path"]

        if "filter_mode" in config:
            vals["filter_mode"] = config["filter_mode"]
        if "filter_domain" in config:
            vals["filter_domain"] = config["filter_domain"]

        if "aggregation_method" in config:
            vals["aggregation_method"] = config["aggregation_method"]
        if "aggregation_field" in config:
            vals["aggregation_field"] = config["aggregation_field"]

        if "rollup_method" in config:
            vals["rollup_method"] = config["rollup_method"]
        if "rollup_weight_source" in config:
            vals["rollup_weight_source"] = config["rollup_weight_source"]

        return vals

    def _get_context_filter_vals(self):
        """Get context filter values for report creation.

        Override in glue modules to add context filter values like
        program_id or incident_id.

        Returns:
            dict: Context filter field values
        """
        return {}

    def _get_context_code_suffix(self):
        """Get code suffix based on context filters.

        Override in glue modules to add context-specific suffixes
        like program ID or incident ID.

        Returns:
            str: Suffix for report code
        """
        return ""

    def _generate_report_code(self):
        """Generate a unique code for the report.

        Returns:
            str: Unique report code
        """
        self.ensure_one()

        # Start with template code as base
        base_code = self.template_id.code or "report"

        # Add context-specific suffix if applicable
        suffix = self._get_context_code_suffix()

        # Generate unique code
        code = f"{base_code}{suffix}"
        counter = 1

        # Ensure uniqueness
        while self.env["spp.gis.report"].search([("code", "=", code)], limit=1):
            code = f"{base_code}{suffix}_{counter}"
            counter += 1

        return code
