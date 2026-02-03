# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import models


class SPPGRMDemoWizard(models.TransientModel):
    _name = "spp.grm.demo.wizard"
    _inherit = "spp.grm.demo.generator"
    _description = "GRM Demo Data Wizard"

    # Inherits all fields and methods from spp.grm.demo.generator
    # This provides a clean separation between the generator logic
    # and the wizard interface
