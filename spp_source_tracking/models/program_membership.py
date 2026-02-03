# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import models


class SPPProgramMembership(models.Model):
    """Extend spp.program.membership with source tracking capabilities."""

    _name = "spp.program.membership"
    _inherit = ["spp.program.membership", "spp.mixin.source.tracking"]
