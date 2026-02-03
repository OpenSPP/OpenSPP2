# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DPV-aligned Consent Purpose taxonomy.

Based on W3C Data Privacy Vocabulary (DPV) purpose hierarchy.
See: https://w3id.org/dpv#Purpose
"""

from odoo import api, fields, models


class ConsentPurpose(models.Model):
    """
    Purpose for data processing - aligned with W3C DPV.

    Implements hierarchical purpose taxonomy from DPV.
    Social protection-specific purposes extend the base DPV concepts.
    """

    _name = "spp.consent.purpose"
    _description = "Consent Purpose (DPV-aligned)"
    _order = "sequence, name"
    _parent_store = True

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Unique code for this purpose (e.g., 'ServiceProvision')",
    )
    description = fields.Text(translate=True)

    # DPV alignment
    dpv_uri = fields.Char(
        string="DPV URI",
        help="W3C DPV URI (e.g., 'https://w3id.org/dpv#ServiceProvision')",
    )
    dpv_concept = fields.Char(
        string="DPV Concept",
        help="DPV concept name (e.g., 'dpv:ServiceProvision')",
    )

    # Hierarchy
    parent_id = fields.Many2one(
        "spp.consent.purpose",
        string="Parent Purpose",
        ondelete="cascade",
        index=True,
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        "spp.consent.purpose",
        "parent_id",
        string="Child Purposes",
    )

    # Classification
    is_social_protection = fields.Boolean(
        string="Social Protection Specific",
        help="Purpose specific to social protection (extends DPV)",
    )
    requires_explicit_consent = fields.Boolean(
        default=True,
        help="Whether this purpose requires explicit consent",
    )

    # UI
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint("UNIQUE(code)", "Purpose code must be unique")

    def name_get(self):
        """Display full path for hierarchical purposes"""
        result = []
        for rec in self:
            if rec.parent_id:
                name = f"{rec.parent_id.name} / {rec.name}"
            else:
                name = rec.name
            result.append((rec.id, name))
        return result

    @api.model
    def get_dpv_purposes(self):
        """Return purposes that have DPV alignment"""
        return self.search([("dpv_uri", "!=", False)])
