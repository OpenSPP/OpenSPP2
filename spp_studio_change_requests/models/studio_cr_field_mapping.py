"""Field mapping model for Studio Change Request Types."""

import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Mapping from res.partner field types to appropriate detail field types
FIELD_TYPE_MAPPING = {
    "char": "char",
    "text": "text",
    "integer": "integer",
    "float": "float",
    "monetary": "float",
    "date": "date",
    "datetime": "datetime",
    "boolean": "boolean",
    "selection": "selection",
    "many2one": "many2one",
    "many2many": "many2many",
}


class StudioCRFieldMapping(models.Model):
    """Field mapping for change request types.

    Defines which fields from res.partner can be changed via
    this change request type.
    """

    _name = "spp.studio.cr.field.mapping"
    _description = "Studio CR Field Mapping"
    _order = "sequence, id"

    cr_type_id = fields.Many2one(
        "spp.studio.change.request.type",
        string="CR Type",
        required=True,
        ondelete="cascade",
        index=True,
    )

    # Field selection
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Field",
        required=True,
        ondelete="cascade",  # 'restrict' not supported for ir.model.fields in Odoo 19
        domain="[('model', '=', 'res.partner'), ('store', '=', True)]",
        help="Field on res.partner that can be changed",
    )
    field_name = fields.Char(
        related="field_id.name",
        string="Field Name",
        store=True,
    )
    field_type = fields.Selection(
        related="field_id.ttype",
        string="Field Type",
        store=True,
    )

    # Display configuration
    label = fields.Char(
        string="Label",
        translate=True,
        help="Display label (defaults to field description)",
    )
    help_text = fields.Text(
        string="Help Text",
        translate=True,
        help="Additional help text for users",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in the form",
    )

    # Field options
    is_required = fields.Boolean(
        string="Required",
        default=False,
        help="This field must be filled in the change request",
    )
    is_readonly = fields.Boolean(
        string="Read-only",
        default=False,
        help="Field is shown but cannot be edited",
    )

    # Validation
    validation_type = fields.Selection(
        [
            ("none", "No Validation"),
            ("regex", "Regular Expression"),
            ("domain", "Domain"),
        ],
        string="Validation",
        default="none",
    )
    validation_rule = fields.Char(
        string="Validation Rule",
        help="Regex pattern or domain expression",
    )

    @api.onchange("field_id")
    def _onchange_field_id(self):
        """Set default label from field description."""
        if self.field_id and not self.label:
            self.label = self.field_id.field_description

    @api.model_create_multi
    def create(self, vals_list):
        """Create field mappings and sync to active types."""
        records = super().create(vals_list)

        # If any CR type is active, sync the detail model
        for record in records:
            if record.cr_type_id.state == "active" and record.cr_type_id.detail_model_id:
                record.cr_type_id._sync_detail_model_fields()

        return records

    def write(self, vals):
        """Update field mappings and sync to active types."""
        result = super().write(vals)

        # If CR type is active, sync the detail model
        for record in self:
            if record.cr_type_id.state == "active" and record.cr_type_id.detail_model_id:
                record.cr_type_id._sync_detail_model_fields()

        return result

    @api.constrains("field_id", "cr_type_id")
    def _check_field_unique(self):
        """Ensure each field is only mapped once per CR type."""
        for record in self:
            if record.field_id and record.cr_type_id:
                count = self.search_count(
                    [
                        ("cr_type_id", "=", record.cr_type_id.id),
                        ("field_id", "=", record.field_id.id),
                        ("id", "!=", record.id),
                    ]
                )
                if count > 0:
                    raise ValidationError(
                        _(
                            "Field '%(field)s' is already mapped in this change request type.",
                            field=record.field_id.field_description,
                        )
                    )

    @api.constrains("validation_type", "validation_rule")
    def _check_validation_rule(self):
        """Validate the validation rule."""
        for record in self:
            if record.validation_type in ("regex", "domain"):
                if not record.validation_rule:
                    raise ValidationError(
                        _("Validation rule is required for %(type)s validation.", type=record.validation_type)
                    )
                if record.validation_type == "regex":
                    # Test if valid regex
                    import re

                    try:
                        re.compile(record.validation_rule)
                    except re.error as e:
                        raise ValidationError(_("Invalid regular expression: %(error)s", error=str(e))) from e

    def _prepare_detail_field_vals(self, detail_model):
        """Prepare values for creating field on detail model.

        Note: We always set required=False at the database level to avoid NOT NULL
        constraints. Required field validation is handled at the application level
        via the CR type's required_field_ids Many2many field.
        """
        self.ensure_one()

        # Get the target field type
        target_type = FIELD_TYPE_MAPPING.get(self.field_type, "char")

        # Field name must start with x_ for manual models
        field_name = self.field_name
        if not field_name.startswith("x_"):
            field_name = f"x_{field_name}"

        vals = {
            "name": field_name,
            "field_description": self.label or self.field_id.field_description,
            "model_id": detail_model.id,
            "ttype": target_type,
            "help": self.help_text or "",
            "required": False,  # Never set database-level constraint
            "readonly": self.is_readonly,
            "state": "manual",
            "copied": False,
        }

        # Handle relational fields
        if self.field_type == "many2one":
            vals["relation"] = self.field_id.relation
            # Copy domain if it exists
            if self.field_id.domain:
                vals["domain"] = self.field_id.domain

        elif self.field_type == "many2many":
            vals["relation"] = self.field_id.relation

        # Handle selection fields
        elif self.field_type == "selection":
            # Copy selection options from original field
            if self.field_id.selection_ids:
                vals["selection_ids"] = [
                    Command.create({"value": sel.value, "name": sel.name, "sequence": sel.sequence})
                    for sel in self.field_id.selection_ids
                ]

        return vals

    def _create_spp_mapping(self, cr_type):
        """Create the spp.change.request.type.mapping for this field.

        The source field is the field on the detail model (x_<fieldname>),
        and the target field is the field on the registrant (fieldname).
        """
        self.ensure_one()

        source_field = f"x_{self.field_name}"
        vals = {
            "type_id": cr_type.id,
            "source_field": source_field,
            "target_field": self.field_name,
            "sequence": self.sequence,
            "transform": "direct",
        }

        self.env["spp.change.request.type.mapping"].sudo().create(vals)
        _logger.debug(
            "Created CR type mapping: %s -> %s",
            source_field,
            self.field_name,
        )
