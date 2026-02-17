"""Studio Event Type models for no-code event type creation."""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Mapping from Studio field types to JSON field types
FIELD_TYPE_MAPPING = {
    "text": "string",
    "long_text": "text",
    "integer": "integer",
    "decimal": "number",
    "date": "date",
    "datetime": "datetime",
    "boolean": "boolean",
    "selection": "selection",
    "multi_select": "multi_select",
    "link": "many2one",
}

# Mapping from Studio field types to Odoo field types for ir.model.fields
STUDIO_TO_ODOO_FIELD_TYPE = {
    "text": "char",
    "long_text": "text",
    "integer": "integer",
    "decimal": "float",
    "date": "date",
    "datetime": "datetime",
    "boolean": "boolean",
    "selection": "selection",
    "multi_select": "char",  # Stored as comma-separated
    "link": "many2one",
}

# Mapping from Studio field types to Odoo view widgets
STUDIO_TO_WIDGET = {
    "long_text": None,  # Text widget is default for text fields
    "boolean": "boolean_toggle",
    "selection": "selection",
    "multi_select": None,  # Will use char with placeholder
    "link": None,  # Many2one default widget
}


class StudioEventType(models.Model):
    """Custom event type definition created via Studio.

    This model tracks event types created through the Studio interface and
    manages their lifecycle (draft/active/inactive).
    """

    _name = "spp.studio.event.type"
    _description = "Studio Event Type"
    _inherit = ["spp.studio.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "name, id"
    _rec_name = "name"

    # Basic Info
    name = fields.Char(
        string="Event Type Name",
        required=True,
        translate=True,
        help="Display name for this event type (e.g., 'Health Screening')",
    )
    technical_name = fields.Char(
        string="Technical Name",
        readonly=True,
        copy=False,
        help="Auto-generated code (x_evt_*)",
    )
    description = fields.Text(
        string="Description",
        translate=True,
        help="Describe what this event type is used for",
    )

    # Target Configuration
    target_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
            ("both", "Both"),
        ],
        string="Target Type",
        required=True,
        default="individual",
        help="Who can this event be recorded for?",
    )

    # Field Groups (for organizing fields into tabs)
    field_group_ids = fields.One2many(
        "spp.studio.event.field.group",
        "event_type_id",
        string="Field Groups",
        help="Groups for organizing fields into tabs in the wizard",
    )
    field_group_count = fields.Integer(
        string="Group Count",
        compute="_compute_field_group_count",
    )

    @api.depends("field_group_ids")
    def _compute_field_group_count(self):
        for record in self:
            record.field_group_count = len(record.field_group_ids)

    # Fields
    data_fields = fields.One2many(
        "spp.studio.event.field",
        "event_type_id",
        string="Event Fields",
        help="Custom fields for this event type",
    )
    data_field_count = fields.Integer(
        string="Field Count",
        compute="_compute_data_field_count",
    )

    @api.depends("data_fields")
    def _compute_data_field_count(self):
        for record in self:
            record.data_field_count = len(record.data_fields)

    # Integration Options
    kobo_form_id = fields.Char(
        string="Kobo Form ID",
        help="Optional Kobo form integration reference",
    )
    allow_multiple = fields.Boolean(
        string="Allow Multiple Events",
        default=True,
        help="Allow multiple events of this type per registrant",
    )
    requires_approval = fields.Boolean(
        string="Requires Approval",
        default=False,
        help="Events of this type need approval before becoming active",
    )
    approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Workflow",
        help="Select the approval workflow for events of this type",
    )

    # Link to created spp.event.type record
    spp_event_type_id = fields.Many2one(
        "spp.event.type",
        string="Event Type Record",
        readonly=True,
        copy=False,
        ondelete="set null",
        help="The actual spp.event.type record created when activated",
    )

    # Link to generated wizard view
    wizard_view_id = fields.Many2one(
        "ir.ui.view",
        string="Wizard View",
        readonly=True,
        copy=False,
        ondelete="set null",
        help="Generated wizard form view for this event type",
    )

    # Link to generated wizard fields
    wizard_field_ids = fields.Many2many(
        "ir.model.fields",
        string="Wizard Fields",
        readonly=True,
        copy=False,
        help="Generated wizard fields for this event type",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Generate technical name on create."""
        for vals in vals_list:
            if not vals.get("technical_name") and vals.get("name"):
                vals["technical_name"] = self._generate_technical_name(vals["name"])
        return super().create(vals_list)

    def write(self, vals):
        """Track changes and prevent editing active event types."""
        for record in self:
            if record.state == "active" and not self.env.context.get("force_write"):
                # Only allow state changes on active records
                allowed_fields = {
                    "state",
                    "deactivated_by_id",
                    "deactivated_date",
                }
                if set(vals.keys()) - allowed_fields:
                    raise UserError(
                        _(
                            "Cannot modify active event type '%(name)s'. Deactivate it first to make changes.",
                            name=record.name,
                        )
                    )
        return super().write(vals)

    @api.model
    def _generate_technical_name(self, name):
        """Generate a technical code from the name."""
        # Convert to lowercase, replace spaces/special chars with underscore
        code = re.sub(r"[^a-z0-9]+", "_", name.lower())
        code = re.sub(r"_+", "_", code).strip("_")
        # Ensure uniqueness
        base_code = f"x_evt_{code}"
        final_code = base_code
        counter = 1

        def code_exists(code_to_check):
            """Check if code exists in spp.event.type or spp.studio.event.type."""
            # Check existing spp.event.type codes
            if self.env["spp.event.type"].search([("code", "=", code_to_check)], limit=1):
                return True
            # Check existing studio event type technical names
            if self.search([("technical_name", "=", code_to_check)], limit=1):
                return True
            return False

        while code_exists(final_code):
            final_code = f"{base_code}_{counter}"
            counter += 1
        return final_code

    @api.constrains("data_fields")
    def _check_has_fields(self):
        """Ensure event type has at least one field before activation."""
        for record in self:
            if record.state != "draft" and not record.data_fields:
                raise ValidationError(_("Event type must have at least one field before activation."))

    @api.constrains("requires_approval", "approval_definition_id")
    def _check_approval_config(self):
        """Ensure approval definition is set when approval is required."""
        for record in self:
            if record.requires_approval and not record.approval_definition_id:
                raise ValidationError(_("Please select an approval workflow when approval is required."))

    def _pre_activate(self):
        """Create the actual spp.event.type record when activating."""
        self.ensure_one()

        if not self.data_fields:
            raise UserError(_("Cannot activate event type without fields. Please add at least one field."))

        if self.spp_event_type_id:
            # Reactivation - update existing records
            self.spp_event_type_id.write({"active": True})
            # Regenerate wizard view to reflect any changes made during deactivation
            self._regenerate_wizard_view()
            _logger.info(
                "Studio event type '%s' reactivated with updated wizard view",
                self.name,
            )
            return

        # Create the actual event type
        event_type_vals = self._prepare_event_type_vals()
        event_type = self.env["spp.event.type"].sudo().create(event_type_vals)

        # Store reference
        self.with_context(force_write=True).spp_event_type_id = event_type.id

        # Create event field definitions
        self._create_event_fields(event_type)

        # Generate wizard view for this event type
        self._generate_wizard_view()

        _logger.info(
            "Studio event type '%s' activated: created spp.event.type %s",
            self.name,
            event_type.code,
        )

    def _regenerate_wizard_view(self):
        """Regenerate the wizard view after changes.

        This is called during reactivation to ensure the wizard view
        reflects any changes made to fields or groups while deactivated.
        """
        self.ensure_one()

        # Delete old wizard view if exists
        if self.wizard_view_id:
            self.wizard_view_id.sudo().unlink()

        # Delete old wizard fields (dynamic x_evt_* fields)
        if self.wizard_field_ids:
            self.wizard_field_ids.sudo().unlink()

        # Clear references
        self.with_context(force_write=True).write(
            {
                "wizard_view_id": False,
                "wizard_field_ids": [(5, 0, 0)],
            }
        )

        # Regenerate
        self._generate_wizard_view()

    def _prepare_event_type_vals(self):
        """Prepare values for creating spp.event.type record."""
        vals = {
            "name": self.name,
            "code": self.technical_name,
            "description": self.description or "",
            "target_type": self.target_type,
            "category": "manual",
            "source_type": "internal" if not self.kobo_form_id else "kobo",
            "external_form_id": self.kobo_form_id or False,
            "is_one_active_per_registrant": not self.allow_multiple,
            "is_requires_approval": self.requires_approval,
            "active": True,
        }
        # Add approval definition if configured
        if self.requires_approval and self.approval_definition_id:
            vals["approval_definition_id"] = self.approval_definition_id.id
        return vals

    def _create_event_fields(self, event_type):
        """Create spp.event.field records for each data field."""
        self.ensure_one()
        EventField = self.env["spp.event.field"]

        # Map Studio field types to spp.event.field field types
        studio_to_event_type = {
            "text": "char",
            "long_text": "text",
            "integer": "integer",
            "decimal": "float",
            "date": "date",
            "datetime": "datetime",
            "boolean": "boolean",
            "selection": "selection",
            "multi_select": "selection",  # Store as selection, handle multi in JSON
            "link": "many2one",
        }

        for field in self.data_fields:
            field_vals = {
                "event_type_id": event_type.id,
                "name": field.technical_name,
                "label": field.label,
                "field_type": studio_to_event_type.get(field.field_type, "char"),
                "required": field.is_required,
                "help_text": field.help_text or "",
                "sequence": field.sequence,
            }

            # Handle selection options (for both selection and multi_select)
            if field.field_type in ("selection", "multi_select") and field.selection_options:
                options = field._parse_selection_options()
                field_vals["selection_options"] = "\n".join([f"{opt[0]}|{opt[1]}" for opt in options])

            # Handle link field
            if field.field_type == "link" and field.link_model_id:
                field_vals["relation_model"] = field.link_model_id.model

            EventField.sudo().create(field_vals)

    def _generate_wizard_view(self):
        """Generate a dedicated wizard form view for this event type.

        This method creates:
        1. ir.model.fields records on spp.event.data.entry.wizard for each data field
        2. An ir.ui.view record that uses these fields with proper widgets
        """
        self.ensure_one()

        # First, create the dynamic fields on the wizard model
        created_fields = self._create_wizard_fields()

        # Build the view arch XML
        view_arch = self._build_wizard_view_arch()

        # Create the view record
        view_vals = {
            "name": f"spp.event.data.entry.wizard.form.{self.technical_name}",
            "model": "spp.event.data.entry.wizard",
            "type": "form",
            "priority": 100,  # Higher priority to ensure it's used
            "arch": view_arch,
            "active": True,
        }

        view = self.env["ir.ui.view"].sudo().create(view_vals)
        self.with_context(force_write=True).write(
            {
                "wizard_view_id": view.id,
                "wizard_field_ids": [(6, 0, created_fields.ids)],
            }
        )

        _logger.info(
            "Generated wizard view '%s' with %d fields for event type '%s'",
            view.name,
            len(created_fields),
            self.name,
        )

    def _create_wizard_fields(self):
        """Create ir.model.fields records for this event type's data fields.

        Returns:
            ir.model.fields recordset: The created field records
        """
        self.ensure_one()
        IrModelFields = self.env["ir.model.fields"].sudo()
        wizard_model = self.env["ir.model"].sudo().search([("model", "=", "spp.event.data.entry.wizard")], limit=1)

        if not wizard_model:
            raise UserError(_("Wizard model not found. Please reinstall the module."))

        created_fields = self.env["ir.model.fields"]

        for field_def in self.data_fields.sorted("sequence"):
            field_name = f"x_evt_{field_def.technical_name}"

            # Check if field already exists
            existing = IrModelFields.search(
                [
                    ("model_id", "=", wizard_model.id),
                    ("name", "=", field_name),
                ],
                limit=1,
            )

            if existing:
                created_fields |= existing
                continue

            # Map studio field type to Odoo field type
            ttype = STUDIO_TO_ODOO_FIELD_TYPE.get(field_def.field_type, "char")

            field_vals = {
                "name": field_name,
                "field_description": field_def.label,
                "model_id": wizard_model.id,
                "ttype": ttype,
                "store": True,
                "copied": False,
            }

            # Add help text if present
            if field_def.help_text:
                field_vals["help"] = field_def.help_text

            # Handle selection fields
            if field_def.field_type == "selection" and field_def.selection_options:
                options = field_def._parse_selection_options()
                selection_list = [(opt[0], opt[1]) for opt in options]
                field_vals["selection"] = str(selection_list)

            # Handle many2one (link) fields
            if field_def.field_type == "link" and field_def.link_model_id:
                field_vals["relation"] = field_def.link_model_id.model

            field_record = IrModelFields.create(field_vals)
            created_fields |= field_record

            _logger.debug(
                "Created wizard field '%s' (type: %s) for event field '%s'",
                field_name,
                ttype,
                field_def.label,
            )

        return created_fields

    def _build_wizard_view_arch(self):
        """Build the XML architecture for the wizard form view.

        Returns:
            str: XML string for the view architecture
        """
        self.ensure_one()

        # Escape special characters in the name for XML
        safe_name = self.name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        # Build the notebook pages based on field groups
        notebook_pages = self._build_notebook_pages()

        # Build the complete form view (no XML declaration - Odoo handles that)
        arch = f"""<form string="Enter Event: {safe_name}">
    <group>
        <group string="Event Information">
            <field name="studio_event_type_id"
                   readonly="1"
                   options="{{'no_create': True, 'no_create_edit': True}}"/>
            <field name="event_type_id" invisible="1"/>
        </group>
        <group string="Registrant">
            <field name="partner_id"
                   readonly="1"
                   options="{{'no_create': True, 'no_create_edit': True}}"/>
            <field name="collection_date"/>
        </group>
    </group>

    <notebook>
{notebook_pages}
    </notebook>

    <footer>
        <button name="action_create_event"
                type="object"
                string="Create Event"
                class="btn-primary"/>
        <button string="Cancel" class="btn-secondary" special="cancel"/>
    </footer>
</form>"""
        return arch

    def _build_notebook_pages(self):
        """Build notebook pages XML based on field groups.

        If field groups are defined, creates a tab for each group plus a "General"
        tab for ungrouped fields. Otherwise creates a single "Event Data" tab.

        Returns:
            str: XML string for notebook pages
        """
        self.ensure_one()

        # Check if we have field groups
        if not self.field_group_ids:
            # No groups - use single tab layout
            return self._build_single_page_layout()

        # Build pages for each field group
        pages = []

        # First, add a page for ungrouped fields (if any)
        ungrouped_fields = self.data_fields.filtered(lambda f: not f.field_group_id).sorted("sequence")
        if ungrouped_fields:
            page_xml = self._build_page_for_fields(ungrouped_fields, "general", _("General"))
            pages.append(page_xml)

        # Then add a page for each field group
        for group in self.field_group_ids.sorted("sequence"):
            group_fields = group.field_ids.sorted("sequence")
            if group_fields:
                # Generate a safe page name from group name
                safe_page_name = re.sub(r"[^a-z0-9]+", "_", group.name.lower()).strip("_")
                page_xml = self._build_page_for_fields(group_fields, safe_page_name, group.name)
                pages.append(page_xml)

        return "\n".join(pages)

    def _build_single_page_layout(self):
        """Build the single-page layout when no field groups are defined.

        Returns:
            str: XML string for a single notebook page with 2-column layout
        """
        field_elements = []
        for field_def in self.data_fields.sorted("sequence"):
            field_element = self._build_field_element(field_def)
            field_elements.append(field_element)

        return self._build_page_for_fields(self.data_fields.sorted("sequence"), "event_data", _("Event Data"))

    def _build_page_for_fields(self, fields, page_name, page_title):
        """Build a notebook page XML for a set of fields.

        Args:
            fields: recordset of spp.studio.event.field
            page_name: technical name for the page
            page_title: display title for the page tab

        Returns:
            str: XML string for the notebook page
        """
        # Build field elements
        field_elements = []
        for field_def in fields:
            field_element = self._build_field_element(field_def)
            field_elements.append(field_element)

        # Split fields into two columns for a better layout
        mid_point = (len(field_elements) + 1) // 2  # Round up for left column
        left_fields = field_elements[:mid_point]
        right_fields = field_elements[mid_point:]

        left_xml = "\n                        ".join(left_fields) if left_fields else ""
        right_xml = "\n                        ".join(right_fields) if right_fields else ""

        # Escape special characters in the title for XML
        safe_title = page_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        return f"""        <page name="{page_name}" string="{safe_title}">
            <group>
                <group>
                    {left_xml}
                </group>
                <group>
                    {right_xml}
                </group>
            </group>
        </page>"""

    def _build_field_element(self, field_def):
        """Build a field XML element for a single field definition.

        Args:
            field_def: spp.studio.event.field record

        Returns:
            str: XML string for the field element
        """
        # Compute field name (this will be a computed field on the wizard)
        field_name = f"x_evt_{field_def.technical_name}"

        # Base attributes
        attrs = [f'name="{field_name}"', f'string="{field_def.label}"']

        # Add required attribute if applicable
        if field_def.is_required:
            attrs.append('required="1"')

        # Add widget based on field type
        widget = STUDIO_TO_WIDGET.get(field_def.field_type)
        if widget:
            attrs.append(f'widget="{widget}"')

        # Add help text if present
        if field_def.help_text:
            # Escape quotes in help text
            help_escaped = field_def.help_text.replace('"', "&quot;")
            attrs.append(f'help="{help_escaped}"')

        # Handle selection fields - add options
        if field_def.field_type in ("selection", "multi_select"):
            # We'll handle selection options via the field definition itself
            pass

        # Handle multi_select with placeholder
        if field_def.field_type == "multi_select":
            attrs.append('placeholder="value1, value2, ..."')

        # Handle conditional visibility
        if field_def.visibility_condition == "conditional" and field_def.visibility_field_id:
            dep_field_name = f"x_evt_{field_def.visibility_field_id.technical_name}"
            if field_def.visibility_operator == "set":
                attrs.append(f'invisible="not {dep_field_name}"')
            elif field_def.visibility_operator == "not_set":
                attrs.append(f'invisible="{dep_field_name}"')
            elif field_def.visibility_operator == "equals":
                val_escaped = field_def.visibility_value.replace("'", "\\'")
                attrs.append(f"invisible=\"{dep_field_name} != '{val_escaped}'\"")
            elif field_def.visibility_operator == "not_equals":
                val_escaped = field_def.visibility_value.replace("'", "\\'")
                attrs.append(f"invisible=\"{dep_field_name} == '{val_escaped}'\"")

        return f"<field {' '.join(attrs)}/>"

    def _post_deactivate(self):
        """Deactivate the linked event type and wizard view when deactivating."""
        if self.spp_event_type_id:
            self.spp_event_type_id.sudo().write({"active": False})
        if self.wizard_view_id:
            self.wizard_view_id.sudo().write({"active": False})
        # Note: We don't delete wizard_field_ids on deactivation.
        # They remain in the database but are unused until reactivation.
        # This preserves the ability to reactivate without regenerating fields.

    def _get_deactivation_impact(self):
        """Check if there are existing events before deactivating."""
        if not self.spp_event_type_id:
            return None

        # Count events using this type
        event_count = self.env["spp.event.data"].search_count([("event_type_id", "=", self.spp_event_type_id.id)])

        if event_count > 0:
            return _(
                "This event type is used by %(count)d event record(s). "
                "Deactivating will hide the event type but preserve existing events.",
                count=event_count,
            )
        return None

    def action_open_event_type(self):
        """Open the actual spp.event.type record."""
        self.ensure_one()
        if not self.spp_event_type_id:
            raise UserError(_("Event type not yet created. Activate this configuration first."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Event Type"),
            "res_model": "spp.event.type",
            "res_id": self.spp_event_type_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_events(self):
        """View events of this type."""
        self.ensure_one()
        if not self.spp_event_type_id:
            raise UserError(_("Event type not yet created. Activate this configuration first."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Events: %(name)s", name=self.name),
            "res_model": "spp.event.data",
            "view_mode": "tree,form",
            "domain": [("event_type_id", "=", self.spp_event_type_id.id)],
            "context": {"default_event_type_id": self.spp_event_type_id.id},
        }

    def action_enter_event_data(self):
        """Open the event data entry wizard for this event type."""
        self.ensure_one()
        if self.state != "active":
            raise UserError(
                _(
                    "Event type '%(name)s' is not active. Please activate it first to enter event data.",
                    name=self.name,
                )
            )

        action = {
            "type": "ir.actions.act_window",
            "name": _("Enter Event: %(name)s", name=self.name),
            "res_model": "spp.event.data.entry.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_studio_event_type_id": self.id,
            },
        }

        # Use the generated view if available
        if self.wizard_view_id:
            action["views"] = [(self.wizard_view_id.id, "form")]

        return action

    @api.model
    def _get_studio_config_type(self):
        return _("Event Type")


class StudioEventFieldGroup(models.Model):
    """Field group for organizing event fields into tabs.

    Field groups allow organizing event fields into logical sections
    that are displayed as separate tabs in the wizard form.
    """

    _name = "spp.studio.event.field.group"
    _description = "Studio Event Field Group"
    _order = "event_type_id, sequence, id"
    _rec_name = "name"

    # Parent event type
    event_type_id = fields.Many2one(
        "spp.studio.event.type",
        string="Event Type",
        required=True,
        ondelete="cascade",
        index=True,
    )
    event_type_state = fields.Selection(
        related="event_type_id.state",
        string="Event Type State",
        store=True,
    )

    # Group identification
    name = fields.Char(
        string="Group Name",
        required=True,
        translate=True,
        help="Display name for this tab (e.g., 'Personal Info', 'Medical History')",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which tabs are displayed",
    )

    # Fields in this group
    field_ids = fields.One2many(
        "spp.studio.event.field",
        "field_group_id",
        string="Fields",
        help="Fields belonging to this group",
    )
    field_count = fields.Integer(
        string="Field Count",
        compute="_compute_field_count",
    )

    @api.depends("field_ids")
    def _compute_field_count(self):
        for record in self:
            record.field_count = len(record.field_ids)

    def write(self, vals):
        """Prevent editing groups if parent event type is active."""
        for record in self:
            if record.event_type_state == "active" and not self.env.context.get("force_write"):
                raise UserError(
                    _(
                        "Cannot modify group '%(name)s' because the event type is active. "
                        "Deactivate the event type first.",
                        name=record.name,
                    )
                )
        return super().write(vals)

    def unlink(self):
        """Prevent deletion if parent event type is active."""
        for record in self:
            if record.event_type_state == "active":
                raise UserError(
                    _(
                        "Cannot delete group '%(name)s' because the event type is active. "
                        "Deactivate the event type first.",
                        name=record.name,
                    )
                )
        return super().unlink()


class StudioEventField(models.Model):
    """Field definition for a studio event type."""

    _name = "spp.studio.event.field"
    _description = "Studio Event Field"
    _order = "event_type_id, sequence, id"
    _rec_name = "label"

    # Parent event type
    event_type_id = fields.Many2one(
        "spp.studio.event.type",
        string="Event Type",
        required=True,
        ondelete="cascade",
        index=True,
    )
    event_type_state = fields.Selection(
        related="event_type_id.state",
        string="Event Type State",
        store=True,
    )

    # Optional field group (for tab organization)
    field_group_id = fields.Many2one(
        "spp.studio.event.field.group",
        string="Field Group",
        ondelete="set null",
        index=True,
        help="Group this field belongs to (displayed as tabs in the wizard)",
    )

    # Field identification
    label = fields.Char(
        string="Field Label",
        required=True,
        translate=True,
        help="Display label shown to users",
    )
    technical_name = fields.Char(
        string="Technical Name",
        compute="_compute_technical_name",
        store=True,
        readonly=True,
        precompute=True,
        help="Field name in JSON data (auto-generated from label)",
    )
    help_text = fields.Text(
        string="Help Text",
        translate=True,
        help="Optional help text shown to users",
    )

    # Field type
    field_type = fields.Selection(
        [
            ("text", "Text"),
            ("long_text", "Long Text"),
            ("integer", "Integer"),
            ("decimal", "Decimal"),
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

    # Link field options
    link_model_id = fields.Many2one(
        "ir.model",
        string="Link To",
        domain=[("transient", "=", False)],
        help="Model to link to for 'Link' field type",
    )
    link_domain = fields.Char(
        string="Link Domain",
        default="[]",
        help="Domain to filter available records (e.g., [('active', '=', True)])",
    )

    # Field options
    is_required = fields.Boolean(
        string="Required",
        default=False,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in the form",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # VALIDATION RULES
    # ══════════════════════════════════════════════════════════════════════════

    validation_type = fields.Selection(
        [
            ("none", "None"),
            ("range", "Value Range"),
            ("regex", "Pattern Match"),
        ],
        string="Validation",
        default="none",
        help="Type of validation to apply to this field",
    )

    # Range validation (for number/date fields)
    validation_min = fields.Float(
        string="Minimum Value",
        help="Minimum allowed value (for numbers) or earliest date",
    )
    validation_max = fields.Float(
        string="Maximum Value",
        help="Maximum allowed value (for numbers) or latest date",
    )

    # Regex validation (for text fields)
    validation_regex = fields.Char(
        string="Pattern",
        help="Regular expression pattern (e.g., ^[A-Z]{2}[0-9]{6}$ for ID format)",
    )

    # Error message
    validation_error_message = fields.Char(
        string="Error Message",
        translate=True,
        help="Message shown when validation fails",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # CONDITIONAL VISIBILITY
    # ══════════════════════════════════════════════════════════════════════════

    visibility_condition = fields.Selection(
        [
            ("always", "Always Visible"),
            ("conditional", "Conditional"),
        ],
        string="Visibility",
        default="always",
        help="Control when this field is visible",
    )

    # Reference another field in the same event type
    visibility_field_id = fields.Many2one(
        "spp.studio.event.field",
        string="Show When Field",
        domain="[('event_type_id', '=', event_type_id), ('id', '!=', id)]",
        help="Field that controls visibility of this field",
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
        help="Value to compare against (for equals/not_equals)",
    )

    @api.depends("label")
    def _compute_technical_name(self):
        """Compute technical name from label.

        The technical name is auto-generated from the label and must be
        unique within the event type. When the label changes (in draft state),
        the technical name is recomputed.
        """
        for record in self:
            if record.label:
                record.technical_name = record._generate_unique_technical_name()
            else:
                record.technical_name = False

    def _generate_unique_technical_name(self):
        """Generate a unique technical field name from the label.

        Returns a technical name that is unique within the event type.
        For existing records, excludes self from the uniqueness check.
        """
        self.ensure_one()

        # Convert to lowercase, replace spaces/special chars with underscore
        name = re.sub(r"[^a-z0-9]+", "_", self.label.lower())
        name = re.sub(r"_+", "_", name).strip("_")

        # Ensure uniqueness within event type
        base_name = name
        final_name = base_name
        counter = 1

        # Build base domain for uniqueness check
        event_type_id = self.event_type_id.id if self.event_type_id else False

        while True:
            domain = [("technical_name", "=", final_name)]
            if event_type_id:
                domain.append(("event_type_id", "=", event_type_id))

            # Exclude self if this is an existing record (has integer ID)
            if isinstance(self.id, int):
                domain.append(("id", "!=", self.id))

            if not self.search(domain, limit=1):
                break

            final_name = f"{base_name}_{counter}"
            counter += 1

        return final_name

    @api.constrains("field_type", "selection_options")
    def _check_selection_options(self):
        for record in self:
            if record.field_type in ("selection", "multi_select"):
                if not record.selection_options:
                    raise ValidationError(
                        _(
                            "Selection options are required for selection fields in field '%(label)s'.",
                            label=record.label,
                        )
                    )

    @api.constrains("field_type", "link_model_id")
    def _check_link_model(self):
        for record in self:
            if record.field_type == "link" and not record.link_model_id:
                raise ValidationError(
                    _(
                        "Link model is required for link fields in field '%(label)s'.",
                        label=record.label,
                    )
                )

    @api.constrains("validation_type", "validation_regex")
    def _check_validation_regex(self):
        """Validate regex pattern is valid."""
        for record in self:
            if record.validation_type == "regex" and record.validation_regex:
                try:
                    re.compile(record.validation_regex)
                except re.error as e:
                    raise ValidationError(
                        _(
                            "Invalid regex pattern in field '%(label)s': %(error)s",
                            label=record.label,
                            error=str(e),
                        )
                    ) from e

    @api.constrains("visibility_condition", "visibility_field_id")
    def _check_visibility_field(self):
        """Ensure visibility field is set when condition is conditional."""
        for record in self:
            if record.visibility_condition == "conditional":
                if not record.visibility_field_id:
                    raise ValidationError(
                        _(
                            "A visibility field must be selected when using "
                            "conditional visibility for field '%(label)s'.",
                            label=record.label,
                        )
                    )
                # Prevent circular references
                if record.visibility_field_id.id == record.id:
                    raise ValidationError(
                        _(
                            "Field '%(label)s' cannot reference itself for visibility.",
                            label=record.label,
                        )
                    )

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

    def validate_value(self, value):
        """Validate a value against this field's validation rules.

        Args:
            value: The value to validate

        Returns:
            tuple: (is_valid, error_message) - error_message is None if valid

        This method is used by the event data entry wizard to validate
        user input before creating event data records.
        """
        self.ensure_one()

        # Skip validation for empty values (required check is separate)
        if value is None or value == "" or value == []:
            return True, None

        # Range validation for numeric fields
        if self.validation_type == "range":
            if self.field_type in ("integer", "decimal"):
                try:
                    num_value = float(value)
                    # Use explicit None check since 0 is a valid min/max
                    if self.validation_min is not None and num_value < self.validation_min:
                        return False, self.validation_error_message or _(
                            "'%(field)s' must be at least %(min)s",
                            field=self.label,
                            min=self.validation_min,
                        )
                    if self.validation_max is not None and num_value > self.validation_max:
                        return False, self.validation_error_message or _(
                            "'%(field)s' must be at most %(max)s",
                            field=self.label,
                            max=self.validation_max,
                        )
                except (ValueError, TypeError):
                    return False, _("'%(field)s' must be a number", field=self.label)

        # Regex validation for text fields
        elif self.validation_type == "regex":
            if self.field_type in ("text", "long_text") and self.validation_regex:
                if not re.match(self.validation_regex, str(value)):
                    return False, self.validation_error_message or _(
                        "'%(field)s' does not match the required format",
                        field=self.label,
                    )

        # Selection validation
        if self.field_type == "selection":
            valid_values = [opt[0] for opt in self._parse_selection_options()]
            if value not in valid_values:
                return False, _(
                    "'%(field)s' has an invalid selection value",
                    field=self.label,
                )

        # Multi-select validation
        if self.field_type == "multi_select":
            valid_values = [opt[0] for opt in self._parse_selection_options()]
            if isinstance(value, list):
                for v in value:
                    if v not in valid_values:
                        return False, _(
                            "'%(field)s' contains invalid selection value '%(value)s'",
                            field=self.label,
                            value=v,
                        )

        return True, None

    def write(self, vals):
        """Prevent editing fields if parent event type is active."""
        for record in self:
            if record.event_type_state == "active" and not self.env.context.get("force_write"):
                raise UserError(
                    _(
                        "Cannot modify field '%(name)s' because the event type is active. "
                        "Deactivate the event type first.",
                        name=record.label,
                    )
                )
        return super().write(vals)

    def unlink(self):
        """Prevent deletion if parent event type is active."""
        for record in self:
            if record.event_type_state == "active":
                raise UserError(
                    _(
                        "Cannot delete field '%(name)s' because the event type is active. "
                        "Deactivate the event type first.",
                        name=record.label,
                    )
                )
        return super().unlink()
