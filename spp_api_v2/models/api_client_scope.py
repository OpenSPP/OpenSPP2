# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ApiClientScope(models.Model):
    """Scope/permission for an API client"""

    _name = "spp.api.client.scope"
    _description = "API Client Scope"
    _order = "client_id, resource, action"

    client_id = fields.Many2one(
        "spp.api.client",
        required=True,
        ondelete="cascade",
        index=True,
    )

    resource = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
            ("program", "Program"),
            ("program_membership", "Program Membership"),
            ("identifier", "Identifier"),
        ],
        required=True,
        ondelete={
            "individual": "cascade",
            "group": "cascade",
            "program": "cascade",
            "program_membership": "cascade",
            "identifier": "cascade",
        },
    )

    action = fields.Selection(
        [
            ("read", "Read Single"),
            ("search", "Search/List"),
            ("create", "Create"),
            ("update", "Update"),
            ("delete", "Delete"),
            ("all", "All Actions"),
        ],
        required=True,
        ondelete={
            "read": "cascade",
            "search": "cascade",
            "create": "cascade",
            "update": "cascade",
            "delete": "cascade",
            "all": "cascade",
        },
    )

    # Field-level restrictions
    field_filter_ids = fields.Many2many(
        "ir.model.fields",
        string="Allowed Fields",
        help="If empty, all fields are allowed. Otherwise, only listed fields.",
    )

    description = fields.Text()

    @api.constrains("client_id", "resource", "action")
    def _check_unique_scope(self):
        """Ensure no duplicate scope definition for a client."""
        for record in self:
            if not record.client_id or not record.resource or not record.action:
                continue

            domain = [
                ("client_id", "=", record.client_id.id),
                ("resource", "=", record.resource),
                ("action", "=", record.action),
                ("id", "!=", record.id),
            ]
            if self.search(domain, limit=1):
                raise ValidationError(
                    _("Duplicate scope definition for this client. " "The scope '%s:%s' already exists.")
                    % (record.resource, record.action)
                )

    def name_get(self):
        """Display scope as 'resource:action'"""
        result = []
        for rec in self:
            name = f"{rec.resource}:{rec.action}"
            result.append((rec.id, name))
        return result
