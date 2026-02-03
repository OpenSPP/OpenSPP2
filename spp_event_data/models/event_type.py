# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SPPEventType(models.Model):
    """Configuration for event types."""

    _name = "spp.event.type"
    _description = "Event Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True, copy=False)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Categorization
    category = fields.Selection(
        [
            ("survey", "Survey/Assessment"),
            ("visit", "Field Visit"),
            ("sync", "External Sync"),
            ("manual", "Manual Entry"),
        ],
        default="survey",
        required=True,
    )

    # Target type
    target_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group/Household"),
            ("both", "Both"),
        ],
        default="both",
        required=True,
    )

    # ══════════════════════════════════════════════════════════════
    # DATA STRUCTURE
    # ══════════════════════════════════════════════════════════════

    # Option A: Use existing Odoo model for structured storage
    data_model_id = fields.Many2one(
        "ir.model",
        string="Data Model",
        help="Odoo model to store event data. Leave empty for JSON storage.",
        domain=[("model", "like", "spp.event.data.%")],
    )

    # Option B: Define fields directly (links to Configurator)
    field_ids = fields.One2many(
        "spp.event.field",
        "event_type_id",
        string="Event Fields",
    )

    # Storage mode (derived)
    storage_mode = fields.Selection(
        [
            ("model", "Dedicated Model"),
            ("json", "JSON Storage"),
            ("fields", "Custom Fields"),
        ],
        compute="_compute_storage_mode",
        store=True,
    )

    @api.depends("data_model_id", "field_ids")
    def _compute_storage_mode(self):
        for rec in self:
            if rec.data_model_id:
                rec.storage_mode = "model"
            elif rec.field_ids:
                rec.storage_mode = "fields"
            else:
                rec.storage_mode = "json"

    # ══════════════════════════════════════════════════════════════
    # EXTERNAL SOURCE CONFIGURATION
    # ══════════════════════════════════════════════════════════════

    source_type = fields.Selection(
        [
            ("internal", "Internal (Manual/Wizard)"),
            ("odk", "ODK Central"),
            ("kobo", "KoBoToolbox"),
            ("api", "External API"),
        ],
        default="internal",
        required=True,
    )

    # ODK/Kobo settings
    external_form_id = fields.Char(
        string="Form ID",
        help="ODK/Kobo form identifier",
    )
    external_server_url = fields.Char(string="Server URL")
    external_project_id = fields.Char(string="Project ID")

    # Field mapping for external sources
    mapping_ids = fields.One2many(
        "spp.event.type.mapping",
        "event_type_id",
        string="Field Mappings",
    )

    # Registrant identification in external data
    registrant_id_field = fields.Char(
        string="Registrant ID Field",
        help="Field in external data containing registrant identifier",
        default="registrant_id",
    )
    registrant_id_type_id = fields.Many2one(
        "spp.id.type",
        string="ID Type",
        help="Type of ID used to match registrant",
    )

    # ══════════════════════════════════════════════════════════════
    # LIFECYCLE RULES
    # ══════════════════════════════════════════════════════════════

    is_one_active_per_registrant = fields.Boolean(
        default=True,
        help="Automatically supersede previous active event when new one arrives",
    )
    auto_expire_days = fields.Integer(
        default=0,
        help="Auto-expire events after N days (0 = never)",
    )
    is_requires_approval = fields.Boolean(
        default=False,
        help="New events require approval before becoming active",
    )
    approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Workflow",
        help="Approval workflow for events requiring approval",
    )

    # ══════════════════════════════════════════════════════════════
    # CHANGE REQUEST INTEGRATION
    # Note: Change request integration fields are defined in
    # spp_change_request if that module is installed
    # ══════════════════════════════════════════════════════════════

    create_change_request = fields.Boolean(
        default=False,
        help="Automatically create change request when event data differs from registrant",
    )
    # Note: change_request_type_id and cr_field_mapping_ids are defined
    # in spp_change_request module if installed

    # ══════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ══════════════════════════════════════════════════════════════

    _code_uniq = models.Constraint(
        "UNIQUE(code)",
        "Event type code must be unique!",
    )

    # ══════════════════════════════════════════════════════════════
    # METHODS
    # ══════════════════════════════════════════════════════════════

    def get_connector(self):
        """Get the appropriate connector for this event type."""
        self.ensure_one()
        if self.source_type == "internal":
            return None
        connector_model = f"spp.event.connector.{self.source_type}"
        if connector_model in self.env:
            return self.env[connector_model].create({"event_type_id": self.id})
        return None

    def fetch_external_events(self, since_date=None):
        """Fetch events from external source."""
        self.ensure_one()
        if self.source_type == "internal":
            return []
        connector = self.get_connector()
        if connector:
            return connector.fetch(since_date=since_date)
        return []


class SPPEventTypeMapping(models.Model):
    """Mapping external fields to event data."""

    _name = "spp.event.type.mapping"
    _description = "Event Type Field Mapping"
    _order = "sequence"

    event_type_id = fields.Many2one("spp.event.type", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    external_field = fields.Char(required=True, help="Field path in external data")
    internal_field = fields.Char(required=True, help="Field in event data")
    transform = fields.Selection(
        [
            ("direct", "Direct Copy"),
            ("date", "Parse Date"),
            ("datetime", "Parse Datetime"),
            ("integer", "Parse Integer"),
            ("float", "Parse Float"),
            ("boolean", "Parse Boolean"),
            ("lookup", "Lookup Reference"),
            ("expression", "CEL Expression"),
        ],
        default="direct",
    )
    transform_expression = fields.Char(help="Expression for transform")
    lookup_model = fields.Char(help="Model for lookup transform")
    lookup_field = fields.Char(help="Field to match in lookup model")


# Note: SPPEventTypeCRMapping model is defined in spp_change_request module
