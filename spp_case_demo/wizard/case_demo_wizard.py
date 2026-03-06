# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import models


class SPPCaseDemoWizard(models.TransientModel):
    _name = "spp.case.demo.wizard"
    _inherit = "spp.case.demo.generator"
    _description = "Case Management Demo Data Wizard"

    # Inherits all fields and methods from spp.case.demo.generator
    # This provides a clean separation between the generator logic
    # and the wizard interface
