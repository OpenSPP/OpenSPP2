from odoo import api, fields, models


class DCIFetchAudit(models.Model):
    """One row per DCI external fetch attempt.

    Captures provenance for compliance: which provider was queried, for which
    subject, on whose behalf, with what outcome. Reusing spp.audit.log was
    rejected (ADR-023 §6.4) because that model is CRUD-shaped and would
    require synthetic rules to record non-CRUD events.

    A scheduled action prunes rows older than the value of the system
    parameter spp_cel_dci_bridge.audit_retention_days (default 90).
    """

    _name = "spp.dci.fetch.audit"
    _description = "DCI External Fetch Audit"
    _order = "create_date desc"

    create_date = fields.Datetime(readonly=True)
    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        readonly=True,
    )

    provider_code = fields.Char(required=True, index=True)
    data_source_code = fields.Char(required=True, index=True)
    registry_type = fields.Char(required=True)
    variable_name = fields.Char(required=True, index=True)

    subject_model = fields.Char(
        default="res.partner",
        help="Odoo model name the audit row is for (typically res.partner).",
    )
    subject_id = fields.Integer(
        index=True,
        help="Database ID of the subject record at the time of the fetch.",
    )

    # Reference field reconstructed from (subject_model, subject_id) so the
    # list view can render a click-through link to the current partner. Not
    # stored — if the partner is later deleted or renamed, the snapshot
    # subject_id remains as the historical truth in the audit log.
    subject_ref = fields.Reference(
        selection=[("res.partner", "Registrant")],
        string="Subject",
        compute="_compute_subject_ref",
        help="Click-through to the currently registered partner. Empty if the partner has been deleted since the fetch — the immutable subject_id below preserves the historical reference.",
    )

    @api.depends("subject_model", "subject_id")
    def _compute_subject_ref(self):
        for rec in self:
            if not rec.subject_model or not rec.subject_id:
                rec.subject_ref = False
                continue
            target = self.env[rec.subject_model].browse(rec.subject_id).exists()
            rec.subject_ref = f"{rec.subject_model},{rec.subject_id}" if target else False

    result = fields.Selection(
        selection=[
            ("ok", "OK"),
            ("not_found", "Not Found"),
            ("error", "Error"),
        ],
        required=True,
    )
    error_message = fields.Text()
    elapsed_ms = fields.Integer(help="Round-trip duration in milliseconds")
