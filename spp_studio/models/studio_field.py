"""Studio Field model for tracking custom fields created via Studio."""

import json
import logging
import re

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Mapping from Studio field types to Odoo field types
FIELD_TYPE_MAPPING = {
    "text": "char",
    "long_text": "text",
    "integer": "integer",
    "decimal": "float",
    "date": "date",
    "datetime": "datetime",
    "boolean": "boolean",
    "selection": "selection",
    "multi_select": "text",  # Stored as JSON array
    "link": "many2one",
}


class StudioField(models.Model):
    """Custom field definition created via Studio.

    This model tracks fields created through the Studio interface and
    manages their lifecycle (draft/active/inactive).
    """

    _name = "spp.studio.field"
    _description = "Studio Custom Field"
    _inherit = ["spp.studio.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "target_type, placement_zone_id, sequence, id"
    _rec_name = "label"

    # Field identification
    label = fields.Char(
        string="Label",
        required=True,
        translate=True,
        help="Display label shown to users",
    )
    technical_name = fields.Char(
        string="Technical Name",
        readonly=True,
        copy=False,
        help="Auto-generated field name (x_*)",
    )
    help_text = fields.Text(
        string="Help Text",
        translate=True,
        help="Tooltip shown when hovering over the field",
    )

    # Target configuration
    target_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
        ],
        string="Target Registry",
        required=True,
        default="individual",
    )
    target_model = fields.Char(
        string="Target Model",
        compute="_compute_target_model",
        store=True,
    )

    # Placement
    placement_zone_id = fields.Many2one(
        "spp.studio.placement.zone",
        string="Placement Zone",
        required=True,
        domain="[('target_type', 'in', [target_type, 'both'])]",
        help="Where the field will appear in the form",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order within the placement zone",
    )

    # Field type configuration
    field_type = fields.Selection(
        [
            ("text", "Text"),
            ("long_text", "Long Text"),
            ("integer", "Number (whole)"),
            ("decimal", "Number (decimal)"),
            ("date", "Date"),
            ("datetime", "Date & Time"),
            ("boolean", "Yes/No"),
            ("selection", "Selection"),
            ("multi_select", "Multi-Select"),
            ("link", "Link"),
        ],
        string="Field Type",
        required=True,
        default="text",
    )

    # Type-specific options
    selection_options = fields.Text(
        string="Selection Options",
        help="One option per line, format: value|Label",
    )
    link_model_id = fields.Many2one(
        "ir.model",
        string="Link To",
        domain=[("transient", "=", False)],
        help="Model to link to for 'Link' field type",
    )
    link_domain = fields.Char(
        string="Link Domain",
        default="[]",
        help="Domain to filter available records",
    )

    # Field options
    is_required = fields.Boolean(
        string="Required",
        default=False,
    )
    is_readonly = fields.Boolean(
        string="Read-only",
        default=False,
    )
    is_searchable = fields.Boolean(
        string="Searchable",
        default=False,
        help="Add this field to search filters",
    )

    # Conditional visibility
    visibility_condition = fields.Selection(
        [
            ("always", "Always Visible"),
            ("conditional", "Conditional"),
        ],
        string="Visibility",
        default="always",
    )
    visibility_field_id = fields.Many2one(
        "ir.model.fields",
        string="Show When Field",
        domain="[('model', '=', target_model)]",
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
    )
    visibility_value = fields.Char(
        string="Value",
    )

    # Link to actual Odoo field
    ir_model_fields_id = fields.Many2one(
        "ir.model.fields",
        string="Odoo Field",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    view_inherit_id = fields.Many2one(
        "ir.ui.view",
        string="View Extension",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    @api.depends("target_type")
    def _compute_target_model(self):
        for record in self:
            record.target_model = "res.partner"

    @api.constrains("field_type", "selection_options")
    def _check_selection_options(self):
        for record in self:
            if record.field_type in ("selection", "multi_select"):
                if not record.selection_options:
                    raise ValidationError(_("Selection options are required for selection fields."))

    @api.constrains("field_type", "link_model_id")
    def _check_link_model(self):
        for record in self:
            if record.field_type == "link" and not record.link_model_id:
                raise ValidationError(_("Link model is required for link fields."))

    @api.model_create_multi
    def create(self, vals_list):
        """Generate technical name on create."""
        for vals in vals_list:
            if not vals.get("technical_name") and vals.get("label"):
                vals["technical_name"] = self._generate_technical_name(vals["label"])
        return super().create(vals_list)

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

    def write(self, vals):
        """Track changes and prevent editing active fields."""
        for record in self:
            if record.state == "active" and not self.env.context.get("force_write"):
                # Only allow state changes on active records
                allowed_fields = {"state", "deactivated_by_id", "deactivated_date"}
                if set(vals.keys()) - allowed_fields:
                    raise UserError(
                        _(
                            "Cannot modify active field '%(name)s'. Deactivate it first to make changes.",
                            name=record.label,
                        )
                    )
        return super().write(vals)

    @api.model
    def _generate_technical_name(self, label):
        """Generate a technical field name from the label."""
        # Convert to lowercase, replace spaces/special chars with underscore
        name = re.sub(r"[^a-z0-9]+", "_", label.lower())
        name = re.sub(r"_+", "_", name).strip("_")
        # Ensure uniqueness against both ir.model.fields and spp.studio.field
        base_name = f"x_{name}"
        final_name = base_name
        counter = 1
        while self.env["ir.model.fields"].search(
            [("name", "=", final_name), ("model", "=", "res.partner")], limit=1
        ) or self.search([("technical_name", "=", final_name)], limit=1):
            final_name = f"{base_name}_{counter}"
            counter += 1
        return final_name

    def _pre_activate(self):
        """Create the actual Odoo field when activating."""
        self.ensure_one()
        if self.ir_model_fields_id:
            return  # Field already exists

        # Create the field
        field_vals = self._prepare_ir_model_field_vals()
        ir_field = self.env["ir.model.fields"].sudo().create(field_vals)
        self.with_context(force_write=True).ir_model_fields_id = ir_field.id

        # Create view extension
        view_vals = self._prepare_view_extension_vals()
        if view_vals:
            view = self.env["ir.ui.view"].sudo().create(view_vals)
            self.with_context(force_write=True).view_inherit_id = view.id

        # If this field was created from a Logic Variable flow, update the variable
        # to point to the correct technical field name so Studio Logic sees it
        # and, if possible, activate the variable automatically.
        logic_var_id = self.env.context.get("from_logic_variable_id")
        if logic_var_id and "spp.cel.variable" in self.env:
            Variable = self.env["spp.cel.variable"].sudo()
            variable = Variable.browse(logic_var_id)
            if variable and variable.exists():
                update_vals = {
                    "source_field": self.technical_name,
                }
                if not variable.source_model:
                    update_vals["source_model"] = "res.partner"
                variable.with_context(force_write=True).write(update_vals)
                # Try to activate the variable now that the field exists
                try:
                    if hasattr(variable, "action_activate") and variable.state != "active":
                        variable.action_activate()
                except Exception as e:
                    # Don't block field activation if variable activation fails;
                    # errors will be surfaced when the user activates the variable manually.
                    _logger.warning(
                        "Failed to auto-activate logic variable %s after field '%s' activation: %s",
                        variable.name,
                        self.technical_name,
                        e,
                    )

        _logger.info(
            "Studio field '%s' activated: created field %s on %s",
            self.label,
            self.technical_name,
            self.target_model,
        )

    def _post_deactivate(self):
        """Optionally hide or remove the field when deactivating."""
        # For now, we keep the field but mark it as invisible via view
        # Full deletion would require data migration considerations
        if self.view_inherit_id:
            # Update view to make field invisible
            self.view_inherit_id.sudo().write({"active": False})

    def _get_deactivation_impact(self):
        """Check if the field has data before deactivating."""
        if not self.ir_model_fields_id:
            return None

        # Count records with non-empty values
        try:
            count = self.env["res.partner"].search_count([(self.technical_name, "!=", False)])
            if count > 0:
                return _(
                    "This field contains data in %(count)d records. "
                    "Deactivating will hide the field but preserve the data.",
                    count=count,
                )
        except Exception as e:
            _logger.warning(
                "Could not check deactivation impact for field '%s': %s",
                self.technical_name,
                e,
            )
        return None

    def _prepare_ir_model_field_vals(self):
        """Prepare values for creating ir.model.fields record."""
        vals = {
            "name": self.technical_name,
            "field_description": self.label,
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "ttype": FIELD_TYPE_MAPPING.get(self.field_type, "char"),
            "help": self.help_text or "",
            "required": self.is_required,
            "readonly": self.is_readonly,
            "index": self.is_searchable,
            "copied": False,
            "state": "manual",
        }

        # Handle selection options
        if self.field_type in ("selection", "multi_select"):
            selection = self._parse_selection_options()
            vals["selection_ids"] = [
                Command.create({"value": opt[0], "name": opt[1], "sequence": idx * 10})
                for idx, opt in enumerate(selection)
            ]

        # Handle link field
        if self.field_type == "link":
            vals["relation"] = self.link_model_id.model
            vals["domain"] = self.link_domain or "[]"

        return vals

    def _parse_selection_options(self):
        """Parse selection options from text format."""
        if not self.selection_options:
            return []
        options = []
        for line in self.selection_options.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                value, label = line.split("|", 1)
                options.append((value.strip(), label.strip()))
            else:
                # Use line as both value and label
                options.append((line, line))
        return options

    def _prepare_view_extension_vals(self):
        """Prepare values for creating view extension."""
        zone = self.placement_zone_id
        if not zone:
            return None

        # Determine base view
        if self.target_type == "individual":
            base_view = self.env.ref("spp_registry.view_individuals_form", raise_if_not_found=False)
        else:
            base_view = self.env.ref("spp_registry.view_groups_form", raise_if_not_found=False)

        if not base_view:
            return None

        # Build field XML and wrap it in a group so it
        # integrates cleanly with existing grid layouts
        invisible_expr = self._build_visibility_expression()

        # Inject as a new group containing the field, which matches
        # how core views structure Demographics/Contact sections.
        arch = f"""<?xml version="1.0"?>
<data>
    <xpath expr="{zone.xpath_expression}" position="{zone.xpath_position}">
        <group>
            <field name="{self.technical_name}"{invisible_expr}/>
        </group>
    </xpath>
</data>"""

        return {
            "name": f"studio.field.{self.technical_name}",
            "model": "res.partner",
            "inherit_id": base_view.id,
            "arch": arch,
            "priority": 100,
        }

    def _build_field_xml(self):
        """Build the field XML element."""
        attrs = [f'name="{self.technical_name}"']

        # Add widget based on field type
        widget_mapping = {
            "long_text": "text",
            "multi_select": "many2many_tags",
            "boolean": "boolean_toggle",
        }
        if self.field_type in widget_mapping:
            attrs.append(f'widget="{widget_mapping[self.field_type]}"')

        return f"<field {' '.join(attrs)}/>"

    def _build_visibility_expression(self):
        """Build invisible attribute for conditional visibility."""
        if self.visibility_condition != "conditional":
            return ""

        if not self.visibility_field_id:
            return ""

        field_name = self.visibility_field_id.name
        if self.visibility_operator == "set":
            expr = f"not {field_name}"
        elif self.visibility_operator == "not_set":
            expr = field_name
        elif self.visibility_operator == "equals":
            # Use json.dumps to properly escape quotes and special characters
            expr = f"{field_name} != {json.dumps(self.visibility_value)}"
        elif self.visibility_operator == "not_equals":
            expr = f"{field_name} == {json.dumps(self.visibility_value)}"
        else:
            return ""

        return f' invisible="{expr}"'

    @api.model
    def _get_studio_config_type(self):
        return _("Registry Field")

    def action_bulk_activate(self):
        """Bulk activate multiple draft fields."""
        draft_fields = self.filtered(lambda f: f.state == "draft")
        if not draft_fields:
            raise UserError(_("No draft fields selected for activation."))

        activated_count = 0
        errors = []
        for field in draft_fields:
            try:
                field.action_activate()
                activated_count += 1
            except Exception as e:
                errors.append(f"{field.label}: {e}")

        if errors:
            raise UserError(
                _(
                    "Activated %(count)d field(s). Errors:\n%(errors)s",
                    count=activated_count,
                    errors="\n".join(errors),
                )
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Activation"),
                "message": _("Successfully activated %d field(s).") % activated_count,
                "type": "success",
                "sticky": False,
            },
        }

    def action_bulk_deactivate(self):
        """Bulk deactivate multiple active fields."""
        active_fields = self.filtered(lambda f: f.state == "active")
        if not active_fields:
            raise UserError(_("No active fields selected for deactivation."))

        deactivated_count = 0
        errors = []
        for field in active_fields:
            try:
                field.action_deactivate()
                deactivated_count += 1
            except Exception as e:
                errors.append(f"{field.label}: {e}")

        if errors:
            raise UserError(
                _(
                    "Deactivated %(count)d field(s). Errors:\n%(errors)s",
                    count=deactivated_count,
                    errors="\n".join(errors),
                )
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Deactivation"),
                "message": _("Successfully deactivated %d field(s).") % deactivated_count,
                "type": "warning",
                "sticky": False,
            },
        }
