import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SppAssistiveDevice(models.Model):
    _name = "spp.assistive.device"
    _description = "Assistive Device"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(
        compute="_compute_name",
        store=True,
        readonly=True,
    )
    registrant_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        required=True,
        index=True,
        domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
        ondelete="cascade",
    )
    device_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Device Type",
        required=True,
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:dci:cd:dr:04')]",
        tracking=True,
    )
    status = fields.Selection(
        [
            ("needed", "Needed"),
            ("requested", "Requested"),
            ("provided", "Provided"),
        ],
        string="Status",
        default="needed",
        required=True,
        tracking=True,
    )
    provision_date = fields.Date(
        string="Provision Date",
        help="Date when the device was provided",
    )
    provider = fields.Char(
        string="Provider",
        help="Organization or entity that provided the device",
    )
    notes = fields.Text(
        string="Notes",
    )

    @api.depends("registrant_id", "device_type_id")
    def _compute_name(self):
        for rec in self:
            registrant_name = rec.registrant_id.name if rec.registrant_id else "Unknown"
            device_name = rec.device_type_id.display if rec.device_type_id else "Device"
            rec.name = f"{registrant_name} - {device_name}"

    @api.onchange("status")
    def _onchange_status(self):
        """Clear provision date if status is not 'provided'."""
        if self.status != "provided":
            self.provision_date = False

    def action_view_registrant(self):
        """Open the registrant form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": self.registrant_id.id,
            "view_mode": "form",
            "target": "current",
        }


class SppDisabilityAssessmentDeviceRequest(models.Model):
    """Assistive-device request captured on an assessment's Support Needs tab.

    Status is always "Needed" (read-only). On assessment approval each row
    creates a real ``spp.assistive.device`` (status "needed") on the registrant,
    so it surfaces on the Overview / registrant (OP#1068).
    """

    _name = "spp.disability.assessment.device.request"
    _description = "Assessment Assistive Device Request"

    assessment_id = fields.Many2one(
        "spp.disability.assessment",
        string="Assessment",
        required=True,
        index=True,
        ondelete="cascade",
    )
    device_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Device Type",
        required=True,
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:dci:cd:dr:04')]",
    )
    # Always "Needed" — these are requests; the registrant's device record is
    # what later moves to requested/provided.
    status = fields.Selection(
        [("needed", "Needed")],
        string="Status",
        default="needed",
        readonly=True,
    )
    notes = fields.Text(string="Notes")
