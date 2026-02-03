"""Event Data Entry Wizard for entering events via Studio-defined event types."""

import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Prefix for dynamically generated event fields
X_EVT_PREFIX = "x_evt_"


class EventDataEntryWizard(models.TransientModel):
    """Wizard for entering event data based on Studio Event Type configuration.

    This wizard provides a structured data entry interface for Studio-defined
    event types, with field-by-field validation.
    """

    _name = "spp.event.data.entry.wizard"
    _description = "Event Data Entry Wizard"

    # Context fields
    studio_event_type_id = fields.Many2one(
        "spp.studio.event.type",
        string="Studio Event Type",
        required=True,
        domain="[('state', '=', 'active')]",
        help="The Studio Event Type configuration",
    )
    event_type_id = fields.Many2one(
        "spp.event.type",
        string="Event Type",
        compute="_compute_event_type_id",
        store=True,
    )

    @api.depends("studio_event_type_id")
    def _compute_event_type_id(self):
        for wizard in self:
            wizard.event_type_id = wizard.studio_event_type_id.spp_event_type_id

    # Registrant selection
    partner_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        required=True,
        domain="[('is_registrant', '=', True)]",
    )

    # Event metadata
    collection_date = fields.Date(
        string="Collection Date",
        required=True,
        default=fields.Date.context_today,
    )

    # Field values (dynamic)
    field_value_ids = fields.One2many(
        "spp.event.data.entry.wizard.field",
        "wizard_id",
        string="Field Values",
    )

    # Computed fields for preview
    field_count = fields.Integer(
        compute="_compute_field_count",
        string="Fields",
    )

    @api.depends("field_value_ids")
    def _compute_field_count(self):
        for wizard in self:
            wizard.field_count = len(wizard.field_value_ids)

    # ══════════════════════════════════════════════════════════════════════════
    # DYNAMIC FIELD HANDLING
    # ══════════════════════════════════════════════════════════════════════════

    def _get_dynamic_field_values(self):
        """Get values from dynamic x_evt_* fields.

        Returns:
            dict: Mapping of field technical_name to value
        """
        self.ensure_one()
        data_json = {}

        if not self.studio_event_type_id:
            return data_json

        for field_def in self.studio_event_type_id.data_fields:
            field_name = f"{X_EVT_PREFIX}{field_def.technical_name}"
            if field_name not in self._fields:
                continue

            value = getattr(self, field_name, None)

            # Convert value to appropriate type for JSON storage
            if field_def.field_type == "boolean":
                # Store boolean directly
                data_json[field_def.technical_name] = bool(value)
            elif field_def.field_type in ("date", "datetime"):
                # Convert date/datetime to string
                data_json[field_def.technical_name] = str(value) if value else None
            elif field_def.field_type == "multi_select":
                # Convert comma-separated string to list
                if value:
                    data_json[field_def.technical_name] = [v.strip() for v in str(value).split(",") if v.strip()]
                else:
                    data_json[field_def.technical_name] = []
            elif value is not None and value != "" and value is not False:
                data_json[field_def.technical_name] = value

        return data_json

    @api.onchange("studio_event_type_id")
    def _onchange_studio_event_type_id(self):
        """Populate field values when event type changes.

        Note: When a generated wizard view is being used (wizard_view_id is set),
        we skip populating field_value_ids because dynamic x_evt_* fields are used instead.
        """
        if not self.studio_event_type_id:
            self.field_value_ids = [Command.clear()]  # Clear existing
            return

        # Skip field_value_ids population when using generated view with dynamic fields
        # The dynamic x_evt_* fields will be used instead
        if self.studio_event_type_id.wizard_view_id:
            return

        # Build field values from event type definition (legacy/fallback behavior)
        field_vals = []
        for field_def in self.studio_event_type_id.data_fields.sorted("sequence"):
            field_vals.append(Command.create({"field_def_id": field_def.id, "sequence": field_def.sequence}))

        self.field_value_ids = [Command.clear()] + field_vals

    def _check_visibility(self, field_def):
        """Check if a field should be visible based on visibility conditions.

        Returns True if the field should be shown.
        """
        if field_def.visibility_condition != "conditional":
            return True

        if not field_def.visibility_field_id:
            return True

        # Find the value of the dependency field
        dep_field = field_def.visibility_field_id
        dep_value = None
        for field_val in self.field_value_ids:
            if field_val.field_def_id.id == dep_field.id:
                dep_value = field_val._get_typed_value()
                break

        # Evaluate condition
        if field_def.visibility_operator == "set":
            return bool(dep_value)
        elif field_def.visibility_operator == "not_set":
            return not dep_value
        elif field_def.visibility_operator == "equals":
            return str(dep_value) == field_def.visibility_value
        elif field_def.visibility_operator == "not_equals":
            return str(dep_value) != field_def.visibility_value

        return True

    def action_create_event(self):
        """Validate and create the event data record."""
        self.ensure_one()

        if not self.event_type_id:
            raise ValidationError(
                _(
                    "Event type '%(name)s' has not been activated. " "Please activate it first.",
                    name=self.studio_event_type_id.name,
                )
            )

        # Check if we have dynamic fields with values (generated view is being used)
        has_dynamic_fields = self._has_dynamic_fields_with_values()

        # Collect and validate field values
        data_json = {}
        errors = []

        if has_dynamic_fields:
            # Read from dynamic x_evt_* fields
            data_json = self._get_dynamic_field_values()
            # Validate the values
            errors = self._validate_dynamic_field_values(data_json)
        else:
            # Fall back to reading from field_value_ids (legacy behavior)
            for field_val in self.field_value_ids.sorted("sequence"):
                field_def = field_val.field_def_id

                # Check visibility
                if not self._check_visibility(field_def):
                    continue  # Skip hidden fields

                # Get typed value
                value = field_val._get_typed_value()

                # Required check
                if field_def.is_required:
                    if value is None or value == "" or value == []:
                        errors.append(_("'%(field)s' is required", field=field_def.label))
                        continue

                # Skip validation for empty non-required fields
                if value is None or value == "" or value == []:
                    continue

                # Validate value using field definition's validate_value method
                is_valid, error_msg = field_def.validate_value(value)
                if not is_valid:
                    errors.append(error_msg)
                    continue

                # Store the value
                data_json[field_def.technical_name] = value

        if errors:
            raise ValidationError("\n".join(errors))

        # Create the event data record
        event_vals = {
            "event_type_id": self.event_type_id.id,
            "partner_id": self.partner_id.id,
            "collection_date": self.collection_date,
            "data_json": data_json,
            "state": "draft",
        }

        event = self.env["spp.event.data"].create(event_vals)

        _logger.info(
            "Created event data %s for registrant %s via entry wizard",
            event.id,
            self.partner_id.name,
        )

        # Return action to view the created event
        return {
            "type": "ir.actions.act_window",
            "name": _("Event Created"),
            "res_model": "spp.event.data",
            "res_id": event.id,
            "view_mode": "form",
            "target": "current",
        }

    def _has_dynamic_fields_with_values(self):
        """Check if this wizard has dynamic x_evt_* fields with values.

        Returns True only if dynamic fields exist AND at least one has a meaningful value.
        This allows fallback to field_value_ids when dynamic fields exist but are empty.
        """
        if not self.studio_event_type_id:
            return False

        has_any_value = False
        for field_def in self.studio_event_type_id.data_fields:
            field_name = f"{X_EVT_PREFIX}{field_def.technical_name}"
            if field_name not in self._fields:
                continue

            value = getattr(self, field_name, None)

            # Check if field has a meaningful value based on type
            # Empty values: None, False, "", 0, 0.0, []
            if field_def.field_type in ("integer", "decimal", "link"):
                # For numeric fields, 0 is usually the default/empty value
                # Only consider non-zero values as "having a value"
                if value and value != 0:
                    has_any_value = True
                    break
            elif field_def.field_type == "boolean":
                # Boolean fields: only True is considered a value (False is default)
                if value is True:
                    has_any_value = True
                    break
            else:
                # For text, selection, etc: any truthy value counts
                if value:
                    has_any_value = True
                    break

        return has_any_value

    def _validate_dynamic_field_values(self, data_json):
        """Validate values from dynamic fields.

        Args:
            data_json: dict of field technical_name -> value

        Returns:
            list: Error messages (empty if all valid)
        """
        errors = []

        for field_def in self.studio_event_type_id.data_fields:
            value = data_json.get(field_def.technical_name)

            # Check visibility
            if not self._check_visibility_by_data(field_def, data_json):
                continue  # Skip hidden fields

            # Required check
            if field_def.is_required:
                if value is None or value == "" or value == []:
                    errors.append(_("'%(field)s' is required", field=field_def.label))
                    continue

            # Skip validation for empty non-required fields
            if value is None or value == "" or value == []:
                continue

            # Validate value using field definition's validate_value method
            is_valid, error_msg = field_def.validate_value(value)
            if not is_valid:
                errors.append(error_msg)

        return errors

    def _check_visibility_by_data(self, field_def, data_json):
        """Check if a field should be visible based on visibility conditions and data_json.

        Args:
            field_def: spp.studio.event.field record
            data_json: dict of field values

        Returns:
            bool: True if the field should be shown
        """
        if field_def.visibility_condition != "conditional":
            return True

        if not field_def.visibility_field_id:
            return True

        # Get the value of the dependency field
        dep_field = field_def.visibility_field_id
        dep_value = data_json.get(dep_field.technical_name)

        # Evaluate condition
        if field_def.visibility_operator == "set":
            return bool(dep_value)
        elif field_def.visibility_operator == "not_set":
            return not dep_value
        elif field_def.visibility_operator == "equals":
            return str(dep_value) == field_def.visibility_value
        elif field_def.visibility_operator == "not_equals":
            return str(dep_value) != field_def.visibility_value

        return True


