"""Artifact Version model for polymorphic version storage."""

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ArtifactVersion(models.Model):
    """Polymorphic version storage for any versioned artifact.

    KEY DESIGN: Approval workflow is on VERSIONS (this model), not artifacts.
    This means you approve a specific change, not the artifact as a whole.
    """

    _name = "spp.artifact.version"
    _description = "Artifact Version"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "model, res_id, version desc"

    # === Polymorphic Reference ===
    model = fields.Char(
        string="Model",
        required=True,
        index=True,
        help="Technical name of the model this version belongs to",
    )
    res_id = fields.Many2oneReference(
        string="Artifact",
        model_field="model",
        index=True,
        help="Reference to the artifact record",
    )
    artifact_name = fields.Char(
        string="Artifact Name",
        compute="_compute_artifact_name",
        store=True,
    )

    # === Version Identity ===
    version = fields.Integer(
        string="Version Number",
        required=True,
        help="Sequential version number (1, 2, 3...)",
    )
    data_snapshot = fields.Json(
        string="Data Snapshot",
        help="JSON snapshot of versioned fields (properly serialized)",
    )

    # === Temporal Validity ===
    effective_date = fields.Date(
        string="Effective Date",
        help="When this version becomes/became active",
    )
    end_date = fields.Date(
        string="End Date",
        help="When superseded by newer version",
    )
    days_until_active = fields.Integer(
        string="Days Until Active",
        compute="_compute_days_until_active",
    )

    # === Supersession Chain ===
    supersedes_id = fields.Many2one(
        comodel_name="spp.artifact.version",
        string="Supersedes",
        ondelete="set null",
        help="The previous version that this one replaced",
    )
    superseded_by_id = fields.Many2one(
        comodel_name="spp.artifact.version",
        string="Superseded By",
        compute="_compute_superseded_by",
        help="The newer version that replaced this one",
    )

    # === Audit ===
    published_by = fields.Many2one(
        comodel_name="res.users",
        string="Published By",
        default=lambda self: self.env.user,
        ondelete="set null",
    )
    published_date = fields.Datetime(
        string="Published Date",
        default=fields.Datetime.now,
    )
    change_summary = fields.Text(
        string="Change Summary",
        required=True,
        help="Description of what changed in this version",
    )

    # === State ===
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("approved", "Approved"),
            ("scheduled", "Scheduled"),
            ("current", "Current"),
            ("superseded", "Superseded"),
            ("cancelled", "Cancelled"),
            ("archived", "Archived"),
        ],
        string="State",
        default="draft",
        index=True,
        tracking=True,
        help="Current state of this version",
    )

    # === Computed ===
    is_scheduled = fields.Boolean(
        string="Is Scheduled",
        compute="_compute_is_scheduled",
        store=True,
    )

    @api.depends("model", "res_id")
    def _compute_artifact_name(self):
        """Compute the display name of the artifact."""
        for record in self:
            if record.model and record.res_id:
                try:
                    artifact = self.env[record.model].browse(record.res_id)
                    record.artifact_name = artifact.display_name if artifact.exists() else _("Deleted")
                except (KeyError, ValueError):
                    record.artifact_name = _("Unknown Model")
            else:
                record.artifact_name = ""

    @api.depends("effective_date")
    def _compute_days_until_active(self):
        """Compute days until this version becomes active."""
        today = fields.Date.today()
        for record in self:
            if record.effective_date and record.effective_date > today:
                record.days_until_active = (record.effective_date - today).days
            else:
                record.days_until_active = 0

    @api.depends("effective_date", "state")
    def _compute_is_scheduled(self):
        """Compute if this version is scheduled for future activation."""
        today = fields.Date.today()
        for record in self:
            record.is_scheduled = (
                record.state == "scheduled" and record.effective_date and record.effective_date > today
            )

    def _compute_superseded_by(self):
        """Find the version that superseded this one."""
        for record in self:
            superseding = self.search(
                [
                    ("supersedes_id", "=", record.id),
                ],
                limit=1,
            )
            record.superseded_by_id = superseding

    # === Constraints ===
    @api.constrains("state", "model", "res_id")
    def _check_single_current_version(self):
        """Ensure only one version per artifact is 'current'."""
        for record in self.filtered(lambda v: v.state == "current"):
            duplicates = self.search(
                [
                    ("model", "=", record.model),
                    ("res_id", "=", record.res_id),
                    ("state", "=", "current"),
                    ("id", "!=", record.id),
                ]
            )
            if duplicates:
                raise ValidationError(_("Only one version can be current at a time for this artifact."))

    @api.constrains("version", "model", "res_id")
    def _check_version_unique(self):
        """Ensure version number is unique per artifact."""
        for record in self:
            duplicates = self.search(
                [
                    ("model", "=", record.model),
                    ("res_id", "=", record.res_id),
                    ("version", "=", record.version),
                    ("id", "!=", record.id),
                ]
            )
            if duplicates:
                raise ValidationError(
                    _("Version number %(version)d already exists for this artifact.") % {"version": record.version}
                )

    @api.constrains("version")
    def _check_version_positive(self):
        """Ensure version number is positive."""
        for record in self:
            if record.version <= 0:
                raise ValidationError(_("Version number must be positive."))

    # === Serialization Helpers ===
    def _parse_field_spec(self, spec):
        """Parse field specification into (field_name, options_dict).

        Args:
            spec: Field specification - can be:
                - String: "field_name" -> ("field_name", {"strategy": "shallow"})
                - Tuple (str): ("field_name", "embed") -> ("field_name", {"strategy": "embed"})
                - Tuple (dict): ("field_name", {...}) -> ("field_name", {...})

        Returns:
            tuple: (field_name, options_dict)
        """
        # String spec - use as-is with default strategy
        if isinstance(spec, str):
            return (spec, {"strategy": "shallow"})

        # Tuple spec - extract field name and options
        if isinstance(spec, tuple) and spec:
            field_name = spec[0]
            if len(spec) == 1:
                return (field_name, {"strategy": "shallow"})

            # Second element is either strategy string or options dict
            second = spec[1]
            if isinstance(second, str):
                return (field_name, {"strategy": second})
            if isinstance(second, dict):
                options = second.copy()
                options.setdefault("strategy", "shallow")
                return (field_name, options)

        # Invalid spec - raise error for better debugging
        raise ValidationError(_("Invalid field specification: %r. Expected string or tuple.") % (spec,))

    def _get_embed_fields(self, field, options):
        """Get list of fields to embed for a relation.

        Args:
            field: The field object
            options: Options dict that may contain "fields" key

        Returns:
            list: Field names to embed
        """
        if "fields" in options:
            return options["fields"]
        # Default: embed name, and code if it exists
        comodel = self.env[field.comodel_name]
        default_fields = ["name"]
        if "code" in comodel._fields:
            default_fields.append("code")
        return default_fields

    def _record_exists(self, model_name, res_id):
        """Check if a record exists.

        Args:
            model_name: Model name (e.g., 'res.partner')
            res_id: Record ID

        Returns:
            bool: True if record exists, False otherwise
        """
        if not res_id:
            return False
        try:
            record = self.env[model_name].browse(res_id)
            return record.exists()
        except (KeyError, ValueError):
            return False

    def _extract_embed_data(self, record, embed_fields):
        """Extract data for embedding from a record.

        Properly serializes special field types (datetime, date, binary)
        to ensure JSON-serializable output.

        Args:
            record: Record to extract data from
            embed_fields: List of field names to extract

        Returns:
            dict: JSON-serializable field values for embedding
        """
        data = {}
        for field_name in embed_fields:
            if field_name not in record._fields:
                continue
            field = record._fields[field_name]
            value = record[field_name]

            # Handle special types for JSON serialization
            if field.type == "datetime":
                data[field_name] = value.isoformat() if value else False
            elif field.type == "date":
                data[field_name] = value.isoformat() if value else False
            elif field.type == "binary":
                data[field_name] = base64.b64encode(value).decode() if value else False
            elif field.type == "many2one":
                # For nested relations in embed, just store ID (shallow)
                data[field_name] = value.id if value else False
            elif field.type in ("many2many", "one2many"):
                # For nested relations in embed, just store IDs (shallow)
                data[field_name] = value.ids
            else:
                data[field_name] = value
        return data

    def _serialize_relation(self, field, value, strategy, options):
        """Serialize a relational field based on strategy.

        Args:
            field: The field object
            value: The relational recordset value
            strategy: Versioning strategy ("shallow", "embed", "follow")
            options: Additional options dict

        Returns:
            Serialized value (varies by strategy)
        """
        is_many2one = field.type == "many2one"

        if strategy == "shallow":
            # Store ID(s) only
            return value.id if (is_many2one and value) else (False if is_many2one else value.ids)

        if strategy == "embed":
            # Store ID(s) + snapshot of specified fields
            embed_fields = self._get_embed_fields(field, options)
            if is_many2one:
                if not value:
                    return False
                return {"_ref": value.id, "_data": self._extract_embed_data(value, embed_fields)}

            # many2many, one2many
            if not value:
                return {"_refs": [], "_data": []}
            embedded_list = [self._extract_embed_data(rec, embed_fields) for rec in value]
            return {"_refs": value.ids, "_data": embedded_list}

        if strategy == "follow":
            # Store ID(s) + version_id of related record's version
            if is_many2one:
                if not value:
                    return False
                if hasattr(value, "_get_version_snapshot_fields"):
                    related_version = value.action_create_version(change_summary=_("Cascaded from version creation"))
                    return {"_ref": value.id, "_version_id": related_version.id}
                # Model doesn't support versioning, fall back to shallow
                _logger.warning(
                    "Field %s references model %s which does not support versioning. Using shallow strategy.",
                    field.name,
                    field.comodel_name,
                )
                return value.id

            # many2many, one2many
            if not value:
                return {"_refs": [], "_version_ids": []}
            version_ids = []
            for rec in value:
                if hasattr(rec, "_get_version_snapshot_fields"):
                    related_version = rec.action_create_version(change_summary=_("Cascaded from version creation"))
                    version_ids.append(related_version.id)
                else:
                    _logger.warning(
                        "Field %s references model %s which does not support versioning. Using shallow strategy.",
                        field.name,
                        field.comodel_name,
                    )
                    version_ids.append(False)
            return {"_refs": value.ids, "_version_ids": version_ids}

        # Unknown strategy - default to shallow
        return value.id if (is_many2one and value) else (False if is_many2one else value.ids)

    def _serialize_snapshot(self, record, field_specs):
        """Serialize field values for JSON storage (handles all field types).

        The snapshot includes metadata about the field specifications used,
        ensuring reliable deserialization even if the model's configuration changes.

        Args:
            record: The record to serialize
            field_specs: List of field specifications (strings, tuples, or dicts)

        Returns:
            dict: JSON-serializable dictionary with "_meta" and field values
        """
        # Store field specs metadata for reliable deserialization
        # Convert tuples to lists for JSON serialization
        serializable_specs = []
        for spec in field_specs:
            if isinstance(spec, tuple):
                serializable_specs.append(list(spec))
            else:
                serializable_specs.append(spec)

        data = {"_meta": {"field_specs": serializable_specs}}
        for spec in field_specs:
            field_name, options = self._parse_field_spec(spec)
            if field_name not in record._fields:
                continue
            field = record._fields[field_name]
            value = record[field_name]
            strategy = options.get("strategy", "shallow")

            if field.type in ("many2one", "many2many", "one2many"):
                data[field_name] = self._serialize_relation(field, value, strategy, options)
            elif field.type in ("datetime", "date"):
                data[field_name] = value.isoformat() if value else False
            elif field.type == "binary":
                data[field_name] = base64.b64encode(value).decode() if value else False
            elif field.type == "html":
                data[field_name] = str(value) if value else False
            else:
                data[field_name] = value
        return data

    def _deserialize_relation(self, field_name, raw_value, strategy, options, record):
        """Deserialize a relational field based on strategy.

        Args:
            field_name: Name of the field
            raw_value: The serialized value
            strategy: Versioning strategy ("shallow", "embed", "follow")
            options: Additional options dict
            record: The record being deserialized (for field metadata)

        Returns:
            Deserialized value (ID or list of IDs)
        """
        if strategy == "shallow":
            return raw_value

        # For embed and follow strategies, extract from dict structure
        if not isinstance(raw_value, dict):
            return raw_value

        field = record._fields[field_name]

        # Extract ID(s) from dict
        if "_ref" in raw_value:
            # Many2one
            ref_id = raw_value["_ref"]
            if strategy == "embed" and not self._record_exists(field.comodel_name, ref_id):
                if field.required:
                    _logger.warning(
                        "Embedded record %s/%s no longer exists for required field %s",
                        field.comodel_name,
                        ref_id,
                        field_name,
                    )
                return False
            return ref_id

        if "_refs" in raw_value:
            # Many2many/One2many
            ref_ids = raw_value["_refs"]
            if strategy == "embed":
                # Filter out deleted records
                existing_ids = [ref_id for ref_id in ref_ids if self._record_exists(field.comodel_name, ref_id)]
                if len(existing_ids) < len(ref_ids):
                    _logger.warning(
                        "Some embedded records for field %s no longer exist (had %d, found %d)",
                        field_name,
                        len(ref_ids),
                        len(existing_ids),
                    )
                return existing_ids
            return ref_ids

        # No recognized structure
        return raw_value

    def _deserialize_snapshot(self, record, data, field_specs=None):
        """Deserialize JSON snapshot back to field values.

        Uses field specs from snapshot metadata if available, ensuring reliable
        deserialization even if the model's configuration has changed.

        Args:
            record: The record to write values to (for field metadata)
            data: The JSON snapshot dictionary
            field_specs: Optional list of field specifications (fallback if no metadata)

        Returns:
            dict: Dictionary of field values ready for write()
        """
        # Prefer field specs from snapshot metadata (stored at serialization time)
        # This ensures we use the same strategy that was used when creating the snapshot
        if "_meta" in data and "field_specs" in data.get("_meta", {}):
            stored_specs = data["_meta"]["field_specs"]
            # Convert lists back to tuples for consistency
            field_specs = []
            for spec in stored_specs:
                if isinstance(spec, list):
                    field_specs.append(tuple(spec))
                else:
                    field_specs.append(spec)

        # Build strategy map from field_specs
        strategy_map = {}
        if field_specs:
            for spec in field_specs:
                field_name, options = self._parse_field_spec(spec)
                strategy_map[field_name] = options

        values = {}
        for field_name, value in data.items():
            # Skip metadata field
            if field_name == "_meta":
                continue
            if field_name not in record._fields:
                continue
            field = record._fields[field_name]
            options = strategy_map.get(field_name, {"strategy": "shallow"})
            strategy = options.get("strategy", "shallow")

            if field.type in ("many2one", "many2many", "one2many"):
                values[field_name] = self._deserialize_relation(field_name, value, strategy, options, record)
            elif field.type == "datetime" and value:
                values[field_name] = fields.Datetime.from_string(value)
            elif field.type == "date" and value:
                values[field_name] = fields.Date.from_string(value)
            elif field.type == "binary" and value:
                values[field_name] = base64.b64decode(value)
            else:
                values[field_name] = value
        return values

    @api.model
    def create_version(self, model, res_id, change_summary=None):
        """Create a new version for an artifact.

        Args:
            model: The model name (e.g., 'spp.cel.expression')
            res_id: The record ID
            change_summary: Description of what changed

        Returns:
            spp.artifact.version: The created version record
        """
        record = self.env[model].browse(res_id)
        if not record.exists():
            raise ValidationError(_("Artifact not found."))

        # Get previous version
        prev_version = self.search(
            [
                ("model", "=", model),
                ("res_id", "=", res_id),
                ("state", "=", "current"),
            ],
            limit=1,
        )

        # Calculate next version number
        max_version = self.search(
            [
                ("model", "=", model),
                ("res_id", "=", res_id),
            ],
            order="version desc",
            limit=1,
        )
        next_version = (max_version.version + 1) if max_version else 1

        # Create snapshot
        snapshot_fields = record._get_version_snapshot_fields()
        data = self._serialize_snapshot(record, snapshot_fields)

        return self.create(
            {
                "model": model,
                "res_id": res_id,
                "version": next_version,
                "data_snapshot": data,
                "supersedes_id": prev_version.id if prev_version else False,
                "change_summary": change_summary or _("Version %d") % next_version,
            }
        )

    def _is_approval_required(self):
        """Check if approval workflow is enabled.

        Approval is OFF by default. Enable via:
        1. System parameter: spp_versioning.require_approval = True
        2. Per-artifact: artifact.is_approval_required = True

        Returns:
            bool: True if approval required, False to allow direct scheduling
        """
        # Check system parameter (global setting)
        IrConfigParameter = self.env["ir.config_parameter"].sudo()
        if IrConfigParameter.get_param("spp_versioning.require_approval", "False") == "True":
            return True

        # Check per-artifact setting
        if self.res_id and self.model:
            record = self.env[self.model].browse(self.res_id)
            if record.exists() and getattr(record, "is_approval_required", False):
                return True

        return False

    def action_submit_for_approval(self):
        """Submit this version for approval."""
        self.ensure_one()
        if self.state != "draft":
            raise ValidationError(_("Only draft versions can be submitted for approval."))
        self.write({"state": "pending"})
        self.message_post(body=_("Version submitted for approval."))

    def action_approve(self):
        """Approve this version."""
        self.ensure_one()
        if self.state != "pending":
            raise ValidationError(_("Only pending versions can be approved."))
        self.write({"state": "approved"})
        self.message_post(body=_("Version approved."))

    def action_reject(self):
        """Reject this version (return to draft)."""
        self.ensure_one()
        if self.state != "pending":
            raise ValidationError(_("Only pending versions can be rejected."))
        self.write({"state": "draft"})
        self.message_post(body=_("Version rejected."))

    def action_schedule(self, effective_date):
        """Schedule version for future activation.

        If approval is enabled: Version must be approved first.
        If approval is disabled (default): Can schedule directly from draft.

        Args:
            effective_date: Date when this version should become active
        """
        self.ensure_one()

        # Check if approval is required
        if self._is_approval_required():
            if self.state not in ("approved", "current"):
                raise ValidationError(
                    _(
                        "Approval is required. Version must be approved before "
                        "scheduling. Please submit for approval first."
                    )
                )
        else:
            # No approval required - can schedule from draft
            if self.state not in ("draft", "approved", "current"):
                raise ValidationError(_("Version must be in draft state to schedule."))

        if effective_date <= fields.Date.today():
            raise ValidationError(_("Effective date must be in the future for scheduling."))

        self.write(
            {
                "state": "scheduled",
                "effective_date": effective_date,
            }
        )
        self.message_post(body=_("Version scheduled for activation on %(date)s.") % {"date": effective_date})

    def action_activate_now(self):
        """Activate version immediately (bypass scheduling).

        If approval is enabled: Version must be approved first.
        If approval is disabled (default): Can activate directly from draft.
        """
        self.ensure_one()

        if self._is_approval_required():
            if self.state not in ("approved",):
                raise ValidationError(_("Approval is required. Version must be approved before activation."))
        else:
            # No approval required - can activate from draft
            if self.state not in ("draft", "approved"):
                raise ValidationError(_("Version must be in draft state to activate."))

        self._activate_version()

    def action_cancel_scheduled(self):
        """Cancel a scheduled version (abort before activation)."""
        self.ensure_one()
        if self.state != "scheduled":
            raise ValidationError(_("Only scheduled versions can be cancelled."))
        self.write({"state": "cancelled"})
        self.message_post(body=_("Version cancelled."))

    def action_restore_as_new(self):
        """Restore this version's data as a new draft version.

        Creates a NEW version (preserves audit trail) with this version's data.

        Returns:
            dict: Window action to open the scheduling wizard
        """
        self.ensure_one()

        # Calculate next version number
        max_version = self.search(
            [
                ("model", "=", self.model),
                ("res_id", "=", self.res_id),
            ],
            order="version desc",
            limit=1,
        )
        next_version = (max_version.version + 1) if max_version else 1

        # Create new version with this one's snapshot
        new_version = self.create(
            {
                "model": self.model,
                "res_id": self.res_id,
                "version": next_version,
                "data_snapshot": self.data_snapshot,
                "change_summary": _("Restored from v%(version)d") % {"version": self.version},
                "state": "draft",
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Schedule Restored Version"),
            "res_model": "spp.artifact.version.schedule.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_version_id": new_version.id},
        }

    def action_view_artifact(self):
        """View the parent artifact record.

        Returns:
            dict: Window action to view the artifact
        """
        self.ensure_one()
        if not self.model or not self.res_id:
            return {"type": "ir.actions.act_window_close"}

        return {
            "type": "ir.actions.act_window",
            "res_model": self.model,
            "res_id": self.res_id,
            "view_mode": "form",
        }

    @api.model
    def _cron_activate_scheduled_versions(self):
        """Cron job: Activate versions whose effective_date has arrived.

        Runs daily (configure in cron.xml).
        """
        today = fields.Date.today()
        scheduled = self.search(
            [
                ("state", "=", "scheduled"),
                ("effective_date", "<=", today),
            ],
            order="effective_date, version",
        )

        _logger.info("Found %d scheduled versions to activate", len(scheduled))

        for version in scheduled:
            try:
                version._activate_version()
                _logger.info(
                    "Activated version %s (v%d) for %s",
                    version.id,
                    version.version,
                    version.artifact_name,
                )
            except Exception:
                _logger.exception(
                    "Failed to activate version %s",
                    version.id,
                )
                # Continue with next version - don't let one failure block others

    def _activate_version(self):
        """Transition from scheduled/draft to current, superseding previous."""
        self.ensure_one()

        # Find current version for same artifact
        current = self.search(
            [
                ("model", "=", self.model),
                ("res_id", "=", self.res_id),
                ("state", "=", "current"),
                ("id", "!=", self.id),
            ]
        )

        # Determine effective date and supersedes relationship
        effective_date = self.effective_date or fields.Date.today()
        supersedes_id = current.id if current else self.supersedes_id.id

        # Supersede current version(s)
        if current:
            current.write({"state": "superseded", "end_date": effective_date})

        # Activate this version
        self.write(
            {
                "state": "current",
                "effective_date": effective_date,
                "supersedes_id": supersedes_id,
            }
        )

        # Apply snapshot to parent artifact
        self._apply_snapshot_to_artifact()

        self.message_post(body=_("Version activated."))

    def _apply_snapshot_to_artifact(self):
        """Optionally update the artifact with this version's snapshot.

        This is useful when the "live" artifact should reflect the current version.
        Can be disabled per-model if artifacts should remain immutable.
        """
        if not self.data_snapshot:
            return
        try:
            record = self.env[self.model].browse(self.res_id)
            if hasattr(record, "_apply_version_snapshot") and record.exists():
                record._apply_version_snapshot(self.data_snapshot)
        except (KeyError, ValueError):
            _logger.warning(
                "Could not apply snapshot to artifact %s/%s",
                self.model,
                self.res_id,
            )
