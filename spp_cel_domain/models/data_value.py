# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Data Value - Unified cache for variable values.

This module provides the central storage for cached variable values.
All variables with cache_strategy in ('ttl', 'manual') store their
computed/fetched values here.

Key features:
- Subject-based storage (typically res.partner registrants)
- Period-based historical support
- TTL-based expiration
- Bulk upsert operations
- Company isolation
"""

import hashlib
import json
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DataValue(models.Model):
    """Cached Variable Value.

    This model stores computed/fetched variable values for efficient
    retrieval. It replaces the previous spp.indicator.value model
    with a unified approach for all variable types.

    Cache key: (company_id, variable_name, subject_model, subject_id, period_key, provider)

    Values are stored as JSON to support different data types:
    - Numbers: {"value": 42}
    - Strings: {"value": "approved"}
    - Complex: {"value": 45.2, "band": "B", "confidence": 0.95}
    """

    _name = "spp.data.value"
    _description = "Cached Variable Value"
    _order = "recorded_at desc"

    # ─── What (Variable Reference) ─────────────────────────────────────
    variable_name = fields.Char(
        string="Variable Name",
        required=True,
        index=True,
        help="Name of the variable this value belongs to",
    )
    variable_id = fields.Many2one(
        comodel_name="spp.cel.variable",
        string="Variable",
        compute="_compute_variable_id",
        store=True,
        help="Link to variable definition (computed from variable_name)",
    )

    # ─── Who (Subject Reference) ───────────────────────────────────────
    subject_model = fields.Char(
        string="Subject Model",
        required=True,
        default="res.partner",
        index=True,
        help="Model of the subject (typically 'res.partner')",
    )
    subject_id = fields.Integer(
        string="Subject ID",
        required=True,
        index=True,
        help="Database ID of the subject record",
    )
    subject_ref = fields.Char(
        string="Subject Reference",
        compute="_compute_subject_ref",
        help="Human-readable subject reference",
    )

    # ─── When (Time Reference) ────────────────────────────────────────
    period_key = fields.Char(
        string="Period Key",
        index=True,
        help=(
            "Period identifier based on variable's granularity:\n"
            "- 'current' for current-only variables\n"
            "- '2024-12' for monthly\n"
            "- '2024-Q4' for quarterly\n"
            "- '2024' for yearly\n"
            "- ISO datetime for snapshots"
        ),
    )
    as_of = fields.Datetime(
        string="As Of",
        help="Point-in-time this value represents (for snapshots)",
    )
    recorded_at = fields.Datetime(
        string="Recorded At",
        required=True,
        default=fields.Datetime.now,
        index=True,
        help="When this value was stored/updated",
    )
    expires_at = fields.Datetime(
        string="Expires At",
        index=True,
        help="When this cached value expires (for TTL-based caching)",
    )

    # ─── Value ────────────────────────────────────────────────────────
    value_json = fields.Json(
        string="Value (JSON)",
        help="The cached value stored as JSON",
    )
    value_type = fields.Selection(
        selection=[
            ("number", "Number"),
            ("string", "Text"),
            ("boolean", "Yes/No"),
            ("json", "Complex JSON"),
        ],
        string="Value Type",
        default="number",
    )

    # ─── Source Tracking ─────────────────────────────────────────────
    source_type = fields.Selection(
        selection=[
            ("computed", "Computed"),
            ("aggregate", "Aggregate"),
            ("external", "External API"),
            ("scoring", "Scoring Model"),
            ("push", "API Push"),
            ("snapshot", "Manual Snapshot"),
        ],
        string="Source Type",
        help="How this value was obtained",
    )
    provider = fields.Char(
        string="Provider",
        index=True,
        default="",
        help="Provider code for external values (e.g., 'edu_ministry')",
    )
    params_hash = fields.Char(
        string="Parameters Hash",
        index=True,
        default="",
        help=(
            "SHA256 hash (truncated to 16 chars) of additional parameters used "
            "in value computation. Used to distinguish cached values computed "
            "with different parameter sets.\n\n"
            "Example use cases:\n"
            "- Scoring model computed with threshold=100 vs threshold=200\n"
            "- External API query with filter={'status': 'active'}\n"
            "- Aggregate computed over different member subsets\n\n"
            "Empty string when no parameters were used (most common case)."
        ),
    )

    # ─── Quality Metadata ─────────────────────────────────────────────
    coverage = fields.Float(
        string="Coverage",
        help="Data completeness indicator (0.0 to 1.0)",
    )
    is_stale = fields.Boolean(
        string="Is Stale",
        compute="_compute_is_stale",
        store=True,
        help="Whether this value has expired but not yet been refreshed",
    )
    error_code = fields.Char(
        string="Error Code",
        help="Error code if value fetch/compute failed",
    )
    error_message = fields.Text(
        string="Error Message",
        help="Error details if value fetch/compute failed",
    )

    # ─── Audit ───────────────────────────────────────────────────────
    created_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Created By",
        default=lambda self: self.env.user,
        readonly=True,
    )
    invalidated_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Invalidated By",
    )
    invalidated_at = fields.Datetime(
        string="Invalidated At",
    )

    # ─── Multi-tenancy ─────────────────────────────────────────────────
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # Database constraint for cache key uniqueness
    _unique_cache_key = models.Constraint(
        "UNIQUE(company_id, variable_name, subject_model, subject_id, period_key, provider, params_hash)",
        "Variable value already exists for this subject and period.",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED METHODS
    # ═══════════════════════════════════════════════════════════════════════

    @api.depends("variable_name")
    def _compute_variable_id(self):
        """Link to variable definition by name.

        Optimized to batch lookup all unique variable names in a single query
        instead of N+1 queries (one per record).
        """
        if not self:
            return

        # Collect unique variable names
        variable_names = set(rec.variable_name for rec in self if rec.variable_name)

        if not variable_names:
            for rec in self:
                rec.variable_id = False
            return

        # Batch lookup all variables in a single query
        Variable = self.env["spp.cel.variable"]
        variables = Variable.search([("name", "in", list(variable_names))])

        # Build name -> variable mapping
        name_to_variable = {var.name: var for var in variables}

        # Assign to records
        for rec in self:
            if rec.variable_name:
                rec.variable_id = name_to_variable.get(rec.variable_name, False)
            else:
                rec.variable_id = False

    def _compute_subject_ref(self):
        """Compute human-readable subject reference."""
        for rec in self:
            if rec.subject_model and rec.subject_id:
                try:
                    subject = self.env[rec.subject_model].browse(rec.subject_id)
                    if subject.exists():
                        rec.subject_ref = subject.display_name
                    else:
                        rec.subject_ref = f"{rec.subject_model}#{rec.subject_id} (deleted)"
                except Exception:
                    rec.subject_ref = f"{rec.subject_model}#{rec.subject_id}"
            else:
                rec.subject_ref = False

    @api.depends("expires_at")
    def _compute_is_stale(self):
        """Check if value has expired."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.expires_at:
                rec.is_stale = rec.expires_at < now
            else:
                rec.is_stale = False

    # ═══════════════════════════════════════════════════════════════════════
    # CORE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def upsert_values(self, values_list):
        """Bulk insert or update cached values.

        This is the primary method for storing variable values. It handles
        conflict resolution on the unique constraint.

        Args:
            values_list: List of dicts with keys:
                - variable_name (required)
                - subject_model (default: 'res.partner')
                - subject_id (required)
                - period_key (optional)
                - value_json (required)
                - value_type (default: 'number')
                - source_type (optional)
                - provider (optional)
                - params (optional dict, will be hashed)
                - ttl_seconds (optional, to compute expires_at)
                - as_of (optional)
                - coverage (optional)

        Returns:
            dict: {'inserted': int, 'updated': int}
        """
        if not values_list:
            return {"inserted": 0, "updated": 0}

        now = fields.Datetime.now()
        company_id = self.env.company.id

        # Prepare records for bulk SQL upsert
        records = []
        for vals in values_list:
            variable_name = vals.get("variable_name")
            if not variable_name:
                _logger.warning("Skipping value without variable_name")
                continue

            subject_id = vals.get("subject_id")
            if not subject_id:
                _logger.warning("Skipping value without subject_id for %s", variable_name)
                continue

            # Hash params if provided
            params = vals.get("params")
            params_hash = self._hash_params(params) if params else ""

            # Compute expires_at if TTL provided
            ttl_seconds = vals.get("ttl_seconds")
            expires_at = now + timedelta(seconds=ttl_seconds) if ttl_seconds and ttl_seconds > 0 else None

            records.append(
                {
                    "company_id": company_id,
                    "variable_name": variable_name,
                    "subject_model": vals.get("subject_model", "res.partner"),
                    "subject_id": subject_id,
                    "period_key": vals.get("period_key", "current"),
                    "value_json": json.dumps(vals.get("value_json")),
                    "value_type": vals.get("value_type", "number"),
                    "source_type": vals.get("source_type"),
                    "provider": vals.get("provider", ""),
                    "params_hash": params_hash,
                    "as_of": vals.get("as_of"),
                    "coverage": vals.get("coverage"),
                    "recorded_at": now,
                    "expires_at": expires_at,
                }
            )

        if not records:
            return {"inserted": 0, "updated": 0}

        # Use bulk SQL INSERT ... ON CONFLICT for performance
        # This avoids N+1 queries when processing large batches
        cr = self.env.cr

        # Build the INSERT query with ON CONFLICT DO UPDATE
        insert_sql = """
            INSERT INTO spp_data_value (
                company_id, variable_name, subject_model, subject_id,
                period_key, value_json, value_type, source_type,
                provider, params_hash, as_of, coverage,
                recorded_at, expires_at, error_code, error_message,
                create_uid, create_date, write_uid, write_date
            ) VALUES %s
            ON CONFLICT (company_id, variable_name, subject_model, subject_id, period_key, provider, params_hash)
            DO UPDATE SET
                value_json = EXCLUDED.value_json,
                value_type = EXCLUDED.value_type,
                source_type = EXCLUDED.source_type,
                as_of = EXCLUDED.as_of,
                coverage = EXCLUDED.coverage,
                recorded_at = EXCLUDED.recorded_at,
                expires_at = EXCLUDED.expires_at,
                error_code = NULL,
                error_message = NULL,
                write_uid = EXCLUDED.write_uid,
                write_date = EXCLUDED.write_date
        """

        # Format values for execute_values
        uid = self.env.uid
        template = (
            "(%(company_id)s, %(variable_name)s, %(subject_model)s, %(subject_id)s, "
            "%(period_key)s, %(value_json)s::jsonb, %(value_type)s, %(source_type)s, "
            "%(provider)s, %(params_hash)s, %(as_of)s, %(coverage)s, "
            "%(recorded_at)s, %(expires_at)s, NULL, NULL, "
            f"{uid}, %(recorded_at)s, {uid}, %(recorded_at)s)"
        )

        from psycopg2.extras import execute_values

        execute_values(cr._obj, insert_sql, records, template=template, page_size=1000)

        # Invalidate cache for affected records
        self.invalidate_model()

        # Return approximate counts (exact split between insert/update not easily available)
        return {"inserted": len(records), "updated": 0}

    @api.model
    def read_values(self, variable_name, subject_ids, period_key=None, provider=None):
        """Read cached values for a variable.

        Args:
            variable_name: Name of the variable
            subject_ids: List of subject IDs
            period_key: Optional period filter (defaults to 'current')
            provider: Optional provider filter

        Returns:
            dict: {subject_id: value, ...} for subjects with cached values
        """
        if not subject_ids:
            return {}

        domain = [
            ("company_id", "=", self.env.company.id),
            ("variable_name", "=", variable_name),
            ("subject_id", "in", subject_ids),
        ]

        if period_key:
            domain.append(("period_key", "=", period_key))
        else:
            domain.append(("period_key", "=", "current"))

        if provider:
            domain.append(("provider", "=", provider))

        # Exclude expired values unless explicitly including stale
        domain.append("|")
        domain.append(("expires_at", "=", False))
        domain.append(("expires_at", ">", fields.Datetime.now()))

        records = self.search(domain)

        result = {}
        for rec in records:
            # Extract value from JSON
            if rec.value_json:
                if isinstance(rec.value_json, dict) and "value" in rec.value_json:
                    result[rec.subject_id] = rec.value_json["value"]
                else:
                    result[rec.subject_id] = rec.value_json

        return result

    @api.model
    def read_values_with_metadata(self, variable_name, subject_ids, period_key=None):
        """Read cached values with full metadata.

        Args:
            variable_name: Name of the variable
            subject_ids: List of subject IDs
            period_key: Optional period filter

        Returns:
            dict: {subject_id: {'value': ..., 'recorded_at': ..., 'is_stale': ...}, ...}
        """
        if not subject_ids:
            return {}

        domain = [
            ("company_id", "=", self.env.company.id),
            ("variable_name", "=", variable_name),
            ("subject_id", "in", subject_ids),
        ]

        if period_key:
            domain.append(("period_key", "=", period_key))

        records = self.search(domain)

        result = {}
        for rec in records:
            value = rec.value_json.get("value") if isinstance(rec.value_json, dict) else rec.value_json
            result[rec.subject_id] = {
                "value": value,
                "value_json": rec.value_json,
                "recorded_at": rec.recorded_at,
                "expires_at": rec.expires_at,
                "is_stale": rec.is_stale,
                "source_type": rec.source_type,
                "provider": rec.provider,
                "coverage": rec.coverage,
            }

        return result

    def invalidate(self, variable_name=None, subject_ids=None, period_key=None, provider=None):
        """Mark cached values as expired.

        This doesn't delete values but marks them as stale so they can
        be used as fallback while fresh values are being fetched.

        Args:
            variable_name: Optional variable filter
            subject_ids: Optional subject ID filter
            period_key: Optional period filter
            provider: Optional provider filter
        """
        domain = [("company_id", "=", self.env.company.id)]

        if variable_name:
            domain.append(("variable_name", "=", variable_name))
        if subject_ids:
            domain.append(("subject_id", "in", subject_ids))
        if period_key:
            domain.append(("period_key", "=", period_key))
        if provider:
            domain.append(("provider", "=", provider))

        now = fields.Datetime.now()
        records = self.search(domain)
        records.write(
            {
                "expires_at": now,
                "invalidated_at": now,
                "invalidated_by_id": self.env.user.id,
            }
        )

        return len(records)

    def invalidate_pattern(self, pattern, subject_ids=None, provider_id=None):
        """Invalidate values matching a variable name pattern.

        Args:
            pattern: Variable name pattern with wildcards (e.g., 'household.*')
            subject_ids: Optional subject ID filter
            provider_id: Optional provider ID filter

        Returns:
            int: Number of values invalidated
        """
        # Convert wildcard pattern to SQL LIKE
        sql_pattern = pattern.replace("*", "%").replace("?", "_")

        domain = [
            ("company_id", "=", self.env.company.id),
            ("variable_name", "=like", sql_pattern),
        ]

        if subject_ids:
            domain.append(("subject_id", "in", subject_ids))

        if provider_id:
            domain.append(("provider_id", "=", provider_id))

        now = fields.Datetime.now()
        records = self.search(domain)
        records.write(
            {
                "expires_at": now,
                "invalidated_at": now,
                "invalidated_by_id": self.env.user.id,
            }
        )

        return len(records)

    # ═══════════════════════════════════════════════════════════════════════
    # PURGE / CLEANUP
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def cron_purge_expired(self, retention_days=None):
        """Purge old expired values.

        Called by cron job to clean up stale cached values.

        Args:
            retention_days: Dict of source_type -> retention days
                          If None, uses system configuration
        """
        if retention_days is None:
            # Get from system config
            config = self.env["ir.config_parameter"].sudo()
            retention_json = config.get_param(
                "spp.data_value.retention_by_source",
                default='{"external": 90, "aggregate": 180, "scoring": 730, "snapshot": 1825}',
            )
            default_days = int(config.get_param("spp.data_value.retention_days", "365"))
            try:
                retention_days = json.loads(retention_json)
            except json.JSONDecodeError:
                retention_days = {}
        else:
            default_days = 365

        total_deleted = 0
        now = fields.Datetime.now()

        # Purge by source type
        for source_type, days in retention_days.items():
            cutoff = now - timedelta(days=days)
            records = self.search(
                [
                    ("source_type", "=", source_type),
                    ("recorded_at", "<", cutoff),
                ]
            )
            if records:
                count = len(records)
                records.unlink()
                total_deleted += count
                _logger.info(
                    "Purged %d expired %s values older than %d days",
                    count,
                    source_type,
                    days,
                )

        # Purge remaining with default retention
        cutoff = now - timedelta(days=default_days)
        records = self.search(
            [
                ("source_type", "not in", list(retention_days.keys())),
                ("recorded_at", "<", cutoff),
            ]
        )
        if records:
            count = len(records)
            records.unlink()
            total_deleted += count
            _logger.info(
                "Purged %d expired values older than %d days (default retention)",
                count,
                default_days,
            )

        return total_deleted

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _hash_params(params):
        """Create a stable hash of parameters dict for cache key differentiation.

        This is used in the unique constraint to allow the same variable to have
        multiple cached values when computed with different parameters. For example:
        - A scoring model might be computed with different thresholds
        - An external API might be queried with different filters
        - An aggregate might be computed over different member subsets

        The hash is deterministic (order-independent) so identical parameter dicts
        always produce the same hash, even if keys are in different order.

        Args:
            params: Dict of parameters to hash. If None or empty, returns "".

        Returns:
            str: First 16 characters of SHA256 hash of sorted JSON, or "" if no params.

        Example:
            >>> DataValue._hash_params({"threshold": 100, "mode": "strict"})
            'a1b2c3d4e5f67890'
            >>> DataValue._hash_params({"mode": "strict", "threshold": 100})  # Same hash
            'a1b2c3d4e5f67890'
            >>> DataValue._hash_params({})
            ''
        """
        if not params:
            return ""
        # Sort keys for stable ordering
        sorted_json = json.dumps(params, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(sorted_json.encode()).hexdigest()[:16]

    def get_value(self):
        """Extract the value from value_json.

        Returns:
            The stored value (number, string, dict, etc.)
        """
        self.ensure_one()
        if not self.value_json:
            return None
        if isinstance(self.value_json, dict) and "value" in self.value_json:
            return self.value_json["value"]
        return self.value_json

    def set_value(self, value, **metadata):
        """Set the value with optional metadata.

        Args:
            value: The value to store
            **metadata: Additional metadata (coverage, confidence, etc.)
        """
        self.ensure_one()
        if metadata:
            self.value_json = {"value": value, **metadata}
        else:
            self.value_json = {"value": value}
        self.recorded_at = fields.Datetime.now()

    def name_get(self):
        """Display name for cached values."""
        result = []
        for rec in self:
            period = f" ({rec.period_key})" if rec.period_key and rec.period_key != "current" else ""
            result.append((rec.id, f"{rec.variable_name}#{rec.subject_id}{period}"))
        return result
