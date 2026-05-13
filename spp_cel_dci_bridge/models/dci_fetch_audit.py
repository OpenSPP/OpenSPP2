from odoo import fields, models


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

    subject_model = fields.Char(default="res.partner")
    subject_id = fields.Integer(index=True)

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
