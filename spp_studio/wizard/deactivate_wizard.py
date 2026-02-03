"""Deactivation confirmation wizard for Studio configurations."""

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StudioDeactivateWizard(models.TransientModel):
    """Wizard to confirm deactivation with impact warning."""

    _name = "spp.studio.deactivate.wizard"
    _description = "Studio Deactivation Wizard"

    config_model = fields.Char(
        string="Configuration Model",
        required=True,
        default=lambda self: self.env.context.get("default_config_model"),
        help="Model name of the configuration being deactivated",
    )
    config_id = fields.Integer(
        string="Configuration ID",
        required=True,
        default=lambda self: self.env.context.get("default_config_id"),
        help="ID of the configuration record",
    )
    config_name = fields.Char(
        string="Configuration Name",
        compute="_compute_config_info",
        help="Display name of the configuration",
    )
    config_type = fields.Char(
        string="Configuration Type",
        compute="_compute_config_info",
        help="Type of configuration (Field, Event Type, etc.)",
    )
    impact_message = fields.Text(
        string="Impact Warning",
        required=True,
        default=lambda self: self.env.context.get("default_impact_message"),
        help="Description of what will be affected by this deactivation",
    )
    record_count = fields.Integer(
        string="Affected Records",
        compute="_compute_config_info",
        help="Number of records that will be affected",
    )

    def _compute_config_info(self):
        """Compute configuration details from model and ID."""
        for wizard in self:
            # Always compute record_count from impact_message
            wizard.record_count = wizard._extract_record_count(wizard.impact_message)

            if not wizard.config_model or not wizard.config_id:
                wizard.config_name = ""
                wizard.config_type = ""
                continue

            try:
                config = self.env[wizard.config_model].browse(wizard.config_id)
                if config.exists():
                    wizard.config_name = config.display_name
                    # Check if model has _get_studio_config_type method
                    if hasattr(config, "_get_studio_config_type"):
                        wizard.config_type = config._get_studio_config_type()
                    else:
                        # Fallback: derive type from model name
                        wizard.config_type = wizard.config_model.replace(".", " ").title()
                else:
                    wizard.config_name = _("(Record not found)")
                    wizard.config_type = ""
            except Exception as e:
                _logger.warning(
                    "Failed to compute config info for %s[%s]: %s",
                    wizard.config_model,
                    wizard.config_id,
                    e,
                )
                wizard.config_name = _("(Error loading record)")
                wizard.config_type = ""

    def _extract_record_count(self, message):
        """Extract record count from impact message."""
        import re

        if not message:
            return 0

        # Look for patterns like "1,247 records", "5 event record(s)", or "3 requests"
        matches = re.findall(r"(\d+(?:,\d+)*)\s+(?:record|event|request)", message)
        if matches:
            # Remove commas and convert to int
            count_str = matches[0].replace(",", "")
            try:
                return int(count_str)
            except ValueError:
                return 0
        return 0

    def action_confirm_deactivate(self):
        """Confirm and proceed with deactivation."""
        self.ensure_one()

        if not self.config_model or not self.config_id:
            raise UserError(_("Invalid configuration reference."))

        try:
            config = self.env[self.config_model].browse(self.config_id)
            if not config.exists():
                raise UserError(_("Configuration record not found. It may have been deleted."))

            # Call the actual deactivation method
            config._do_deactivate()

            _logger.info(
                "User confirmed deactivation of %s[%s] with %d affected records",
                self.config_model,
                self.config_id,
                self.record_count,
            )

            return {"type": "ir.actions.act_window_close"}

        except Exception as e:
            _logger.error(
                "Failed to deactivate %s[%s]: %s",
                self.config_model,
                self.config_id,
                e,
            )
            raise UserError(_("Failed to deactivate configuration: %(error)s", error=str(e))) from e

    def action_cancel(self):
        """Cancel deactivation."""
        self.ensure_one()
        _logger.info(
            "User cancelled deactivation of %s[%s]",
            self.config_model,
            self.config_id,
        )
        return {"type": "ir.actions.act_window_close"}
