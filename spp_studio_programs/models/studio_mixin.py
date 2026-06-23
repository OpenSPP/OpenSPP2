# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Add program-scoping to Studio configurations.

Re-opens ``spp.studio.mixin`` to add the optional ``program_ids`` link, so
Studio configs (fields, logic variables) can be scoped to specific programs.
This lives in the companion so the base ``spp_studio`` module does not depend
on ``spp_programs`` (OP#1083).
"""

from odoo import fields, models


class StudioMixin(models.AbstractModel):
    _inherit = "spp.studio.mixin"

    program_ids = fields.Many2many(
        "spp.program",
        string="Programs",
        help="If set, this configuration is only visible in these programs. Leave empty for global visibility.",
    )
