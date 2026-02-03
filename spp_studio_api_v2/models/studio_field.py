# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend Studio Field with API auto-registration."""

import logging

from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)

# Mapping from target_type to extension XML ID
EXTENSION_MAPPING = {
    "individual": "spp_studio_api_v2.api_extension_studio_individual",
    "group": "spp_studio_api_v2.api_extension_studio_group",
}


class StudioFieldAPI(models.Model):
    """Extend Studio Field with automatic API extension registration."""

    _inherit = "spp.studio.field"

    api_exposed = fields.Boolean(
        string="Expose via API",
        default=True,
        help="Include this field in API v2 responses and allow updates via API",
    )

    def _post_activate(self):
        """Register field in API extension after activation."""
        super()._post_activate()

        for record in self:
            if record.api_exposed and record.ir_model_fields_id:
                record._register_api_extension()

    def _post_deactivate(self):
        """Unregister field from API extension when deactivated."""
        super()._post_deactivate()

        for record in self:
            if record.ir_model_fields_id:
                record._unregister_api_extension()

    def _register_api_extension(self):
        """Add this field to the appropriate Studio API extension."""
        self.ensure_one()

        if not self.ir_model_fields_id:
            _logger.warning(
                "Cannot register Studio field '%s' in API: no ir.model.fields record",
                self.label,
            )
            return

        extension = self._get_studio_extension()
        if not extension:
            _logger.warning(
                "Cannot find Studio API extension for target_type='%s'",
                self.target_type,
            )
            return

        # Add field to extension if not already present
        if self.ir_model_fields_id not in extension.field_ids:
            # sudo() required: Extension registration is system-level config,
            # done during field activation regardless of user permissions.
            extension.sudo().write(
                {
                    "field_ids": [Command.link(self.ir_model_fields_id.id)],
                }
            )
            _logger.info(
                "Registered Studio field '%s' (%s) in API extension '%s'",
                self.label,
                self.technical_name,
                extension.url,
            )

    def _unregister_api_extension(self):
        """Remove this field from the Studio API extension."""
        self.ensure_one()

        if not self.ir_model_fields_id:
            return

        extension = self._get_studio_extension()
        if not extension:
            return

        # Remove field from extension
        if self.ir_model_fields_id in extension.field_ids:
            # sudo() required: Extension registration is system-level config,
            # done during field deactivation regardless of user permissions.
            extension.sudo().write(
                {
                    "field_ids": [Command.unlink(self.ir_model_fields_id.id)],
                }
            )
            _logger.info(
                "Unregistered Studio field '%s' (%s) from API extension '%s'",
                self.label,
                self.technical_name,
                extension.url,
            )

    def _get_studio_extension(self):
        """Get the Studio API extension for this field's target_type."""
        ext_xmlid = EXTENSION_MAPPING.get(self.target_type)
        if not ext_xmlid:
            return None

        try:
            return self.env.ref(ext_xmlid)
        except ValueError:
            _logger.warning("API extension '%s' not found", ext_xmlid)
            return None

    def write(self, vals):
        """Handle api_exposed changes."""
        result = super().write(vals)

        # If api_exposed changed on active fields, update registration
        if "api_exposed" in vals:
            for record in self:
                if record.state == "active" and record.ir_model_fields_id:
                    if vals["api_exposed"]:
                        record._register_api_extension()
                    else:
                        record._unregister_api_extension()

        return result

    @api.model
    def _register_existing_fields(self):
        """Migration helper: register all existing active fields with api_exposed=True.

        Call this after module installation to register pre-existing fields.
        """
        active_fields = self.search(
            [
                ("state", "=", "active"),
                ("api_exposed", "=", True),
                ("ir_model_fields_id", "!=", False),
            ]
        )

        registered = 0
        for field in active_fields:
            try:
                field._register_api_extension()
                registered += 1
            except Exception as e:
                _logger.warning(
                    "Failed to register existing field '%s': %s",
                    field.label,
                    e,
                )

        _logger.info("Registered %d existing Studio fields in API extensions", registered)
        return registered
