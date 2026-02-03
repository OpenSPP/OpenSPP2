# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DPV-aligned Processing Operations.

Based on W3C Data Privacy Vocabulary (DPV) processing taxonomy.
See: https://w3id.org/dpv#Processing
"""

from odoo import fields, models


class ConsentProcessing(models.Model):
    """
    Processing operations covered by consent - aligned with W3C DPV.

    Defines what operations (collect, store, share, etc.) are permitted
    under a consent.
    """

    _name = "spp.consent.processing"
    _description = "Processing Operation (DPV-aligned)"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Unique code (e.g., 'Collect', 'Store', 'Share')",
    )
    description = fields.Text(translate=True)

    # DPV alignment
    dpv_uri = fields.Char(
        string="DPV URI",
        help="W3C DPV URI (e.g., 'https://w3id.org/dpv#Collect')",
    )
    dpv_concept = fields.Char(
        string="DPV Concept",
        help="DPV concept name (e.g., 'dpv:Collect')",
    )

    # Classification
    category = fields.Selection(
        [
            ("obtain", "Obtain"),  # Collect, Generate, Observe
            ("store", "Store"),  # Store, Record
            ("use", "Use"),  # Use, Analyse, Consult
            ("disclose", "Disclose"),  # Share, Transmit, Disseminate
            ("remove", "Remove"),  # Delete, Destroy, Erase
        ],
        required=True,
        help="DPV processing category",
    )

    # Risk level
    risk_level = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        default="low",
        help="Risk level associated with this processing",
    )

    # UI
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint("UNIQUE(code)", "Processing code must be unique")