class EventDataEntryWizardField(models.TransientModel):
    """Field value entry in the event data entry wizard.

    This model holds the value for a single field in the wizard,
    with separate storage columns for different data types.
    """

    _name = "spp.event.data.entry.wizard.field"
    _description = "Event Data Entry Wizard Field"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        "spp.event.data.entry.wizard",
        required=True,
        ondelete="cascade",
    )

    # Reference to field definition
    field_def_id = fields.Many2one(
        "spp.studio.event.field",
        string="Field",
        required=True,
        ondelete="cascade",
    )

    # Field metadata (for display)
    label = fields.Char(related="field_def_id.label")
    field_type = fields.Selection(related="field_def_id.field_type")
    is_required = fields.Boolean(related="field_def_id.is_required")
    help_text = fields.Text(related="field_def_id.help_text")
    selection_options = fields.Text(related="field_def_id.selection_options")
    sequence = fields.Integer(default=10)

    # Value storage (one per type for proper form widget support)
    value_text = fields.Char(string="Text Value")
    value_long_text = fields.Text(string="Long Text Value")
    value_integer = fields.Integer(string="Integer Value")
    value_decimal = fields.Float(string="Decimal Value")
    value_date = fields.Date(string="Date Value")
    value_datetime = fields.Datetime(string="Datetime Value")
    value_boolean = fields.Boolean(string="Boolean Value")
    # Selection fields use Char to store the selected option code.
    # Options are validated against field_def_id.selection_options.
    value_selection = fields.Char(string="Selection Value")
    # Multi-select uses comma-separated values for flexibility.
    # Options are validated against field_def_id.selection_options.
    value_multi_select = fields.Char(
        string="Multi-Select Value",
        help="Comma-separated selection values",
    )
    value_link = fields.Integer(
        string="Link Value",
        help="ID of linked record",
    )

    # Computed display value for clean list view
    display_value = fields.Char(
        string="Value",
        compute="_compute_display_value",
        inverse="_inverse_display_value",
    )

    @api.depends(
        "field_type",
        "value_text",
        "value_long_text",
        "value_integer",
        "value_decimal",
        "value_date",
        "value_datetime",
        "value_boolean",
        "value_selection",
        "value_multi_select",
        "value_link",
    )
    def _compute_display_value(self):
        """Compute a display-friendly value for the list view."""
        for rec in self:
            field_type = rec.field_type
            if field_type == "text":
                rec.display_value = rec.value_text or ""
            elif field_type == "long_text":
                # Truncate long text for display
                text = rec.value_long_text or ""
                rec.display_value = (text[:50] + "...") if len(text) > 50 else text
            elif field_type == "integer":
                rec.display_value = str(rec.value_integer) if rec.value_integer else ""
            elif field_type == "decimal":
                rec.display_value = str(rec.value_decimal) if rec.value_decimal else ""
            elif field_type == "date":
                rec.display_value = str(rec.value_date) if rec.value_date else ""
            elif field_type == "datetime":
                rec.display_value = str(rec.value_datetime) if rec.value_datetime else ""
            elif field_type == "boolean":
                rec.display_value = _("Yes") if rec.value_boolean else _("No")
            elif field_type == "selection":
                # Try to get the label from selection options
                rec.display_value = rec._get_selection_label(rec.value_selection)
            elif field_type == "multi_select":
                rec.display_value = rec.value_multi_select or ""
            elif field_type == "link":
                rec.display_value = str(rec.value_link) if rec.value_link else ""
            else:
                rec.display_value = ""

    def _inverse_display_value(self):
        """Allow editing display_value for simple text fields."""
        for rec in self:
            if rec.field_type == "text":
                rec.value_text = rec.display_value
            elif rec.field_type == "long_text":
                rec.value_long_text = rec.display_value
            # For other types, the display_value is read-only
            # User must use the specific typed fields to edit

    def _get_selection_label(self, value):
        """Get the display label for a selection value."""
        if not value or not self.selection_options:
            return value or ""

        # Parse selection options (format: "key:Label\nkey2:Label2")
        for line in (self.selection_options or "").split("\n"):
            line = line.strip()
            if ":" in line:
                key, label = line.split(":", 1)
                if key.strip() == value:
                    return label.strip()
        return value

    def _get_typed_value(self):
        """Get the value in its proper type."""
        self.ensure_one()

        field_type = self.field_type
        if field_type == "text":
            return self.value_text or None
        elif field_type == "long_text":
            return self.value_long_text or None
        elif field_type == "integer":
            return self.value_integer if self.value_integer else None
        elif field_type == "decimal":
            return self.value_decimal if self.value_decimal else None
        elif field_type == "date":
            return str(self.value_date) if self.value_date else None
        elif field_type == "datetime":
            return str(self.value_datetime) if self.value_datetime else None
        elif field_type == "boolean":
            return self.value_boolean
        elif field_type == "selection":
            return self.value_selection or None
        elif field_type == "multi_select":
            if self.value_multi_select:
                return [v.strip() for v in self.value_multi_select.split(",") if v.strip()]
            return []
        elif field_type == "link":
            return self.value_link if self.value_link else None
        return None

    def _set_typed_value(self, value):
        """Set the value from its typed form.

        Args:
            value: The value in its native type (str, int, float, bool, date, list, etc.)
        """
        self.ensure_one()

        field_type = self.field_type
        if field_type == "text":
            self.value_text = str(value) if value else False
        elif field_type == "long_text":
            self.value_long_text = str(value) if value else False
        elif field_type == "integer":
            self.value_integer = int(value) if value else 0
        elif field_type == "decimal":
            self.value_decimal = float(value) if value else 0.0
        elif field_type == "date":
            self.value_date = value if value else False
        elif field_type == "datetime":
            self.value_datetime = value if value else False
        elif field_type == "boolean":
            self.value_boolean = bool(value)
        elif field_type == "selection":
            self.value_selection = str(value) if value else False
        elif field_type == "multi_select":
            if isinstance(value, list):
                self.value_multi_select = ", ".join(str(v) for v in value)
            else:
                self.value_multi_select = str(value) if value else False
        elif field_type == "link":
            self.value_link = int(value) if value else 0
