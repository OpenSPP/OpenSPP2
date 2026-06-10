# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Field Encryption Configuration.

Provides UI-based configuration for enabling/disabling encryption on
specific fields, along with blind index settings for searchable encryption.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FieldEncryptionConfig(models.Model):
    """Configuration for field-level encryption.

    Allows administrators to enable encryption on specific fields via UI
    instead of requiring code changes.
    """

    _name = "spp.field.encryption.config"
    _description = "Field Encryption Configuration"
    _order = "model_id, field_id"
    _rec_name = "display_name"

    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
        help="The model containing the field to encrypt",
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        index=True,
    )
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Field",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['char', 'text'])]",
        help="The field to encrypt (only char and text fields supported)",
    )
    field_name = fields.Char(
        related="field_id.name",
        store=True,
        index=True,
    )

    encryption_enabled = fields.Boolean(
        string="Encryption Enabled",
        default=True,
        help="Enable encryption for this field",
    )

    blind_index_enabled = fields.Boolean(
        string="Blind Index Enabled",
        default=True,
        help="Enable blind index for searching encrypted values",
    )

    index_type = fields.Selection(
        selection=[
            ("exact", "Exact Match"),
            ("partial", "Partial (Last 4)"),
            ("phonetic", "Phonetic (Soundex)"),
        ],
        string="Index Type",
        default="exact",
        help="Type of blind index to use for searching:\n"
        "- Exact: Full value matching (normalized)\n"
        "- Partial: Match last 4 characters\n"
        "- Phonetic: Sound-alike matching for names",
    )

    index_field_name = fields.Char(
        string="Index Field",
        compute="_compute_index_field_name",
        help="Name of the field that stores the blind index",
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    active = fields.Boolean(
        default=True,
        help="Set to false to disable this configuration without deleting it",
    )

    notes = fields.Text(
        string="Notes",
        help="Optional notes about this encryption configuration",
    )

    # Unique constraint
    _unique_model_field = models.Constraint(
        "UNIQUE(model_id, field_id)",
        "Encryption configuration already exists for this model and field!",
    )

    @api.depends("model_id", "field_id")
    def _compute_display_name(self):
        for record in self:
            if record.model_id and record.field_id:
                record.display_name = f"{record.model_id.model}.{record.field_id.name}"
            else:
                record.display_name = "New Configuration"

    @api.depends("field_id", "index_type")
    def _compute_index_field_name(self):
        for record in self:
            if record.field_id:
                if record.index_type == "partial":
                    record.index_field_name = f"{record.field_id.name}_last4"
                else:
                    record.index_field_name = f"{record.field_id.name}_index"
            else:
                record.index_field_name = False

    @api.constrains("field_id")
    def _check_field_type(self):
        """Ensure only char and text fields can be encrypted."""
        for record in self:
            if record.field_id and record.field_id.ttype not in ("char", "text"):
                raise ValidationError(
                    _(
                        "Only Char and Text fields can be encrypted. '%(field)s' is a %(ttype)s field.",
                        field=record.field_id.name,
                        ttype=record.field_id.ttype,
                    )
                )

    @api.model
    def get_encrypted_fields(self, model_name):
        """Get list of encrypted field names for a model.

        This method is called by the encrypted field mixin to determine
        which fields should be encrypted.

        Args:
            model_name: The model technical name (e.g., 'res.partner')

        Returns:
            list: Field names that should be encrypted
        """
        configs = self.search(
            [
                ("model_name", "=", model_name),
                ("encryption_enabled", "=", True),
                ("active", "=", True),
            ]
        )
        return configs.mapped("field_name")

    @api.model
    def get_field_config(self, model_name, field_name):
        """Get encryption configuration for a specific field.

        Args:
            model_name: The model technical name
            field_name: The field name

        Returns:
            spp.field.encryption.config record or empty recordset
        """
        return self.search(
            [
                ("model_name", "=", model_name),
                ("field_name", "=", field_name),
                ("active", "=", True),
            ],
            limit=1,
        )

    @api.model
    def is_field_encrypted(self, model_name, field_name):
        """Check if a field is configured for encryption.

        Args:
            model_name: The model technical name
            field_name: The field name

        Returns:
            bool: True if field should be encrypted
        """
        config = self.get_field_config(model_name, field_name)
        return bool(config and config.encryption_enabled)

    @api.model
    def get_index_type(self, model_name, field_name):
        """Get the blind index type for a field.

        Args:
            model_name: The model technical name
            field_name: The field name

        Returns:
            str: Index type ('exact', 'partial', 'phonetic') or None
        """
        config = self.get_field_config(model_name, field_name)
        if config and config.blind_index_enabled:
            return config.index_type
        return None

    def action_toggle_encryption(self):
        """Toggle encryption for this field."""
        for record in self:
            record.encryption_enabled = not record.encryption_enabled

    def action_toggle_blind_index(self):
        """Toggle blind index for this field."""
        for record in self:
            record.blind_index_enabled = not record.blind_index_enabled
