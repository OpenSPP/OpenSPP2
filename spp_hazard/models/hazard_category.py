# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HazardCategory(models.Model):
    """
    Represents a hazard category in the OpenSPP system.

    This model defines the structure and behavior of hazard types,
    including their hierarchical relationships. Categories can be
    organized in a tree structure (e.g., Natural → Storm → Typhoon).
    """

    _name = "spp.hazard.category"
    _description = "Hazard Category"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "complete_name"
    _order = "parent_id,name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Unique system code (e.g., NAT_STORM_TYPHOON)",
    )
    description = fields.Text(translate=True)
    parent_id = fields.Many2one(
        "spp.hazard.category",
        string="Parent Category",
        index=True,
        ondelete="restrict",
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        "spp.hazard.category",
        "parent_id",
        string="Subcategories",
    )
    complete_name = fields.Char(
        compute="_compute_complete_name",
        recursive=True,
        store=True,
        translate=True,
    )
    active = fields.Boolean(
        default=True,
        help="Enable or disable this category",
    )
    incident_ids = fields.One2many(
        "spp.hazard.incident",
        "category_id",
        string="Incidents",
    )
    incident_count = fields.Integer(
        compute="_compute_incident_count",
        string="Number of Incidents",
    )

    _code_unique = models.Constraint(
        "unique (code)",
        "A hazard category with this code already exists!",
    )

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        """
        Compute the complete hierarchical name of the category.

        The complete name includes the parent's complete name (if any)
        and the category's own name, separated by ' > '.
        """
        for rec in self:
            if rec.parent_id:
                rec.complete_name = f"{rec.parent_id.complete_name} > {rec.name}"
            else:
                rec.complete_name = rec.name

    @api.depends("incident_ids")
    def _compute_incident_count(self):
        """Compute the number of incidents linked to this category."""
        for rec in self:
            rec.incident_count = len(rec.incident_ids)

    def action_view_incidents(self):
        """Open a list view of incidents for this category."""
        self.ensure_one()
        return {
            "name": self.name,
            "type": "ir.actions.act_window",
            "res_model": "spp.hazard.incident",
            "view_mode": "list,form",
            "domain": [("category_id", "=", self.id)],
            "context": {"default_category_id": self.id},
        }
