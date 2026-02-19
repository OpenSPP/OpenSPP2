"""Event Type Builder Wizard for creating custom event types."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EventTypeBuilderWizard(models.TransientModel):
    """Three-step wizard for creating custom event types.

    Step 1: Basic Info - name, target type, description
    Step 2: Add Fields - define event fields (inline editable)
    Step 3: Review - summary and create as draft
    """

    _name = "spp.studio.event.type.wizard"
    _description = "Event Type Builder Wizard"

    # Wizard state
    step = fields.Selection(
        [
            ("basic", "Basic Info"),
            ("fields", "Add Fields"),
            ("review", "Review"),
        ],
        string="Step",
        default="basic",
        required=True,
    )

    # Step 1: Basic Info
    name = fields.Char(
        string="Event Type Name",
        required=True,
        help="Name for this event type (e.g., 'Health Screening')",
    )
    description = fields.Text(
        string="Description",
        help="Describe what this event type is used for",
    )
    target_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
            ("both", "Both Individual and Group"),
        ],
        string="Can be recorded for",
        required=True,
        default="individual",
        help="Who can this event be recorded for?",
    )

    # Step 2: Fields
    field_line_ids = fields.One2many(
        "spp.studio.event.type.wizard.field",
        "wizard_id",
        string="Event Fields",
        help="Define the fields for this event type",
    )
    field_count = fields.Integer(
        string="Field Count",
        compute="_compute_field_count",
    )

    @api.depends("field_line_ids")
    def _compute_field_count(self):
        for wizard in self:
            wizard.field_count = len(wizard.field_line_ids)

    # Step 3: Preview
    kobo_form_id = fields.Char(
        string="Kobo Form ID (Optional)",
        help="If you collect data using KoboToolbox, enter the form ID here to link it",
    )
    allow_multiple = fields.Boolean(
        string="Allow Multiple Events",
        default=True,
        help=(
            "If checked, a person can have multiple events of this type "
            "(e.g., multiple assessments). If unchecked, new events replace old ones."
        ),
    )
    requires_approval = fields.Boolean(
        string="Requires Approval",
        default=False,
        help="If checked, events must be reviewed and approved before being recorded",
    )

    preview_technical_name = fields.Char(
        string="Technical Code",
        compute="_compute_preview",
        help="Auto-generated code used internally. You don't need to change this.",
    )

    @api.depends("name")
    def _compute_preview(self):
        for wizard in self:
            if wizard.name:
                import re

                code = re.sub(r"[^a-z0-9]+", "_", wizard.name.lower())
                code = re.sub(r"_+", "_", code).strip("_")
                wizard.preview_technical_name = f"x_evt_{code}"
            else:
                wizard.preview_technical_name = ""

    def action_next(self):
        """Move to the next step."""
        self.ensure_one()
        if self.step == "basic":
            if not self.name:
                raise ValidationError(_("Please enter an event type name."))
            if not self.target_type:
                raise ValidationError(_("Please select a target type."))
            self.step = "fields"
        elif self.step == "fields":
            if not self.field_line_ids:
                raise ValidationError(_("Please add at least one field. Use the 'Add a line' button below."))
            # Validate all fields
            for field in self.field_line_ids:
                if not field.label:
                    raise ValidationError(_("All fields must have a label."))
                if field.field_type in ("selection", "multi_select") and not field.selection_options:
                    raise ValidationError(
                        _(
                            "Selection field '%(label)s' must have options.",
                            label=field.label,
                        )
                    )
                if field.field_type == "link" and not field.link_model_id:
                    raise ValidationError(
                        _(
                            "Link field '%(label)s' must specify a model to link to.",
                            label=field.label,
                        )
                    )
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
        if self.step == "fields":
            self.step = "basic"
        elif self.step == "review":
            self.step = "fields"

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_create_event_type(self):
        """Create the studio event type as a draft."""
        self.ensure_one()

        # Create the event type
        event_type_vals = {
            "name": self.name,
            "description": self.description,
            "target_type": self.target_type,
            "kobo_form_id": self.kobo_form_id or False,
            "allow_multiple": self.allow_multiple,
            "requires_approval": self.requires_approval,
            "state": "draft",
        }

        event_type = self.env["spp.studio.event.type"].create(event_type_vals)

        # Create fields
        for idx, field_line in enumerate(self.field_line_ids):
            field_vals = {
                "event_type_id": event_type.id,
                "label": field_line.label,
                "help_text": field_line.help_text or "",
                "field_type": field_line.field_type,
                "selection_options": field_line.selection_options or "",
                "is_required": field_line.is_required,
                "sequence": (idx + 1) * 10,
                # Link field options
                "link_model_id": field_line.link_model_id.id if field_line.link_model_id else False,
                "link_domain": field_line.link_domain or "[]",
                # Validation rules
                "validation_type": field_line.validation_type,
                "validation_min": field_line.validation_min,
                "validation_max": field_line.validation_max,
                "validation_regex": field_line.validation_regex,
                "validation_error_message": field_line.validation_error_message,
            }
            self.env["spp.studio.event.field"].create(field_vals)

        # Return action to view the created event type
        return {
            "type": "ir.actions.act_window",
            "name": _("Event Type Created"),
            "res_model": "spp.studio.event.type",
            "res_id": event_type.id,
            "view_mode": "form",
            "target": "current",
        }


class EventTypeBuilderWizardField(models.TransientModel):
    """Field line in the event type wizard."""

    _name = "spp.studio.event.type.wizard.field"
    _description = "Event Type Wizard Field Line"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        "spp.studio.event.type.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )

    label = fields.Char(
        string="Field Label",
        required=True,
        help="Label shown to users",
    )

    field_type = fields.Selection(
        [
            ("text", "Short Text"),
            ("long_text", "Long Text"),
            ("integer", "Whole Number"),
            ("decimal", "Decimal Number"),
            ("date", "Date"),
            ("datetime", "Date & Time"),
            ("boolean", "Yes/No"),
            ("selection", "Single Choice"),
            ("multi_select", "Multiple Choice"),
            ("link", "Link to Record"),
        ],
        string="Type",
        required=True,
        default="text",
        help="Choose the type of information you want to collect",
    )

    selection_options = fields.Text(
        string="Options",
        help="For selection fields: one option per line (format: value|Label)",
    )

    # Link field options
    link_model_id = fields.Many2one(
        "ir.model",
        string="Link To",
        domain=[("transient", "=", False)],
        help="Model to link to for 'Link' field type",
    )
    link_domain = fields.Char(
        string="Link Filter",
        default="[]",
        help="Domain to filter available records",
    )

    is_required = fields.Boolean(
        string="Required",
        default=False,
    )

    help_text = fields.Text(
        string="Help Text",
        help="Optional help text for users",
    )

    # Validation rules
    validation_type = fields.Selection(
        [
            ("none", "None"),
            ("range", "Value Range"),
            ("regex", "Pattern Match"),
        ],
        string="Validation",
        default="none",
    )
    validation_min = fields.Float(string="Minimum")
    validation_max = fields.Float(string="Maximum")
    validation_regex = fields.Char(string="Pattern")
    validation_error_message = fields.Char(string="Error Message")

    # Note: Constraints are not applied here because the wizard validates fields
    # in action_next() when moving from 'fields' to 'review' step.
    # This allows users to create incomplete fields and fix them before proceeding.
