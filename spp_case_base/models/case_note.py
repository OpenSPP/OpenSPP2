"""Case Note Model."""

from odoo import _, api, fields, models


class CaseNote(models.Model):
    """Notes and documentation for cases."""

    _name = "spp.case.note"
    _description = "Case Note"
    _order = "note_date desc"

    case_id = fields.Many2one(
        "spp.case",
        string="Case",
        required=True,
        ondelete="cascade",
    )

    note_date = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
    )

    author_id = fields.Many2one(
        "res.users",
        string="Author",
        required=True,
        default=lambda self: self.env.user,
    )

    note_type = fields.Selection(
        [
            ("general", "General Note"),
            ("assessment", "Assessment"),
            ("progress", "Progress Update"),
            ("supervision", "Supervision Note"),
        ],
        required=True,
        default="general",
    )

    content = fields.Html(
        required=True,
    )

    is_confidential = fields.Boolean(
        string="Confidential",
        default=False,
        help="Mark this note as confidential (restricted access)",
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
    note_date_display = fields.Char(
        string="Date",
        compute="_compute_note_date_display",
        store=False,
    )

    def _compute_note_date_display(self):
        """Format note date for display."""
        for note in self:
            if note.note_date:
                note.note_date_display = fields.Datetime.to_string(note.note_date)
            else:
                note.note_date_display = ""

    def _compute_display_name(self):
        """Compute display name for notes."""
        note_type_labels = dict(self._fields["note_type"].selection)
        for note in self:
            type_label = note_type_labels.get(note.note_type, note.note_type)
            if note.note_date and note.client_id:
                date_str = note.note_date.strftime("%b %d, %Y")
                note.display_name = f"{type_label} - {date_str} - {note.client_id.name}"
            elif note.note_date:
                date_str = note.note_date.strftime("%b %d, %Y")
                note.display_name = f"{type_label} - {date_str}"
            else:
                note.display_name = type_label

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to log note creation."""
        notes = super().create(vals_list)
        # Post message to case chatter
        for note in notes:
            if note.case_id:
                note_type_label = dict(note._fields["note_type"].selection).get(note.note_type)
                note.case_id.message_post(
                    body=_("New %(type)s added by %(author)s", type=note_type_label, author=note.author_id.name),
                    subject=_("Case Note: %(type)s", type=note_type_label),
                )
        return notes
