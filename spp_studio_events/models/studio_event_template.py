"""Event Field Templates for reusable event type patterns."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StudioEventFieldTemplate(models.Model):
    """Template containing a set of fields for common event type patterns.

    Templates provide reusable field definitions that can be applied to
    new event types, saving time and ensuring consistency.
    """

    _name = "spp.studio.event.field.template"
    _description = "Event Field Template"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Display name for the template",
    )
    code = fields.Char(
        required=True,
        index=True,
        help="Unique code for the template",
    )
    description = fields.Text(
        translate=True,
        help="Description of what this template is used for",
    )
    sequence = fields.Integer(
        default=10,
        help="Order in the template list",
    )

    category = fields.Selection(
        [
            ("survey", "Survey/Assessment"),
            ("health", "Health Screening"),
            ("economic", "Economic Assessment"),
            ("demographic", "Demographic"),
            ("visit", "Field Visit"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
        help="Category for organizing templates",
    )

    field_ids = fields.One2many(
        "spp.studio.event.field.template.line",
        "template_id",
        string="Fields",
        help="Field definitions in this template",
    )

    field_count = fields.Integer(
        string="Field Count",
        compute="_compute_field_count",
    )

    active = fields.Boolean(
        default=True,
        help="Set to false to hide the template without deleting it",
    )

    @api.depends("field_ids")
    def _compute_field_count(self):
        for rec in self:
            rec.field_count = len(rec.field_ids)

    _code_unique = models.Constraint("UNIQUE(code)", "Template code must be unique!")

    def action_apply_to_event_type(self):
        """Open wizard to apply this template to an event type."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Apply Template: %(name)s", name=self.name),
            "res_model": "spp.studio.event.field.template.apply.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_template_id": self.id,
            },
        }

    def apply_to_event_type(self, event_type, replace_existing=False):
        """Apply template fields to an event type.

        Args:
            event_type: The spp.studio.event.type record to apply to
            replace_existing: If True, removes existing fields first

        Returns:
            The created field records
        """
        self.ensure_one()

        if event_type.state != "draft":
            raise UserError(
                _(
                    "Cannot apply template to '%(name)s'. Only draft event types can be modified.",
                    name=event_type.name,
                )
            )

        if replace_existing:
            event_type.data_fields.unlink()

        StudioField = self.env["spp.studio.event.field"]
        created_fields = StudioField

        # Get max sequence of existing fields
        max_seq = max((f.sequence for f in event_type.data_fields), default=0)

        for line in self.field_ids.sorted("sequence"):
            field_vals = {
                "event_type_id": event_type.id,
                "label": line.label,
                "field_type": line.field_type,
                "help_text": line.help_text,
                "is_required": line.is_required,
                "selection_options": line.selection_options,
                "sequence": max_seq + line.sequence,
                # Validation
                "validation_type": line.validation_type,
                "validation_min": line.validation_min,
                "validation_max": line.validation_max,
                "validation_regex": line.validation_regex,
                "validation_error_message": line.validation_error_message,
            }

            # Handle link field
            if line.field_type == "link" and line.link_model_name:
                model = self.env["ir.model"].search([("model", "=", line.link_model_name)], limit=1)
                if model:
                    field_vals["link_model_id"] = model.id
                    field_vals["link_domain"] = line.link_domain or "[]"

            created_fields |= StudioField.create(field_vals)

        return created_fields


class StudioEventFieldTemplateLine(models.Model):
    """Field definition within an event field template."""

    _name = "spp.studio.event.field.template.line"
    _description = "Event Field Template Line"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "spp.studio.event.field.template",
        required=True,
        ondelete="cascade",
        index=True,
    )

    # Field definition (mirrors spp.studio.event.field)
    label = fields.Char(
        required=True,
        translate=True,
        help="Display label for the field",
    )
    technical_name = fields.Char(
        help="Suggested technical name (auto-generated if blank)",
    )
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
        required=True,
        default="text",
    )
    help_text = fields.Text(
        translate=True,
        help="Help text shown to users",
    )
    is_required = fields.Boolean(
        default=False,
    )
    selection_options = fields.Text(
        help="For selection/multi_select: value|Label per line",
    )
    sequence = fields.Integer(
        default=10,
    )

    # Link field options
    link_model_name = fields.Char(
        string="Link Model",
        help="Model name (e.g., res.partner) for link fields",
    )
    link_domain = fields.Char(
        string="Link Domain",
        default="[]",
    )

    # Validation defaults
    validation_type = fields.Selection(
        [
            ("none", "None"),
            ("range", "Value Range"),
            ("regex", "Pattern Match"),
        ],
        default="none",
    )
    validation_min = fields.Float()
    validation_max = fields.Float()
    validation_regex = fields.Char()
    validation_error_message = fields.Char(translate=True)


class StudioEventFieldTemplateApplyWizard(models.TransientModel):
    """Wizard for applying a template to an event type."""

    _name = "spp.studio.event.field.template.apply.wizard"
    _description = "Apply Event Field Template"

    template_id = fields.Many2one(
        "spp.studio.event.field.template",
        string="Template",
        required=True,
        ondelete="cascade",
    )
    event_type_id = fields.Many2one(
        "spp.studio.event.type",
        string="Event Type",
        required=True,
        domain=[("state", "=", "draft")],
        ondelete="cascade",
    )
    replace_existing = fields.Boolean(
        string="Replace Existing Fields",
        default=False,
        help="If checked, removes all existing fields before applying template",
    )

    # Preview information
    template_field_count = fields.Integer(
        related="template_id.field_count",
    )
    event_type_field_count = fields.Integer(
        related="event_type_id.data_field_count",
    )

    def action_apply(self):
        """Apply the template to the event type."""
        self.ensure_one()

        self.template_id.apply_to_event_type(
            self.event_type_id,
            replace_existing=self.replace_existing,
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.studio.event.type",
            "res_id": self.event_type_id.id,
            "view_mode": "form",
            "target": "current",
        }
