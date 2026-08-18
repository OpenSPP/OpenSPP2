# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Add program selection to the Logic Pack install wizard.

Re-opens ``spp.studio.pack.install.wizard`` to add the optional ``program_id``
used for constant-value lookups during pack expansion, and supplies it through
the ``_get_pack_program_id`` hook defined on the base wizard (OP#1083).
"""

from odoo import fields, models


class PackInstallWizard(models.TransientModel):
    _inherit = "spp.studio.pack.install.wizard"

    program_id = fields.Many2one(
        "spp.program",
        string="Program",
        help="Optional: Program for constant value lookups",
    )

    def _get_pack_program_id(self):
        """Use the selected program for constant-value lookups."""
        self.ensure_one()
        return self.program_id.id if self.program_id else None
