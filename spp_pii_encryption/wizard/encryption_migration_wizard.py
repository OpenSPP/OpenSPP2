# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""PII Data Encryption Migration Wizard.

Migrates existing plaintext PII data to encrypted format. This is a
one-time migration driven by the classification registry: every field
classified as PII (spp.field.classification, is_pii=True) on a model that
supports encryption (inherits spp.encrypted.field.mixin, i.e. has a
``<field>_index`` blind-index column) can be scanned, previewed and
encrypted in place.

Features:
- Scan classified models for PII fields that need encryption
- Dry-run mode to preview how many records a migration would touch
- Batched in-place migration with per-record error isolation

There is deliberately NO in-app rollback or plaintext backup: encrypted
values remain readable through the mixin, and a plaintext backup table
would defeat the purpose of the migration (ADR-012 threat model, "backup
exposure"). Operators must take a database snapshot before migrating.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class EncryptionMigrationWizard(models.TransientModel):
    """Wizard to migrate existing plaintext data to encrypted format."""

    _name = "spp.encryption.migration.wizard"
    _description = "PII Data Encryption Migration Wizard"

    # Model selection
    model_ids = fields.Many2many(
        comodel_name="ir.model",
        string="Models to Process",
        help="Select models to process. Leave empty to process all models with PII fields.",
    )

    # Processing options
    batch_size = fields.Integer(
        default=100,
        help="Number of records to process per batch",
    )

    # Results
    state = fields.Selection(
        selection=[
            ("draft", "Not Started"),
            ("scanning", "Scanning"),
            ("ready", "Ready"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="draft",
    )

    progress = fields.Float(default=0.0)

    result_summary = fields.Text(readonly=True)

    scan_result_ids = fields.One2many(
        comodel_name="spp.encryption.migration.scan.result",
        inverse_name="wizard_id",
        string="Scan Results",
    )

    migration_log_ids = fields.One2many(
        comodel_name="spp.encryption.migration.log",
        inverse_name="wizard_id",
        string="Migration Log",
    )

    @api.constrains("batch_size")
    def _check_batch_size(self):
        for wizard in self:
            if wizard.batch_size <= 0:
                raise ValidationError(_("Batch size must be a positive number."))

    def action_scan(self):
        """Scan for PII fields that need encryption."""
        self.ensure_one()
        self.state = "scanning"
        self.scan_result_ids.unlink()
        self.migration_log_ids.unlink()

        # Get PII field classifications
        domain = [("is_pii", "=", True)]
        if self.model_ids:
            domain.append(("model_id", "in", self.model_ids.ids))
        classifications = self.env["spp.field.classification"].search(domain)

        results = []
        skipped_models = set()
        for classification in classifications:
            # Stored related on the classification — deliberately NOT
            # classification.model_id.model: ir.model records are readable
            # only by the Access Rights group, which the encryption admin
            # does not necessarily hold.
            model_name = classification.model_name
            field_name = classification.field_name

            # Check if model exists in the registry
            Model = self.env.get(model_name)
            if Model is None:
                continue

            # Check if field exists
            if field_name not in Model._fields:
                continue

            # A field is encryptable when its model carries the mixin's
            # blind-index companion column
            index_field = f"{field_name}_index"
            is_encrypted = index_field in Model._fields

            try:
                total_records = Model.search_count([])
                records_with_data = Model.search_count(
                    [
                        (field_name, "!=", False),
                        (field_name, "!=", ""),
                    ]
                )
                encrypted_count = 0
                if is_encrypted:
                    encrypted_count = Model.search_count([(index_field, "!=", False)])
            except AccessError:
                # The encryption admin is deliberately not a system admin;
                # one unreadable model must not abort the whole scan.
                if model_name not in skipped_models:
                    skipped_models.add(model_name)
                    self._log_entry(
                        model_name,
                        field_name,
                        "skipped",
                        _("Access denied — run the scan as a user who can read this model."),
                    )
                continue

            results.append(
                {
                    "wizard_id": self.id,
                    "model_id": classification.model_id.id,
                    "model_name": model_name,
                    "field_name": field_name,
                    "classification_id": classification.id,
                    "total_records": total_records,
                    "records_with_data": records_with_data,
                    "encrypted_records": encrypted_count,
                    "needs_migration": max(0, records_with_data - encrypted_count),
                    "is_encrypted": is_encrypted,
                }
            )

        self.env["spp.encryption.migration.scan.result"].create(results)

        self.state = "ready"
        model_count = len({r["model_id"] for r in results})
        summary = _("Scan complete. Found %(fields)d PII fields across %(models)d models.") % {
            "fields": len(results),
            "models": model_count,
        }
        if skipped_models:
            summary += "\n" + _("%(count)d model(s) skipped (no read access) — see the Migration Log.") % {
                "count": len(skipped_models)
            }
        self.result_summary = summary

        return self._return_wizard()

    def action_dry_run(self):
        """Preview what the migration will do."""
        self.ensure_one()
        return self._run_migration(dry_run=True)

    def action_migrate(self):
        """Run the actual migration."""
        self.ensure_one()
        return self._run_migration(dry_run=False)

    def _run_migration(self, dry_run=False):
        """Execute the migration process.

        Args:
            dry_run: If True, only count what the migration would touch
        """
        self.state = "processing"
        self.progress = 0.0
        self.migration_log_ids.unlink()

        # Only fields with encryption support and pending records
        to_migrate = self.scan_result_ids.filtered(lambda r: r.needs_migration > 0 and r.is_encrypted)

        if not to_migrate:
            self.result_summary = _("No fields need migration.")
            self.state = "done"
            return self._return_wizard()

        total_records = sum(to_migrate.mapped("needs_migration"))
        processed = 0
        errors = []

        for scan_result in to_migrate:
            model_name = scan_result.model_name
            field_name = scan_result.field_name
            try:
                count, failed = self._migrate_field(scan_result, dry_run)
            except Exception as e:
                # A field-level failure (bad key setup, missing column, ...)
                # must not abort the remaining fields.
                errors.append(f"{model_name}.{field_name}: {e}")
                self._log_entry(model_name, field_name, "error", str(e))
                _logger.exception("Migration error for %s.%s", model_name, field_name)
                continue

            processed += count
            status = "dry_run" if dry_run else "success"
            action_label = _("Would process %(count)d records") if dry_run else _("Processed %(count)d records")
            self._log_entry(model_name, field_name, status, action_label % {"count": count})
            if failed:
                errors.append(
                    _("%(model)s.%(field)s: %(count)d record(s) failed — see the server log.")
                    % {"model": model_name, "field": field_name, "count": failed}
                )
                self._log_entry(
                    model_name,
                    field_name,
                    "error",
                    _("%(count)d record(s) failed — see the server log.") % {"count": failed},
                )

            self.progress = (processed / total_records) * 100 if total_records else 100

        if dry_run:
            self.result_summary = _("Dry run complete. Would process %(count)d records.") % {"count": processed}
        else:
            self.result_summary = _("Migration complete. Processed %(count)d records.") % {"count": processed}

        if errors:
            self.result_summary += "\n\n" + _("Errors (%(count)d):", count=len(errors)) + "\n" + "\n".join(errors)
            self.state = "error"
        else:
            self.state = "done"

        return self._return_wizard()

    def _pending_domain(self, field_name):
        """Domain matching records that hold data but no blind index yet."""
        index_field = f"{field_name}_index"
        return [
            (field_name, "!=", False),
            (field_name, "!=", ""),
            "|",
            (index_field, "=", False),
            (index_field, "=", ""),
        ]

    def _migrate_field(self, scan_result, dry_run=False):
        """Migrate a single field, batch by batch, until exhausted.

        Args:
            scan_result: The scan result to migrate
            dry_run: If True, only count matching records

        Returns:
            tuple: (records processed, records that failed)
        """
        model_name = scan_result.model_name
        field_name = scan_result.field_name
        Model = self.env[model_name]
        base_domain = self._pending_domain(field_name)

        if dry_run:
            # No writes happen in a dry run, so looping would never
            # converge — a count IS the preview.
            return Model.search_count(base_domain), 0

        processed = 0
        failed_ids = []
        while True:
            # Exclude records that already failed, otherwise a persistently
            # failing record would match forever and loop this batch.
            domain = base_domain if not failed_ids else [("id", "not in", failed_ids), *base_domain]
            records = Model.search(domain, limit=self.batch_size)
            if not records:
                break

            for record in records:
                try:
                    # Attribute access returns the raw stored value (the
                    # mixin decrypts only in read()); these records hold
                    # legacy plaintext, which is exactly what we re-write.
                    value = record[field_name]
                    if not value:
                        failed_ids.append(record.id)
                        continue
                    # The write-back goes through the encrypted-field
                    # mixin, which encrypts the value and computes the
                    # blind index.
                    record.write({field_name: value})
                    processed += 1
                except Exception:
                    failed_ids.append(record.id)
                    # Log ids only — never field values (PII).
                    _logger.exception("Error migrating record %s#%s", model_name, record.id)

            # Bound memory across large tables.
            self.env.flush_all()
            self.env.invalidate_all()

        return processed, len(failed_ids)

    def _log_entry(self, model_name, field_name, status, message):
        """Create a migration-log line."""
        self.env["spp.encryption.migration.log"].create(
            {
                "wizard_id": self.id,
                "model_name": model_name,
                "field_name": field_name,
                "status": status,
                "message": message,
                "timestamp": fields.Datetime.now(),
            }
        )

    def _return_wizard(self):
        """Return the wizard view."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class EncryptionMigrationScanResult(models.TransientModel):
    """Scan result for encryption migration."""

    _name = "spp.encryption.migration.scan.result"
    _description = "Encryption Migration Scan Result"

    wizard_id = fields.Many2one(
        comodel_name="spp.encryption.migration.wizard",
        ondelete="cascade",
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
    )
    # Plain copy of the technical name: readable by operators who cannot
    # read ir.model records
    model_name = fields.Char()
    field_name = fields.Char(string="Field")
    classification_id = fields.Many2one(comodel_name="spp.field.classification")
    total_records = fields.Integer()
    records_with_data = fields.Integer()
    encrypted_records = fields.Integer(string="Already Encrypted")
    needs_migration = fields.Integer()
    is_encrypted = fields.Boolean(string="Has Encryption Support")


class EncryptionMigrationLog(models.TransientModel):
    """Log entry for encryption migration."""

    _name = "spp.encryption.migration.log"
    _description = "Encryption Migration Log"

    wizard_id = fields.Many2one(
        comodel_name="spp.encryption.migration.wizard",
        ondelete="cascade",
    )
    model_name = fields.Char(string="Model")
    field_name = fields.Char(string="Field")
    status = fields.Selection(
        selection=[
            ("success", "Success"),
            ("dry_run", "Dry Run"),
            ("error", "Error"),
            ("skipped", "Skipped"),
        ],
    )
    message = fields.Text()
    timestamp = fields.Datetime()
