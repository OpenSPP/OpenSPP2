# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class DrimsPersonnel(models.Model):
    """Deployed Personnel tracking for disaster response.

    Tracks field staff, volunteers, and team members deployed
    across different areas during disaster response operations.
    """

    _name = "spp.drims.personnel"
    _description = "Deployed Personnel"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "deployment_date desc, name"

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
        help="Link to existing individual registrant (optional)",
    )
    organization_id = fields.Many2one(
        "res.partner",
        string="Organization",
        domain="[('is_drims_organization', '=', True)]",
        context={
            "default_is_company": True,
            "default_is_drims_organization": True,
            "default_is_registrant": False,
            "form_view_ref": "spp_drims.view_drims_organization_form",
        },
        tracking=True,
        help="Deploying organization",
    )
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        required=True,
        tracking=True,
        index=True,
    )
    deployment_area_id = fields.Many2one(
        "spp.area",
        string="Deployment Area",
        tracking=True,
        help="Geographic area where personnel is deployed",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Base Warehouse",
        domain="[('is_drims_warehouse', '=', True)]",
        help="Primary warehouse base for this personnel",
    )
    role_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:personnel-roles')]",
        tracking=True,
    )
    cluster_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Cluster",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:ocha:iasc:clusters')]",
        help="OCHA/IASC humanitarian cluster assignment",
    )

    # Contact Information
    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")
    radio_callsign = fields.Char(string="Radio Callsign")

    # Deployment Details
    deployment_date = fields.Date(
        string="Deployment Date",
        default=fields.Date.today,
        tracking=True,
    )
    expected_return_date = fields.Date(
        string="Expected Return",
    )
    actual_return_date = fields.Date(
        string="Actual Return",
        tracking=True,
    )
    status = fields.Selection(
        selection=[
            ("deployed", "Deployed"),
            ("standby", "Standby"),
            ("on_leave", "On Leave"),
            ("returned", "Returned"),
        ],
        string="Status",
        default="deployed",
        required=True,
        tracking=True,
    )

    # Skills and Certifications
    skills = fields.Text(
        string="Skills/Certifications",
        help="Relevant skills, certifications, and qualifications",
    )
    languages = fields.Char(
        string="Languages",
        help="Languages spoken (e.g., Sinhala, Tamil, English)",
    )

    notes = fields.Text(string="Notes")

    # Computed Fields
    days_deployed = fields.Integer(
        string="Days Deployed",
        compute="_compute_days_deployed",
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("name", "role_id", "organization_id")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name]
            if rec.role_id:
                parts.append(f"({rec.role_id.display})")
            if rec.organization_id:
                parts.append(f"- {rec.organization_id.name}")
            rec.display_name = " ".join(parts)

    @api.depends("deployment_date", "actual_return_date", "status")
    def _compute_days_deployed(self):
        today = fields.Date.today()
        for rec in self:
            if rec.deployment_date:
                end_date = rec.actual_return_date or today
                rec.days_deployed = (end_date - rec.deployment_date).days
            else:
                rec.days_deployed = 0

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Auto-fill contact details from partner."""
        if self.partner_id:
            self.name = self.name or self.partner_id.name
            self.phone = self.phone or self.partner_id.phone
            self.email = self.email or self.partner_id.email

    def action_mark_returned(self):
        """Mark personnel as returned."""
        self.write(
            {
                "status": "returned",
                "actual_return_date": fields.Date.today(),
            }
        )

    def action_mark_deployed(self):
        """Mark personnel as deployed."""
        self.write(
            {
                "status": "deployed",
                "actual_return_date": False,
            }
        )

    def action_mark_on_leave(self):
        """Mark personnel as on leave (GAP-PER-001)."""
        self.write({"status": "on_leave"})

    def action_mark_standby(self):
        """Mark personnel as standby."""
        self.write({"status": "standby"})
