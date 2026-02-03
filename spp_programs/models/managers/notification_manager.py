# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class Notification(models.Model):
    _name = "spp.program.notification.manager"
    _description = "Program Notification Manager"
    _inherit = "spp.manager.mixin"

    program_id = fields.Many2one("spp.program", "Program", ondelete="cascade")

    @api.model
    def _selection_manager_ref_id(self):
        selection = super()._selection_manager_ref_id()
        # SMS notification manager requires 'sms' module - moved to spp_programs_sms bridge module
        return selection


class BaseNotificationManager(models.AbstractModel):
    """
    This component is used to notify beneficiaries of their enrollment and other events related to the program
    """

    _name = "spp.base.program.notification.manager"
    _description = "Base Program Notification Manager"

    name = fields.Char("Manager Name", required=True)
    program_id = fields.Many2one("spp.program", string="Program", required=True)
    is_on_enrolled_in_program = fields.Boolean(default=True)
    is_on_cycle_started = fields.Boolean(default=True)
    is_on_cycle_ended = fields.Boolean(default=True)


# NOTE: SMS notification functionality has been removed from this module.
# It requires the 'sms' module which is an optional dependency.
# TODO: Create spp_programs_sms bridge module to provide SMS notification support
# when the sms module is installed. The bridge module should define:
# - SMSNotificationManager (spp.program.notification.manager.sms)
# - SMSTemplate extension (sms.template with spp_sms_id field)
