# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OpenSPPEventData(models.Model):
    """Event data records."""

    _name = "spp.event.data"
    _description = "Event Data"
    _inherit = ["mail.thread", "mail.activity.mixin", "spp.approval.mixin"]
    _order = "collection_date desc, id desc"

    # ══════════════════════════════════════════════════════════════
    # CORE FIELDS
    # ══════════════════════════════════════════════════════════════

    name = fields.Char(compute="_compute_name", store=True)

    event_type_id = fields.Many2one(
        "spp.event.type",
        string="Event Type",
        required=False,  # Not required for legacy model-based events
        index=True,
        ondelete="restrict",
    )
    event_type_code = fields.Char(
        related="event_type_id.code",
        store=True,
        index=True,
    )

    # Registrant link
    partner_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        required=True,
        index=True,
        ondelete="cascade",
        domain=[("is_registrant", "=", True)],
    )

    # Legacy fields for backward compatibility
    model = fields.Char(
        "Related Document Model",
        index=True,
        help="Deprecated: Use event_type_id instead",
    )
    res_id = fields.Many2oneReference("Related Data", index=True, model_field="model", help="Deprecated")
    registrar = fields.Char(help="Deprecated: Use collector_name instead")

    # ══════════════════════════════════════════════════════════════
    # COLLECTION METADATA
    # ══════════════════════════════════════════════════════════════

    collection_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    collector_id = fields.Many2one(
        "res.users",
        string="Collected By",
        default=lambda self: self.env.user,
    )
    collector_name = fields.Char(
        string="Collector Name",
        help="For external collectors not in system",
    )

    # Expiry
    expiry_date = fields.Date()
    is_expired = fields.Boolean(compute="_compute_is_expired", store=True)

    @api.depends("expiry_date")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = rec.expiry_date and rec.expiry_date < today

    # ══════════════════════════════════════════════════════════════
    # STATE MANAGEMENT
    # ══════════════════════════════════════════════════════════════

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("active", "Active"),
            ("superseded", "Superseded"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
            ("inactive", "Inactive"),  # Legacy state
        ],
        default="draft",
        required=True,
        index=True,
    )

    superseded_by_id = fields.Many2one(
        "spp.event.data",
        string="Superseded By",
        readonly=True,
    )
    supersedes_id = fields.Many2one(
        "spp.event.data",
        string="Supersedes",
        readonly=True,
    )

    # ══════════════════════════════════════════════════════════════
    # DATA STORAGE
    # ══════════════════════════════════════════════════════════════

    # Option A: Link to dedicated model record
    data_model = fields.Char(
        related="event_type_id.data_model_id.model",
        store=True,
    )
    data_record_id = fields.Many2oneReference(
        string="Data Record",
        model_field="data_model",
    )

    # Option B: JSON storage
    data_json = fields.Json(string="Event Data")

    # Computed: structured access to data
    @api.depends("data_record_id", "data_json", "event_type_id")
    def _compute_data_values(self):
        """Get data as dictionary regardless of storage mode."""
        for rec in self:
            if rec.data_record_id and rec.data_model:
                try:
                    record = self.env[rec.data_model].browse(rec.data_record_id)
                    rec.data_values = record.read()[0] if record.exists() else {}
                except Exception:
                    rec.data_values = {}
            else:
                rec.data_values = rec.data_json or {}

    data_values = fields.Json(compute="_compute_data_values")

    # Computed: HTML formatted data for better UI display
    data_html = fields.Html(compute="_compute_data_html", sanitize=False)

    @api.depends("data_json")
    def _compute_data_html(self):
        """Convert JSON data to formatted HTML for display."""
        for rec in self:
            if not rec.data_json:
                rec.data_html = False
                continue

            # Collect all items to render
            items = []

            # Collect all items
            for key, value in rec.data_json.items():
                self._collect_json_items(key, value, items, level=0)

            # Split items into two columns
            mid_point = (len(items) + 1) // 2
            left_items = items[:mid_point]
            right_items = items[mid_point:]

            # Build HTML with two columns
            html_parts = [
                '<div class="row g-3">',
                '<div class="col-md-6">',
                '<div class="card shadow-sm">',
                '<div class="card-body p-3">',
            ]

            # Render left column
            html_parts.append(self._render_items_list(left_items))

            html_parts.extend(
                [
                    "</div>",  # card-body
                    "</div>",  # card
                    "</div>",  # col
                    '<div class="col-md-6">',
                    '<div class="card shadow-sm">',
                    '<div class="card-body p-3">',
                ]
            )

            # Render right column
            html_parts.append(self._render_items_list(right_items))

            html_parts.extend(
                [
                    "</div>",  # card-body
                    "</div>",  # card
                    "</div>",  # col
                    "</div>",  # row
                ]
            )

            rec.data_html = "".join(html_parts)

    def _collect_json_items(self, key, value, items_list, level=0):
        """Recursively collect items from JSON."""
        if isinstance(value, dict):
            items_list.append((key, None, "header", level))
            for sub_key, sub_value in value.items():
                self._collect_json_items(sub_key, sub_value, items_list, level + 1)
        elif isinstance(value, list):
            items_list.append((key, None, "header", level))
            for idx, item in enumerate(value):
                if isinstance(item, dict | list):
                    self._collect_json_items(f"[{idx}]", item, items_list, level + 1)
                else:
                    items_list.append((f"Item {idx + 1}", item, "value", level + 1))
        else:
            items_list.append((key, value, "value", level))

    def _render_items_list(self, items):
        """Render a list of items as HTML."""
        if not items:
            return '<p class="text-muted fst-italic mb-0">No data</p>'

        parts = ['<div class="o_event_data_list">']
        for key, value, item_type, level in items:
            indent_style = f"padding-left: {level * 20}px;"
            formatted_key = self._format_label(key)

            if item_type == "header":
                parts.append(
                    f'<div class="mb-2" style="{indent_style}">'
                    f'<strong class="text-primary">{formatted_key}:</strong>'
                    f"</div>"
                )
            else:
                formatted_value = self._format_value(value)
                parts.append(
                    f'<div class="d-flex justify-content-between align-items-start mb-1" '
                    f'style="{indent_style}">'
                    f'<span class="text-muted me-3" style="min-width: 40%;">{formatted_key}:</span>'
                    f'<span class="text-end" style="word-break: break-word; flex: 1;">'
                    f"{formatted_value}</span>"
                    f"</div>"
                )
        parts.append("</div>")
        return "".join(parts)

    def _format_label(self, label):
        """Format a label for display by replacing underscores and title-casing.

        Examples:
            'user_name' -> 'User Name'
            'old_state' -> 'Old State'
            'action' -> 'Action'
            '[0]' -> '[0]'
        """
        # Don't modify array indices
        if label.startswith("[") and label.endswith("]"):
            return label

        # Replace underscores with spaces and title case
        return label.replace("_", " ").title()

    def _format_value(self, value):
        """Format a value for HTML display."""
        if value is None:
            return '<span class="text-muted fst-italic">None</span>'
        elif value is True:
            return '<span class="badge text-bg-success">True</span>'
        elif value is False:
            return '<span class="badge text-bg-secondary">False</span>'
        elif isinstance(value, int | float):
            return f'<span class="text-primary">{value}</span>'
        else:
            # Escape HTML and handle strings
            from markupsafe import Markup

            return Markup.escape(str(value))

    # ══════════════════════════════════════════════════════════════
    # EXTERNAL SOURCE TRACKING
    # ══════════════════════════════════════════════════════════════

    source_type = fields.Selection(related="event_type_id.source_type", store=True, index=True)
    source_reference = fields.Char(
        string="Source Reference",
        help="External submission ID (ODK instance ID, etc.)",
        index=True,
    )
    source_url = fields.Char(string="Source URL")
    source_received_date = fields.Datetime(
        string="Received Date",
        help="When data was received from external source",
    )
    source_raw_data = fields.Json(
        string="Raw Source Data",
        help="Original data from external source (for debugging)",
    )

    # ══════════════════════════════════════════════════════════════
    # CHANGE REQUEST LINK
    # Note: change_request_ids and change_request_count fields are
    # defined in spp_change_request module if installed
    # ══════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ══════════════════════════════════════════════════════════════

    @api.depends("event_type_id", "partner_id", "collection_date", "model")
    def _compute_name(self):
        for rec in self:
            if rec.event_type_id:
                parts = [
                    rec.event_type_id.name or "Event",
                    rec.partner_id.name or "",
                    str(rec.collection_date) if rec.collection_date else "",
                ]
                rec.name = " - ".join(filter(None, parts))
            elif rec.model:
                # Legacy name computation
                model_name = self.env["ir.model"].search([("model", "=", rec.model)]).name
                rec.name = model_name or ""
                if rec.create_date:
                    rec.name += f" - [{rec.create_date.strftime('%Y-%m-%d %H:%M')}]"
            else:
                rec.name = "Event"

    # ══════════════════════════════════════════════════════════════
    # LIFECYCLE METHODS
    # ══════════════════════════════════════════════════════════════

    @api.model_create_multi
    def create(self, vals_list):
        """Handle lifecycle on create."""
        # Handle legacy model-based events
        for vals in vals_list:
            if vals.get("model") and not vals.get("event_type_id"):
                # Legacy creation - handle backward compatibility
                model = vals["model"]
                partner = vals.get("partner_id")
                active_event = self.search(
                    [
                        ("model", "=", model),
                        ("state", "in", ["active", "inactive"]),
                        ("partner_id", "=", partner),
                    ]
                )
                if active_event:
                    active_event.end_active_event()

        records = super().create(vals_list)

        for record in records:
            if record.event_type_id:
                record._handle_lifecycle_on_create()

        return records

    def _handle_lifecycle_on_create(self):
        """Handle auto-supersede and approval requirements."""
        self.ensure_one()
        event_type = self.event_type_id

        if not event_type:
            return

        vals = {}

        # Auto-supersede previous active event
        if event_type.is_one_active_per_registrant and self.state == "draft":
            previous = self.search(
                [
                    ("event_type_id", "=", event_type.id),
                    ("partner_id", "=", self.partner_id.id),
                    ("state", "=", "active"),
                    ("id", "!=", self.id),
                ],
                limit=1,
            )
            if previous:
                vals["supersedes_id"] = previous.id

        # Set expiry date
        if event_type.auto_expire_days and not self.expiry_date:
            vals["expiry_date"] = fields.Date.add(
                self.collection_date,
                days=event_type.auto_expire_days,
            )

        if vals:
            self.write(vals)

        # Handle approval requirement - submit for approval if configured
        if event_type.is_requires_approval and event_type.approval_definition_id:
            self.write({"state": "pending"})
            self.action_submit_for_approval()

    # ══════════════════════════════════════════════════════════════
    # STATE TRANSITIONS
    # ══════════════════════════════════════════════════════════════

    def action_activate(self):
        """Activate the event and supersede previous."""
        for rec in self:
            if rec.supersedes_id and rec.supersedes_id.state == "active":
                rec.supersedes_id.write({"state": "superseded", "superseded_by_id": rec.id})
            rec.write({"state": "active"})

            # Trigger change request creation if configured
            if rec.event_type_id.create_change_request:
                rec._create_change_requests()

        return True

    def action_cancel(self):
        """Cancel the event."""
        self.write({"state": "cancelled"})
        return True

    def action_set_draft(self):
        """Reset to draft state."""
        self.write({"state": "draft"})
        return True

    def end_active_event(self):
        """Legacy method for backward compatibility."""
        for rec in self:
            if rec.state == "active":
                rec.write({"state": "superseded"})
            else:
                rec.write({"state": "inactive"})

    # ══════════════════════════════════════════════════════════════
    # APPROVAL WORKFLOW (from spp.approval.mixin)
    # ══════════════════════════════════════════════════════════════

    def _get_approval_definition(self):
        """Return the approval definition from the event type.

        This method is called by the approval mixin to determine which
        approval workflow to use for this event.
        """
        self.ensure_one()
        if not self.event_type_id:
            raise UserError(_("Cannot submit for approval: No event type specified."))

        if not self.event_type_id.approval_definition_id:
            raise UserError(
                _(
                    "No approval workflow configured for event type '%(name)s'. "
                    "Please configure an approval definition in Events > Configuration > Event Types.",
                    name=self.event_type_id.name,
                )
            )
        return self.event_type_id.approval_definition_id

    def _on_approve(self):
        """Hook called after approval - activate the event."""
        super()._on_approve()
        # Activate the event when approved
        self.action_activate()

    def _on_reject(self, reason):
        """Hook called after rejection - cancel the event."""
        super()._on_reject(reason)
        # Set state to cancelled when rejected
        self.write({"state": "cancelled"})

    def _on_reset_to_draft(self):
        """Hook called after resetting to draft."""
        super()._on_reset_to_draft()
        # Reset event state to draft as well
        self.write({"state": "draft"})

    def _create_change_requests(self):
        """Create change requests based on event type configuration.

        Note: Full CR integration (change_request_type_id, cr_field_mapping_ids)
        is provided by the spp_change_request module when installed.
        This base method is a hook for that integration.
        """
        self.ensure_one()
        event_type = self.event_type_id

        # Check if create_change_request is enabled
        if not event_type.create_change_request:
            return

        # Check if change_request_type_id field exists (from spp_change_request module)
        if not hasattr(event_type, "change_request_type_id"):
            _logger.debug("Change request integration not available - install spp_change_request module")
            return

        cr_type = getattr(event_type, "change_request_type_id", None)
        if not cr_type:
            return

        # Check if spp.change.request model exists
        if "spp.change.request" not in self.env:
            _logger.warning("spp.change.request model not available")
            return

        try:
            data = self.data_values or {}

            # Check if field mappings exist (from spp_change_request module)
            cr_field_mappings = getattr(event_type, "cr_field_mapping_ids", None)
            if not cr_field_mappings:
                return

            # Evaluate field mappings
            should_create = False
            cr_data = {}

            for mapping in cr_field_mappings:
                try:
                    event_value = data.get(mapping.event_field)
                    # Use getattr for safe field access
                    registrant_value = getattr(self.partner_id, mapping.registrant_field, None)

                    if mapping.compare_mode == "always":
                        should_create = True
                        cr_data[mapping.registrant_field] = event_value
                    elif mapping.compare_mode == "different" and event_value != registrant_value:
                        should_create = True
                        cr_data[mapping.registrant_field] = event_value
                    elif mapping.compare_mode == "empty" and not registrant_value:
                        should_create = True
                        cr_data[mapping.registrant_field] = event_value
                except Exception as field_error:
                    _logger.warning(
                        "Error evaluating field mapping %s for event %s: %s",
                        mapping.event_field,
                        self.id,
                        field_error,
                    )
                    continue

            if should_create and cr_data:
                self.env["spp.change.request"].create(
                    {
                        "change_request_type_id": cr_type.id,
                        "registrant_id": self.partner_id.id,
                        "source_event_id": self.id,
                        "proposed_data": cr_data,
                    }
                )
        except Exception as e:
            _logger.error(
                "Failed to create change request from event %s: %s",
                self.id,
                e,
            )

    # ══════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ══════════════════════════════════════════════════════════════

    def open_form(self):
        """Open the related data form (legacy support)."""
        for rec in self:
            if rec.data_record_id and rec.data_model:
                return {
                    "name": rec.name,
                    "view_mode": "form",
                    "res_model": rec.data_model,
                    "res_id": rec.data_record_id,
                    "type": "ir.actions.act_window",
                    "target": "new",
                    "context": {"create": False, "edit": False},
                    "flags": {"mode": "readonly"},
                }
            elif rec.model and rec.res_id:
                # Legacy support
                context = {"create": False, "edit": False}
                res_model = rec.model
                view_id = self.env[res_model].get_view_id() if hasattr(self.env[res_model], "get_view_id") else False
                return {
                    "name": rec.name,
                    "view_mode": "form",
                    "res_model": res_model,
                    "res_id": rec.res_id,
                    "view_id": view_id,
                    "type": "ir.actions.act_window",
                    "target": "new",
                    "context": context,
                    "flags": {"mode": "readonly"},
                }
        return True

    # Note: action_view_change_requests is defined in spp_change_request module

    def get_data_value(self, field_name, default=None):
        """Get a specific value from event data."""
        self.ensure_one()
        data = self.data_values or {}
        return data.get(field_name, default)

    def set_data_value(self, field_name, value):
        """Set a specific value in event data (JSON mode only)."""
        self.ensure_one()
        if self.data_model:
            raise ValueError("Cannot set data values on model-based events directly")
        data = dict(self.data_json or {})
        data[field_name] = value
        self.write({"data_json": data})

    # ══════════════════════════════════════════════════════════════
    # CRON METHODS
    # ══════════════════════════════════════════════════════════════

    @api.model
    def _cron_expire_events(self):
        """Expire events past their expiry date."""
        today = fields.Date.context_today(self)
        expired = self.search(
            [
                ("state", "=", "active"),
                ("expiry_date", "!=", False),
                ("expiry_date", "<", today),
            ]
        )
        if expired:
            expired.write({"state": "expired"})
            _logger.info("Expired %d events", len(expired))
        return True
