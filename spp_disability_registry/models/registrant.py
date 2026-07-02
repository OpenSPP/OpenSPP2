import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # === Assessment History ===
    disability_assessment_ids = fields.One2many(
        "spp.disability.assessment",
        "registrant_id",
        string="Disability Assessments",
    )
    disability_assessment_count = fields.Integer(
        string="Assessment Count",
        compute="_compute_disability_assessment_count",
    )

    # === Current Status (from latest approved assessment) ===
    current_disability_assessment_id = fields.Many2one(
        "spp.disability.assessment",
        string="Current Assessment",
        compute="_compute_current_disability_assessment",
        store=True,
    )
    has_disability = fields.Boolean(
        string="Has Disability",
        related="current_disability_assessment_id.has_disability",
        store=True,
        readonly=True,
    )
    disability_severity_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Disability Severity",
        related="current_disability_assessment_id.severity_level_id",
        store=True,
        readonly=True,
    )
    disability_review_category = fields.Selection(
        related="current_disability_assessment_id.review_category",
        store=True,
        readonly=True,
    )
    disability_next_review = fields.Date(
        string="Next Review Date",
        related="current_disability_assessment_id.next_review_date",
        store=True,
        readonly=True,
    )

    # === Assistive Devices ===
    assistive_device_ids = fields.One2many(
        "spp.assistive.device",
        "registrant_id",
        string="Assistive Devices",
    )
    assistive_device_count = fields.Integer(
        string="Device Count",
        compute="_compute_assistive_device_count",
    )
    has_unmet_device_need = fields.Boolean(
        string="Has Unmet Device Need",
        compute="_compute_unmet_device_need",
        store=True,
    )

    def _compute_disability_assessment_count(self):
        for rec in self:
            rec.disability_assessment_count = len(rec.disability_assessment_ids)

    @api.depends(
        "disability_assessment_ids",
        "disability_assessment_ids.approval_state",
        "disability_assessment_ids.assessment_date",
    )
    def _compute_current_disability_assessment(self):
        for rec in self:
            approved_assessments = rec.disability_assessment_ids.filtered(
                lambda a: a.approval_state == "approved"
            ).sorted("assessment_date", reverse=True)
            rec.current_disability_assessment_id = approved_assessments[:1]

    def _compute_assistive_device_count(self):
        for rec in self:
            rec.assistive_device_count = len(rec.assistive_device_ids)

    @api.depends("assistive_device_ids", "assistive_device_ids.status")
    def _compute_unmet_device_need(self):
        for rec in self:
            rec.has_unmet_device_need = any(d.status == "needed" for d in rec.assistive_device_ids)

    def action_view_disability_assessments(self):
        """Open disability assessments for this registrant."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Disability Assessments",
            "res_model": "spp.disability.assessment",
            "view_mode": "list,form",
            "domain": [("registrant_id", "=", self.id)],
            "context": {"default_registrant_id": self.id},
        }

    def action_view_assistive_devices(self):
        """Open assistive devices for this registrant."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Assistive Devices",
            "res_model": "spp.assistive.device",
            "view_mode": "list,form",
            "domain": [("registrant_id", "=", self.id)],
            "context": {"default_registrant_id": self.id},
        }

    def action_create_disability_assessment(self):
        """Create a new disability assessment for this registrant."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "New Disability Assessment",
            "res_model": "spp.disability.assessment",
            "view_mode": "form",
            "context": {"default_registrant_id": self.id},
            "target": "current",
        }
