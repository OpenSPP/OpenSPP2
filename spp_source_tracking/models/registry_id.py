# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import models


class SPPRegistrantID(models.Model):
    """Extend spp.registry.id with source tracking capabilities."""

    _name = "spp.registry.id"
    _inherit = ["spp.registry.id", "spp.mixin.source.tracking"]
