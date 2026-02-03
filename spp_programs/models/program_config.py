# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProgramConfig(models.TransientModel):
    _name = "spp.program.settings"
    _inherit = "res.config.settings"
    _description = "Program Settings"

    # Field Definitions
    default_eligibility_manager_ids = fields.Many2many(
        "spp.eligibility.manager",
        string="Eligibility Managers",
        default_model="spp.program",
    )
    deduplication_manager_ids = fields.Many2many(
        "spp.deduplication.manager",
        default_model="spp.program",
    )
    notification_manager_ids = fields.Many2many(
        "spp.program.notification.manager",
        default_model="spp.program",
    )
    program_manager_ids = fields.Many2many("spp.program.manager", default_model="spp.program")
    cycle_manager_ids = fields.Many2many("spp.cycle.manager", default_model="spp.program")
    entitlement_manager_ids = fields.Many2many(
        "spp.program.entitlement.manager",
        default_model="spp.program",
    )
