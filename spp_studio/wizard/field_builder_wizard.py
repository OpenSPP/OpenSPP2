"""Field builder wizard for creating custom registry fields."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StudioFieldBuilderWizard(models.TransientModel):
    """Three-step wizard for creating custom registry fields.

    Step 1: Basic Info - target registry, field type, label
    Step 2: Configuration - type-specific options, placement zone
    Step 3: Review - summary and create as draft
    """

    _name = "spp.studio.field.builder.wizard"
    _description = "Field Builder Wizard"

    # Field type metadata for visual display
    FIELD_TYPE_METADATA = {
        "text": {
            "icon": "📝",
            "name": "Text",
            "description": "Short text up to 256 characters",
        },
        "long_text": {
            "icon": "📄",
            "name": "Long Text",
            "description": "Multi-line text area",
        },
        "integer": {
            "icon": "🔢",
            "name": "Whole Number",
            "description": "Integer value (1, 2, 3...)",
        },
        "decimal": {
            "icon": "💯",
            "name": "Decimal Number",
            "description": "Number with decimals",
        },
        "date": {
            "icon": "📅",
            "name": "Date",
            "description": "Calendar date picker",
        },
        "datetime": {
            "icon": "🕐",
            "name": "Date & Time",
            "description": "Date with time picker",
        },
        "boolean": {
            "icon": "✓",
            "name": "Yes/No",
            "description": "Checkbox (true/false)",
        },
        "selection": {
            "icon": "📋",
            "name": "Dropdown",
            "description": "Single choice from list",
        },
        "multi_select": {
            "icon": "☑",
            "name": "Multi-Select",
            "description": "Multiple choices (tags)",
        },
        "link": {
            "icon": "🔗",
            "name": "Link",
            "description": "Link to another record",
        },
    }

    # Wizard state
    step = fields.Selection(
        [
            ("basic", "Basic Info"),
            ("config", "Configuration"),
            ("review", "Review"),
        ],
        string="Step",
        default="basic",
        required=True,
    )

    # Step 1: Basic Info
    target_type = fields.Selection(
        [
            ("individual", "👤 Individual Registry"),
            ("group", "👥 Group Registry"),
        ],
        string="Target Registry",
        required=True,
        default="individual",
        help="Choose whether this field applies to Individual beneficiaries, Household groups, or both",
    )
    field_type = fields.Selection(
        [
            ("text", "Text - Short text up to 256 characters"),
            ("long_text", "Long Text - Multi-line text area"),
            ("integer", "Whole Number - Integer value (1, 2, 3...)"),
            ("decimal", "Decimal Number - Number with decimals"),
            ("date", "Date - Calendar date picker"),
            ("datetime", "Date & Time - Date with time picker"),
            ("boolean", "Yes/No - Checkbox (true/false)"),
            ("selection", "Dropdown - Single choice from list"),
            ("multi_select", "Multi-Select - Multiple choices (tags)"),
            ("link", "Link - Link to another record"),
        ],
        string="Field Type",
        required=True,
        default="text",
        help="Choose the type of information you want to collect",
    )
    label = fields.Char(
        string="Field Label",
        help="The label users will see for this field",
    )
    help_text = fields.Text(
        string="Help Text",
        help="Optional tooltip shown when hovering over the field",
    )

    # Step 2: Configuration
    placement_zone_id = fields.Many2one(
        "spp.studio.placement.zone",
        string="Placement Zone",
        domain="[('target_type', 'in', [target_type, 'both'])]",
        help="Where this field will appear on the registration form",
    )
    is_required = fields.Boolean(
        string="Required",
        default=False,
        help="If checked, users must fill in this field when creating or editing a record",
    )
    is_searchable = fields.Boolean(
        string="Searchable",
        default=False,
        help="If checked, this field will appear in search filters and be searchable",
    )

    # Selection field options
    selection_options = fields.Text(
        string="Options",
        help="One option per line. Format: value|Label (or just Label)",
    )

    # Link field options
    link_model_id = fields.Many2one(
        "ir.model",
        string="Link to",
        domain=[("transient", "=", False)],
        help="Select the type of record to link to",
    )
    link_domain = fields.Char(
        string="Filter",
        default="[]",
        help="Optional domain to filter available records",
    )

    # Conditional visibility
    visibility_condition = fields.Selection(
        [
            ("always", "Always Visible"),
            ("conditional", "Show Conditionally"),
        ],
        string="Visibility",
        default="always",
        help="Control when this field should be shown or hidden based on other field values",
    )
    visibility_field_id = fields.Many2one(
        "ir.model.fields",
        string="Show when field",
        domain="[('model', '=', 'res.partner')]",
        help="Select the field that controls visibility of this field",
    )
    visibility_operator = fields.Selection(
        [
            ("set", "Is Set"),
            ("not_set", "Is Not Set"),
            ("equals", "Equals"),
            ("not_equals", "Does Not Equal"),
        ],
        string="Condition",
        default="set",
        help="Condition to check on the controlling field",
    )
    visibility_value = fields.Char(
        string="Value",
        help="Value to compare against (for Equals/Not Equals conditions)",
    )

    # Preview fields (computed for step 3)
    preview_technical_name = fields.Char(
        string="Technical Name",
        compute="_compute_preview",
        help="Auto-generated code used internally. You don't need to change this.",
    )
    preview_odoo_type = fields.Char(
        string="Odoo Field Type",
        compute="_compute_preview",
        help="The underlying Odoo field type that will be created",
    )

    # Computed field for grouping placement zones by tab
    placement_zones_grouped = fields.Text(
        string="Placement Zones Grouped",
        compute="_compute_placement_zones_grouped",
        help="JSON structure of zones grouped by tab",
    )

    # Review step options
    create_as_draft = fields.Boolean(
        string="Create as Draft (do not activate yet)",
        default=False,
        help=(
            "If enabled, the custom field will be created as Draft only. "
            "You will need to activate it later from the Custom Fields screen."
        ),
    )

    @api.model
    def default_get(self, fields_list):
        """Apply default placement from context when provided.

        Logic Studio can pass `default_placement_zone_code` in context
        (based on the variable's preferred placement). Use it to prefill
        placement_zone_id if not already set.
        """
        res = super().default_get(fields_list)

        code = self.env.context.get("default_placement_zone_code")
        if code and "placement_zone_id" in fields_list and not res.get("placement_zone_id"):
            Zone = self.env["spp.studio.placement.zone"]
            zone = Zone.search([("code", "=", code)], limit=1)
            if zone:
                res["placement_zone_id"] = zone.id

        return res

    @api.depends("label", "field_type")
    def _compute_preview(self):
        field_type_map = {
            "text": "Char",
            "long_text": "Text",
            "integer": "Integer",
            "decimal": "Float",
            "date": "Date",
            "datetime": "Datetime",
            "boolean": "Boolean",
            "selection": "Selection",
            "multi_select": "Char (with tags widget)",
            "link": "Many2one",
        }
        for wizard in self:
            if wizard.label:
                # Generate technical name preview
                import re

                name = re.sub(r"[^a-z0-9]+", "_", wizard.label.lower())
                name = re.sub(r"_+", "_", name).strip("_")
                wizard.preview_technical_name = f"x_{name}"
            else:
                wizard.preview_technical_name = ""
            wizard.preview_odoo_type = field_type_map.get(wizard.field_type, "Char")

    @api.depends("target_type")
    def _compute_placement_zones_grouped(self):
        """Group placement zones by tab for visual display."""
        import json

        for wizard in self:
            if not wizard.target_type:
                wizard.placement_zones_grouped = "{}"
                continue

            # Get zones for this target type
            zones = self.env["spp.studio.placement.zone"].search(
                [
                    "|",
                    ("target_type", "=", wizard.target_type),
                    ("target_type", "=", "both"),
                ],
                order="tab_sequence, sequence",
            )

            # Group by tab
            grouped = {}
            for zone in zones:
                tab_name = zone.tab_name
                if tab_name not in grouped:
                    grouped[tab_name] = []
                grouped[tab_name].append(
                    {
                        "id": zone.id,
                        "name": zone.name,
                        "description": zone.description or "",
                    }
                )

            wizard.placement_zones_grouped = json.dumps(grouped)

    @api.constrains("field_type", "selection_options")
    def _check_selection_options(self):
        for wizard in self:
            if wizard.step == "config" and wizard.field_type in (
                "selection",
                "multi_select",
            ):
                if not wizard.selection_options:
                    raise ValidationError(_("Please provide at least one option for selection fields."))

    @api.constrains("field_type", "link_model_id")
    def _check_link_model(self):
        for wizard in self:
            if wizard.step == "config" and wizard.field_type == "link":
                if not wizard.link_model_id:
                    raise ValidationError(_("Please select a model to link to for link fields."))

    def action_next(self):
        """Move to the next step."""
        self.ensure_one()
        if self.step == "basic":
            if not self.label:
                raise ValidationError(_("Please enter a field label."))
            self.step = "config"
        elif self.step == "config":
            # Validate configuration
            if not self.placement_zone_id:
                raise ValidationError(_("Please select where to place the field."))
            if self.field_type in ("selection", "multi_select"):
                if not self.selection_options:
                    raise ValidationError(_("Please provide options for the selection field."))
            if self.field_type == "link" and not self.link_model_id:
                raise ValidationError(_("Please select a model to link to."))
            self.step = "review"

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_previous(self):
        """Move to the previous step."""
        self.ensure_one()
        if self.step == "config":
            self.step = "basic"
        elif self.step == "review":
            self.step = "config"

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_create_field(self):
        """Create the Studio field, optionally activate it, and finish the wizard.

        Default behaviour:
        - Create the field and activate it immediately (usable right away)

        If `create_as_draft` is enabled:
        - Create the field as Draft and open it in the Custom Field form
          for further editing and manual activation.
        """
        self.ensure_one()

        vals = {
            "label": self.label,
            "help_text": self.help_text,
            "target_type": self.target_type,
            "field_type": self.field_type,
            "placement_zone_id": self.placement_zone_id.id,
            "is_required": self.is_required,
            "is_searchable": self.is_searchable,
            "visibility_condition": self.visibility_condition,
            "state": "draft",
        }

        # Add type-specific options
        if self.field_type in ("selection", "multi_select"):
            vals["selection_options"] = self.selection_options

        if self.field_type == "link":
            vals["link_model_id"] = self.link_model_id.id
            vals["link_domain"] = self.link_domain

        if self.visibility_condition == "conditional":
            vals["visibility_field_id"] = self.visibility_field_id.id
            vals["visibility_operator"] = self.visibility_operator
            vals["visibility_value"] = self.visibility_value

        # Create the Studio field record
        field = self.env["spp.studio.field"].create(vals)

        if self.create_as_draft:
            # Leave as draft and open the field form for advanced editing
            return {
                "type": "ir.actions.act_window",
                "name": _("Custom Field Draft"),
                "res_model": "spp.studio.field",
                "res_id": field.id,
                "view_mode": "form",
                "target": "current",
            }

        # Default path: activate immediately so the actual model field and view extension exist
        field.action_activate()

        # Close the wizard popup; caller (e.g. Logic Studio) will refresh as needed
        return {"type": "ir.actions.act_window_close"}
