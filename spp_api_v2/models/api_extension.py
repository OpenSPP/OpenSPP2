# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""API Extension Registry Model"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApiExtension(models.Model):
    """
    Registry for API V2 extensions.

    Extensions are registered by domain modules (e.g., spp_farmer_registry)
    to expose their custom fields via the API.
    """

    _name = "spp.api.extension"
    _description = "API Extension Registry"

    name = fields.Char(required=True, help="Human-readable name for this extension")

    url = fields.Char(
        required=True,
        help="URN for this extension, e.g., urn:openspp:extension:farmer",
    )

    module_id = fields.Many2one(
        "ir.module.module",
        required=True,
        domain=[("state", "=", "installed")],
        ondelete="cascade",
        help="Module that provides this extension",
    )

    applies_to = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
            ("both", "Individual and Group"),
        ],
        required=True,
        help="Which resource types this extension applies to",
    )

    # Fields provided by this extension
    field_ids = fields.Many2many(
        "ir.model.fields",
        string="Extension Fields",
        help="Odoo fields that should be exposed in this extension",
    )

    # JSON Schema for the extension (optional, for documentation)
    schema_json = fields.Text(
        help="JSON Schema definition for this extension (optional)",
    )

    # Is this extension active?
    active = fields.Boolean(default=True)

    _unique_url = models.Constraint("UNIQUE(url)", "Extension URL must be unique")

    @api.model
    def get_extensions_for_resource(self, resource_type):
        """
        Get all active extensions for a resource type.

        Args:
            resource_type: 'individual' or 'group'

        Returns:
            Recordset of spp.api.extension records
        """
        domain = [
            ("active", "=", True),
            ("module_id.state", "=", "installed"),
        ]

        if resource_type == "individual":
            domain.append(("applies_to", "in", ("individual", "both")))
        elif resource_type == "group":
            domain.append(("applies_to", "in", ("group", "both")))
        else:
            _logger.warning("Unknown resource type: %s", resource_type)
            return self.env["spp.api.extension"]

        return self.sudo().search(  # nosemgrep: odoo-sudo-without-context - API extensions are configuration records; sudo() is used to read active extensions regardless of caller ACLs.
            domain
        )

    def get_field_names(self):
        """
        Get list of field names for this extension.

        Returns:
            List of field names (strings)
        """
        self.ensure_one()
        return [field.name for field in self.field_ids]
