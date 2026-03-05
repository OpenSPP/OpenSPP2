"""Case Visit Model."""

from odoo import api, fields, models


class CaseVisit(models.Model):
    """Visits and contacts with case clients."""

    _name = "spp.case.visit"
    _description = "Case Visit"
    _order = "visit_date desc"

    case_id = fields.Many2one(
        "spp.case",
        string="Case",
        required=True,
        ondelete="cascade",
    )

    visit_date = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
    )

    visit_type = fields.Selection(
        [
            ("home", "Home Visit"),
            ("office", "Office Visit"),
            ("phone", "Phone Call"),
            ("virtual", "Virtual Meeting"),
        ],
        required=True,
        default="office",
    )

    duration_minutes = fields.Integer(
        string="Duration (Minutes)",
        help="Duration of the visit in minutes",
    )

    purpose = fields.Char(
        help="Main purpose or objective of the visit",
    )

    notes = fields.Html(
        string="Visit Notes",
        help="Detailed notes from the visit",
    )

    attendee_ids = fields.Many2many(
        "res.partner",
        "case_visit_attendee_rel",
        "visit_id",
        "partner_id",
        string="Attendees",
        help="People who attended the visit",
    )

    conducted_by_id = fields.Many2one(
        "res.users",
        string="Conducted By",
        required=True,
        default=lambda self: self.env.user,
    )

    # Related fields for easy access
    case_worker_id = fields.Many2one(
        "res.users",
        string="Case Worker",
        related="case_id.case_worker_id",
        store=True,
        readonly=True,
    )

    client_id = fields.Many2one(
        "res.partner",
        string="Client",
        related="case_id.partner_id",
        store=True,
        readonly=True,
    )

    # Computed fields
    visit_date_display = fields.Char(
        string="Visit Date",
        compute="_compute_visit_date_display",
        store=False,
    )

    def _compute_visit_date_display(self):
        """Format visit date for display."""
        for visit in self:
            if visit.visit_date:
                visit.visit_date_display = fields.Datetime.to_string(visit.visit_date)
            else:
                visit.visit_date_display = ""

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to add default attendee."""
        visits = super().create(vals_list)
        # Add client as default attendee if not already added
        for visit in visits:
            if visit.case_id.partner_id and visit.case_id.partner_id not in visit.attendee_ids:
                visit.attendee_ids = [(4, visit.case_id.partner_id.id)]
        return visits

    def _compute_display_name(self):
        """Compute display name for visits."""
        visit_type_labels = dict(self._fields["visit_type"].selection)
        for visit in self:
            type_label = visit_type_labels.get(visit.visit_type, visit.visit_type)
            if visit.visit_date and visit.client_id:
                date_str = visit.visit_date.strftime("%b %d, %Y")
                visit.display_name = f"{type_label} - {date_str} - {visit.client_id.name}"
            elif visit.visit_date:
                date_str = visit.visit_date.strftime("%b %d, %Y")
                visit.display_name = f"{type_label} - {date_str}"
            else:
                visit.display_name = type_label
