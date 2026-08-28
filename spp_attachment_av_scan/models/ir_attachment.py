import base64
import hashlib
import json
import logging

import psycopg2

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, ConcurrencyError, UserError

_logger = logging.getLogger(__name__)

#: Queueing a malware scan is best-effort — a scan that cannot be enqueued must not
#: block the attachment write. A **database** error is categorically different: it
#: leaves the transaction unusable, so swallowing one converts a recoverable fault
#: into an unrelated failure somewhere downstream.
#:
#: This is a superset of the classes ``odoo.service.model.retrying`` recovers from
#: by rolling back and re-running the request (``IntegrityError``, ``OperationalError``,
#: ``ConcurrencyError`` — see ``odoo/service/model.py``); the non-retryable rest of
#: ``psycopg2.Error`` then surfaces with the true traceback instead of poisoning
#: downstream code. ``SerializationFailure``
#: resolves through that tuple via
#: ``SerializationFailure -> TransactionRollbackError -> OperationalError``, so a
#: concurrent-update conflict on an attachment is retried transparently — *unless*
#: something catches it first.
_MUST_NOT_SWALLOW = (psycopg2.Error, ConcurrencyError)

QUARANTINE_PROVIDER_PARAM = "spp_attachment_av_scan.quarantine_encryption_provider_id"
QUARANTINE_RETENTION_DAYS_PARAM = "spp_attachment_av_scan.quarantine_retention_days"
DEFAULT_QUARANTINE_RETENTION_DAYS = 90
FORENSIC_DOWNLOAD_RETENTION_HOURS_PARAM = "spp_attachment_av_scan.forensic_download_retention_hours"
DEFAULT_FORENSIC_DOWNLOAD_RETENTION_HOURS = 24

PENDING_SWEEP_MIN_AGE_MINUTES_PARAM = "spp_attachment_av_scan.pending_sweep_min_age_minutes"
DEFAULT_PENDING_SWEEP_MIN_AGE_MINUTES = 60
PENDING_SWEEP_BATCH_SIZE_PARAM = "spp_attachment_av_scan.pending_sweep_batch_size"
DEFAULT_PENDING_SWEEP_BATCH_SIZE = 100
PENDING_SWEEP_MAX_ATTEMPTS_PARAM = "spp_attachment_av_scan.pending_sweep_max_attempts"
DEFAULT_PENDING_SWEEP_MAX_ATTEMPTS = 3

#: Models whose attachments the pending sweep leaves alone. These store their own
#: source-controlled binaries rather than user content: ``ir.ui.menu.web_icon_data`` is
#: rewritten by every module upgrade that reloads the menu's XML, and scanning our own
#: icon PNGs has near-zero value.
#:
#: A blank ``res_model`` is *not* a proxy for this set. ``Binary(attachment=True)``
#: storage records the owning model, so a menu icon arrives as
#: ``res_model='ir.ui.menu'``, ``res_field='web_icon_data'``. Excluding all field
#: storage would be worse still: a user-uploaded ``res.partner.image_1920`` is field
#: storage too, and it is exactly the content this sweep exists for.
SWEEP_EXCLUDED_MODELS = ("ir.ui.menu",)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    scan_status = fields.Selection(
        [
            ("pending", "Pending Scan"),
            ("scanning", "Scanning"),
            ("clean", "Clean"),
            ("infected", "Infected"),
            ("error", "Scan Error"),
            ("skipped", "Skipped"),
        ],
        default="pending",
        index=True,
        help="Status of the malware scan for this attachment",
    )
    scan_date = fields.Datetime(
        string="Scan Date",
        help="Date and time when the file was scanned",
    )
    scan_result = fields.Text(
        string="Scan Result Details",
        help="Detailed scan result in JSON format",
    )
    threat_name = fields.Char(
        string="Threat Name",
        help="Name of the detected threat if file is infected",
    )
    is_quarantined = fields.Boolean(
        string="Quarantined",
        default=False,
        index=True,
        help="Whether this file has been quarantined due to malware detection",
    )

    # Encrypted quarantine storage fields
    quarantine_data = fields.Binary(
        string="Encrypted Quarantine Data",
        attachment=False,
        help="Encrypted copy of the infected file for forensic analysis",
    )
    quarantine_hash = fields.Char(
        string="File SHA256 Hash",
        help="SHA256 hash of the original infected file for verification",
    )
    quarantine_date = fields.Datetime(
        string="Quarantine Date",
        help="Date and time when the file was quarantined",
    )
    original_file_size = fields.Integer(
        string="Original File Size",
        help="Size of the original file in bytes before quarantine",
    )

    # Forensic download tracking
    is_forensic_download = fields.Boolean(
        string="Forensic Download",
        default=False,
        index=True,
        help="Marks temporary attachments created for forensic analysis downloads",
    )

    scan_queue_attempts = fields.Integer(
        string="Scan Queue Attempts",
        default=0,
        readonly=True,
        help=(
            "Number of times the pending-scan sweep has re-queued this attachment. "
            "Bounds the retries for a record that cannot be scanned, so a broken queue "
            "is not retried at full rate forever. Reset whenever the file's bytes change "
            "or an administrator triggers a rescan."
        ),
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to queue malware scan for binary attachments."""
        attachments = super().create(vals_list)

        # Never enqueue while the registry is still loading. Everything written then is
        # a system asset — module data records, and the ``ir.attachment`` backing
        # ``ir.ui.menu.web_icon_data``, which every menu carrying a ``web_icon`` rewrites
        # whenever its XML is (re)loaded. Enqueueing there inserts a ``queue.job`` row,
        # which flushes the pending ``ir_attachment`` UPDATE inside a hook that re-raises
        # database errors (see ``_MUST_NOT_SWALLOW``). Registry construction has no
        # ``odoo.service.model.retrying`` wrapper around it, so a transient serialization
        # failure against a peer instance on a shared database aborts the whole load
        # instead of being retried. The records keep the ``scan_status`` default
        # ("pending"), so nothing is left looking scanned. Runtime uploads still queue.
        if not self.env.registry.ready:
            return attachments

        # Queue scan for attachments that have binary data
        for attachment in attachments:
            if attachment.type == "binary" and attachment.datas:
                try:
                    # Queue the scan job
                    attachment.with_delay(
                        description=f"Scan attachment {attachment.id} for malware",
                        priority=20,
                    )._scan_for_malware()
                    _logger.info("Queued malware scan for attachment ID %s", attachment.id)
                except _MUST_NOT_SWALLOW:
                    # Never swallow: see ``_MUST_NOT_SWALLOW``. Re-raise so the
                    # request is rolled back and retried instead of continuing on a
                    # dead transaction.
                    raise
                except Exception as error:
                    _logger.error(
                        "Failed to queue malware scan for attachment ID %s: %s",
                        attachment.id,
                        str(error),
                    )

        return attachments

    def write(self, vals):
        """Override write to queue scan if binary data is updated."""
        result = super().write(vals)

        if "datas" in vals and not self.env.context.get("skip_av_scan_queue"):
            for attachment in self:
                if attachment.type == "binary" and attachment.datas:
                    try:
                        attachment.with_context(skip_av_scan_queue=True).write(
                            {
                                "scan_status": "pending",
                                "scan_date": None,
                                "scan_result": None,
                                "threat_name": None,
                                "is_quarantined": False,
                                "quarantine_data": None,
                                "quarantine_hash": None,
                                "quarantine_date": None,
                                "original_file_size": None,
                                # New bytes are a new scan need: the previous file's
                                # sweep budget must not carry over and strand this one.
                                "scan_queue_attempts": 0,
                            }
                        )
                        if not self.env.registry.ready:
                            # Same reasoning as ``create``: no scan may be enqueued during
                            # registry load. The status reset above still runs — it is a
                            # cache-level write on a row this transaction already dirtied,
                            # so it adds no SQL and no conflict window, and skipping it
                            # would leave changed bytes wearing a stale "clean" status.
                            continue
                        attachment.with_delay(
                            description=f"Scan updated attachment {attachment.id} for malware",
                            priority=20,
                        )._scan_for_malware()
                        _logger.info(
                            "Queued malware scan for updated attachment ID %s",
                            attachment.id,
                        )
                    except _MUST_NOT_SWALLOW:
                        # Never swallow: see ``_MUST_NOT_SWALLOW``. This is the exact
                        # site that turned a transient "could not serialize access due
                        # to concurrent update" on an attachment into an
                        # InFailedSqlTransaction reported from an unrelated menu-icon
                        # lookup, on every module upgrade, with the real cause visible
                        # only as a stray ERROR line in the server log.
                        raise
                    except Exception as error:
                        _logger.error(
                            "Failed to queue malware scan for updated attachment ID %s: %s",
                            attachment.id,
                            str(error),
                        )

        return result

    def _scan_for_malware(self):
        """Scan attachment for malware using configured antivirus backend."""
        self.ensure_one()

        if self.type != "binary" or not self.datas:
            _logger.info(
                "Skipping scan for attachment ID %s (not binary or no data)",
                self.id,
            )
            self.write(
                {
                    "scan_status": "skipped",
                    "scan_date": fields.Datetime.now(),
                    "scan_result": json.dumps(
                        {
                            "status": "skipped",
                            "reason": "Not a binary attachment or no data",
                        }
                    ),
                }
            )
            return

        scanner_backend = self.env["spp.av.scanner.backend"].get_active_scanner()
        if not scanner_backend:
            _logger.warning("No active antivirus scanner backend configured")
            self.write(
                {
                    "scan_status": "skipped",
                    "scan_date": fields.Datetime.now(),
                    "scan_result": json.dumps(
                        {
                            "status": "skipped",
                            "reason": "No active scanner backend configured",
                        }
                    ),
                }
            )
            return

        try:
            self.write({"scan_status": "scanning"})

            # Decode binary data once and reuse to avoid race conditions
            # In Odoo, self.datas is always base64-encoded (str or bytes)
            # Ensure raw_binary_data is always bytes to avoid TypeError in scan_binary()
            raw_binary_data = base64.b64decode(self.datas) if self.datas else b""

            scan_result = scanner_backend.scan_binary(
                raw_binary_data,
                filename=self.name,
            )

            scan_status = scan_result.get("status", "error")
            threat_name = scan_result.get("threat_name")

            vals = {
                "scan_status": scan_status,
                "scan_date": fields.Datetime.now(),
                "scan_result": json.dumps(scan_result),
                "threat_name": threat_name,
            }

            if scan_status == "infected":
                vals["is_quarantined"] = True
                self.write(vals)
                # Pass binary_data to avoid re-reading from self.datas (race condition fix)
                self._quarantine(binary_data=raw_binary_data)
                self._notify_security_admins()
            else:
                self.write(vals)

            _logger.info(
                "Malware scan completed for attachment ID %s: %s",
                self.id,
                scan_status,
            )

        except Exception as error:
            _logger.error(
                "Error scanning attachment ID %s for malware: %s",
                self.id,
                str(error),
                exc_info=True,
            )
            self.write(
                {
                    "scan_status": "error",
                    "scan_date": fields.Datetime.now(),
                    "scan_result": json.dumps(
                        {
                            "status": "error",
                            "error": str(error),
                        }
                    ),
                }
            )

    def _get_quarantine_encryption_provider(self):
        """Get or create the encryption provider for quarantine storage."""
        ICP = self.env["ir.config_parameter"].sudo()  # nosemgrep
        provider_id = ICP.get_param(QUARANTINE_PROVIDER_PARAM)

        if provider_id:
            provider = self.env["spp.encryption.provider"].sudo().browse(int(provider_id))  # nosemgrep
            if provider.exists():
                return provider

        provider = (
            self.env["spp.encryption.provider"]  # nosemgrep
            .sudo()
            .search([("type", "=", "jwcrypto")], order="id asc", limit=1)
        )

        if not provider:
            _logger.warning(
                "No encryption provider configured for quarantine. Files will be quarantined without encryption."
            )
            return None

        ICP.set_param(QUARANTINE_PROVIDER_PARAM, str(provider.id))
        return provider

    def _calculate_file_hash(self, binary_data):
        """Calculate SHA256 hash of file data."""
        if isinstance(binary_data, str):
            binary_data = base64.b64decode(binary_data)
        return hashlib.sha256(binary_data).hexdigest()

    def _quarantine(self, binary_data=None):
        """Quarantine infected file with encrypted storage.

        Args:
            binary_data: Raw binary data to quarantine. If not provided, reads from self.datas.
                         Passing binary_data avoids race conditions when data may change.
        """
        self.ensure_one()

        if self.scan_status != "infected":
            return

        _logger.warning(
            "Quarantining infected attachment ID %s (threat: %s)",
            self.id,
            self.threat_name or "Unknown",
        )

        try:
            # Use provided binary_data to avoid race condition, or fall back to self.datas
            if binary_data is None:
                binary_data = base64.b64decode(self.datas) if self.datas else b""
            if not binary_data:
                _logger.warning("No binary data to quarantine for attachment ID %s", self.id)
                return

            file_hash = self._calculate_file_hash(binary_data)
            file_size = len(binary_data)

            encryption_provider = self._get_quarantine_encryption_provider()

            if encryption_provider:
                try:
                    encrypted_data = encryption_provider.encrypt_data(binary_data)
                    quarantine_data = base64.b64encode(encrypted_data)
                    _logger.info(
                        "Encrypted quarantined file for attachment ID %s (hash: %s)",
                        self.id,
                        file_hash,
                    )
                except Exception as enc_error:
                    _logger.error(
                        "Failed to encrypt quarantined file for attachment ID %s: %s",
                        self.id,
                        str(enc_error),
                    )
                    quarantine_data = None
            else:
                quarantine_data = None

            self.with_context(skip_av_scan_queue=True).write(
                {
                    "is_quarantined": True,
                    "quarantine_data": quarantine_data,
                    "quarantine_hash": file_hash,
                    "quarantine_date": fields.Datetime.now(),
                    "original_file_size": file_size,
                    "datas": False,
                }
            )

            _logger.warning(
                "Quarantined attachment ID %s - Original data removed, "
                "encrypted backup stored (hash: %s, size: %d bytes)",
                self.id,
                file_hash,
                file_size,
            )

        except Exception as error:
            _logger.error(
                "Error during quarantine of attachment ID %s: %s",
                self.id,
                str(error),
                exc_info=True,
            )
            self.with_context(skip_av_scan_queue=True).write(
                {
                    "is_quarantined": True,
                    "quarantine_date": fields.Datetime.now(),
                }
            )

    def _notify_security_admins(self):
        """Send notification to security administrators about infected file."""
        self.ensure_one()

        if self.scan_status != "infected":
            return

        _logger.warning(
            "Infected file detected - Attachment ID: %s, Threat: %s",
            self.id,
            self.threat_name or "Unknown",
        )

        try:
            security_group = self.env.ref("spp_attachment_av_scan.group_av_admin", raise_if_not_found=False)
            if not security_group:
                _logger.warning("AV Admin group not found, cannot notify administrators")
                return

            admin_users = security_group.user_ids

            if not admin_users:
                _logger.warning("No users in AV Admin group to notify")
                return

            # Send notification to admin users via internal message
            message_body = _(
                "<p><strong>Malware Detected in Attachment</strong></p>"
                "<ul>"
                "<li>File: %(name)s</li>"
                "<li>Threat: %(threat)s</li>"
                "<li>Hash: %(hash)s</li>"
                "<li>Date: %(date)s</li>"
                "<li>Status: Quarantined and encrypted</li>"
                "</ul>",
                name=self.name,
                threat=self.threat_name or "Unknown",
                hash=self.quarantine_hash or "N/A",
                date=self.scan_date,
            )

            # Create notification for each admin user
            self.env["mail.message"].sudo().create(  # nosemgrep
                {
                    "message_type": "notification",
                    "subject": _("Security Alert: Infected File Detected"),
                    "body": message_body,
                    "partner_ids": [Command.set(admin_users.mapped("partner_id").ids)],
                    "model": "ir.attachment",
                    "res_id": self.id,
                }
            )

            _logger.info(
                "Notified %d security administrators about infected file",
                len(admin_users),
            )

        except Exception as error:
            _logger.error(
                "Failed to notify security admins about infected file: %s",
                str(error),
            )

    def _check_av_admin_access(self):
        """Check if current user has AV Admin access."""
        self.ensure_one()
        if not self.env.user.has_group("spp_attachment_av_scan.group_av_admin"):
            raise AccessError(_("Only Antivirus Administrators can perform this action."))

    def action_restore_quarantined(self):
        """Restore a quarantined file (for false positives). AV Admin only."""
        self.ensure_one()
        self._check_av_admin_access()

        if not self.is_quarantined:
            raise UserError(_("This attachment is not quarantined."))

        if not self.quarantine_data:
            raise UserError(_("No encrypted backup available for this quarantined file."))

        encryption_provider = self._get_quarantine_encryption_provider()
        if not encryption_provider:
            raise UserError(_("No encryption provider configured. Cannot decrypt the file."))

        try:
            encrypted_data = base64.b64decode(self.quarantine_data)
            decrypted_data = encryption_provider.decrypt_data(encrypted_data)

            # Validate decrypted file size matches original
            if self.original_file_size and len(decrypted_data) != self.original_file_size:
                raise UserError(
                    _(
                        "File size mismatch. Expected %(expected)d bytes, got %(actual)d bytes.",
                        expected=self.original_file_size,
                        actual=len(decrypted_data),
                    )
                )

            restored_hash = self._calculate_file_hash(decrypted_data)
            if restored_hash != self.quarantine_hash:
                raise UserError(_("File integrity check failed. The restored file hash does not match."))

            # SECURITY: sudo() is intentional - AV admin access verified via _check_av_admin_access()
            # nosemgrep: semgrep.odoo-sudo-without-context
            self.sudo().with_context(skip_av_scan_queue=True).write(
                {
                    "datas": base64.b64encode(decrypted_data),
                    "is_quarantined": False,
                    "scan_status": "clean",
                    "quarantine_data": False,
                    "quarantine_hash": False,
                    "quarantine_date": False,
                    "original_file_size": False,
                    "threat_name": False,
                    "scan_result": json.dumps(
                        {
                            "status": "restored",
                            "reason": "Manually restored by administrator",
                            "restored_by": self.env.user.name,
                            "restored_date": fields.Datetime.now().isoformat(),
                        }
                    ),
                }
            )

            _logger.warning(
                "Quarantined attachment ID %s restored by user %s",
                self.id,
                self.env.user.name,
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("File Restored"),
                    "message": _("The quarantined file has been restored successfully."),
                    "type": "success",
                    "sticky": False,
                },
            }

        except UserError:
            raise
        except Exception as error:
            _logger.error(
                "Failed to restore quarantined attachment ID %s: %s",
                self.id,
                str(error),
                exc_info=True,
            )
            raise UserError(_("Failed to restore file: %(error)s", error=str(error))) from error

    def action_download_quarantined_for_analysis(self):
        """Download quarantined file for forensic analysis. AV Admin only."""
        self.ensure_one()
        self._check_av_admin_access()

        if not self.is_quarantined:
            raise UserError(_("This attachment is not quarantined."))

        if not self.quarantine_data:
            raise UserError(_("No encrypted backup available for this quarantined file."))

        encryption_provider = self._get_quarantine_encryption_provider()
        if not encryption_provider:
            raise UserError(_("No encryption provider configured. Cannot decrypt the file."))

        try:
            encrypted_data = base64.b64decode(self.quarantine_data)
            decrypted_data = encryption_provider.decrypt_data(encrypted_data)

            # Validate decrypted file size matches original
            if self.original_file_size and len(decrypted_data) != self.original_file_size:
                raise UserError(
                    _(
                        "File size mismatch. Expected %(expected)d bytes, got %(actual)d bytes.",
                        expected=self.original_file_size,
                        actual=len(decrypted_data),
                    )
                )

            download_attachment = (
                self.env["ir.attachment"]  # nosemgrep
                .sudo()
                .with_context(skip_av_scan_queue=True)
                .create(
                    {
                        "name": f"QUARANTINED_{self.name}",
                        "datas": base64.b64encode(decrypted_data),
                        "mimetype": "application/octet-stream",
                        "type": "binary",
                        "res_model": "ir.attachment",
                        "res_id": self.id,
                        # Mark as forensic download for cleanup
                        "is_forensic_download": True,
                        "scan_status": "skipped",
                        "scan_result": json.dumps(
                            {
                                "status": "skipped",
                                "reason": "Forensic download - original quarantined file",
                            }
                        ),
                    }
                )
            )

            _logger.warning(
                "Quarantined attachment ID %s downloaded for analysis by user %s",
                self.id,
                self.env.user.name,
            )

            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{download_attachment.id}?download=true",
                "target": "self",
            }

        except UserError:
            raise
        except Exception as error:
            _logger.error(
                "Failed to download quarantined attachment ID %s: %s",
                self.id,
                str(error),
                exc_info=True,
            )
            raise UserError(_("Failed to download file: %(error)s", error=str(error))) from error

    def action_permanently_delete_quarantined(self):
        """Permanently delete quarantined file and its encrypted backup. AV Admin only."""
        self.ensure_one()
        self._check_av_admin_access()

        if not self.is_quarantined:
            raise UserError(_("This attachment is not quarantined."))

        _logger.warning(
            "Permanently deleting quarantined attachment ID %s (hash: %s) by user %s",
            self.id,
            self.quarantine_hash or "N/A",
            self.env.user.name,
        )

        # SECURITY: sudo() is intentional - AV admin access verified via _check_av_admin_access()
        # nosemgrep: semgrep.odoo-sudo-without-context
        self.sudo().with_context(skip_av_scan_queue=True).write(
            {
                "quarantine_data": False,
                "datas": False,
            }
        )

        # nosemgrep: semgrep.odoo-sudo-without-context
        self.sudo().unlink()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("File Deleted"),
                "message": _("The quarantined file has been permanently deleted."),
                "type": "warning",
                "sticky": False,
            },
        }

    def action_rescan(self):
        """Manually trigger a rescan of the attachment."""
        for attachment in self:
            if attachment.is_quarantined:
                raise UserError(_("Cannot rescan a quarantined file. Restore it first if needed."))

            if attachment.type != "binary" or not attachment.datas:
                raise UserError(_("Cannot scan attachment: not a binary file or no data present."))

            attachment.write(
                {
                    "scan_status": "pending",
                    "scan_date": None,
                    "scan_result": None,
                    "threat_name": None,
                    # A human asking for a rescan re-arms the sweep, so a record that
                    # exhausted its attempts is not left beyond its reach.
                    "scan_queue_attempts": 0,
                }
            )

            try:
                attachment.with_delay(
                    description=f"Manual rescan of attachment {attachment.id}",
                    priority=10,
                )._scan_for_malware()

                _logger.info("Queued manual rescan for attachment ID %s", attachment.id)

            except Exception as error:
                _logger.error(
                    "Failed to queue manual rescan for attachment ID %s: %s",
                    attachment.id,
                    str(error),
                )
                raise UserError(_("Failed to queue rescan: %(error)s", error=str(error))) from error

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Rescan Queued"),
                "message": _("The attachment(s) have been queued for scanning."),
                "type": "success",
                "sticky": False,
            },
        }

    def read(self, fields=None, load="_classic_read"):
        """Override read to block access to quarantined files."""
        result = super().read(fields=fields, load=load)

        if fields and "datas" in fields:
            for record in result:
                attachment = self.browse(record["id"])
                if attachment.is_quarantined:
                    _logger.warning(
                        "Blocked access to quarantined attachment ID %s",
                        attachment.id,
                    )
                    record["datas"] = False

        return result

    @api.model
    def _cron_purge_old_quarantined_files(self):
        """Scheduled job to purge quarantined files older than retention period."""
        ICP = self.env["ir.config_parameter"].sudo()  # nosemgrep
        retention_days = int(ICP.get_param(QUARANTINE_RETENTION_DAYS_PARAM, DEFAULT_QUARANTINE_RETENTION_DAYS))

        if retention_days <= 0:
            _logger.info("Quarantine purge disabled (retention_days <= 0)")
            return

        cutoff_date = fields.Datetime.subtract(fields.Datetime.now(), days=retention_days)

        old_quarantined = self.search(
            [
                ("is_quarantined", "=", True),
                ("quarantine_date", "<", cutoff_date),
                ("quarantine_date", "!=", False),
            ]
        )

        if not old_quarantined:
            _logger.info("No quarantined files older than %d days to purge", retention_days)
            return

        _logger.info(
            "Purging %d quarantined files older than %d days",
            len(old_quarantined),
            retention_days,
        )

        for attachment in old_quarantined:
            _logger.info(
                "Purging old quarantined attachment ID %s (hash: %s, quarantine_date: %s)",
                attachment.id,
                attachment.quarantine_hash or "N/A",
                attachment.quarantine_date,
            )
            attachment.with_context(skip_av_scan_queue=True).write(
                {
                    "quarantine_data": False,
                }
            )

        _logger.info("Purged encrypted data from %d old quarantined files", len(old_quarantined))

    @api.model
    def _cron_cleanup_forensic_downloads(self):
        """Scheduled job to clean up temporary forensic download attachments.

        Forensic download attachments are temporary files created for admin analysis.
        They should be cleaned up after a short retention period (default: 24 hours).
        """
        ICP = self.env["ir.config_parameter"].sudo()  # nosemgrep
        retention_hours = int(
            ICP.get_param(
                FORENSIC_DOWNLOAD_RETENTION_HOURS_PARAM,
                DEFAULT_FORENSIC_DOWNLOAD_RETENTION_HOURS,
            )
        )

        if retention_hours <= 0:
            _logger.info("Forensic download cleanup disabled (retention_hours <= 0)")
            return

        cutoff_date = fields.Datetime.subtract(fields.Datetime.now(), hours=retention_hours)

        old_forensic_downloads = self.search(
            [
                ("is_forensic_download", "=", True),
                ("create_date", "<", cutoff_date),
            ]
        )

        if not old_forensic_downloads:
            _logger.info("No forensic download attachments older than %d hours to clean up", retention_hours)
            return

        _logger.info(
            "Cleaning up %d forensic download attachments older than %d hours. IDs: %s",
            len(old_forensic_downloads),
            retention_hours,
            old_forensic_downloads.ids,
        )

        # Delete all old forensic downloads in batch
        old_forensic_downloads.sudo().with_context(skip_av_scan_queue=True).unlink()  # nosemgrep

    @api.model
    def _pending_sweep_env(self):
        """The recordset the sweep must search through to see everything it covers.

        ``ir.attachment._search`` silently ANDs ``res_field = False`` into any domain
        that does not mention ``res_field`` or ``id``, which hides every attachment
        backing a ``Binary(attachment=True)`` field. Left implicit that would quietly
        drop user-uploaded field content — ``res.partner.image_1920`` and friends — from
        a security sweep, while appearing to cover it. ``skip_res_field_check`` opts back
        in, and ``SWEEP_EXCLUDED_MODELS`` then carries the exclusion the implicit filter
        was giving us by accident.
        """
        return self.with_context(skip_res_field_check=True)

    @api.model
    def _pending_sweep_domain(self, cutoff_date):
        """Attachments stranded at ``pending``, before the attempt budget is applied.

        ``write_date``, not ``create_date``, carries the age: a ``datas`` write resets an
        old record back to ``pending``, so a ``create_date`` cutoff would re-queue it the
        instant the hooks already did. It also means bumping ``scan_queue_attempts``
        refreshes the clock, which gives the retries a flat backoff for free. The
        trade-off is that a record under constant unrelated writes never ages in —
        acceptable, because a change to its *bytes* goes back through the hooks anyway.
        """
        return [
            ("scan_status", "=", "pending"),
            ("type", "=", "binary"),
            ("file_size", ">", 0),
            ("write_date", "<", cutoff_date),
            # ``action_rescan`` refuses a quarantined file; the sweep must agree.
            ("is_quarantined", "=", False),
            # A forensic download is a short-lived admin copy of a file already known
            # infected. Scanning it tells us nothing we do not already know.
            ("is_forensic_download", "=", False),
            # User content only: an attachment with no ``res_model`` hangs off no business
            # record, which is module data and standalone system files.
            ("res_model", "!=", False),
            ("res_model", "not in", list(SWEEP_EXCLUDED_MODELS)),
        ]

    @api.model
    def _cron_sweep_pending_scans(self):
        """Re-queue malware scans for attachments stranded at ``scan_status = pending``.

        Queueing a scan is best-effort — the ``create``/``write`` hooks swallow every
        non-database failure so a dead broker cannot block an attachment write. Without
        this sweep nothing comes back for the records that leaves behind: written, at the
        ``pending`` default, indistinguishable in the UI from a file still waiting its
        turn in a deep queue, and reachable only by a human clicking ``action_rescan``.
        Registry-load writes (see ``create``) land in the same state, benignly.

        Bounded on both axes so this is safe to leave enabled on an existing database: a
        batch limit caps one run, and ``scan_queue_attempts`` caps the total attempts per
        record. A record that cannot be enqueued therefore stops being retried instead of
        failing loudly on every tick.
        """
        ICP = self.env["ir.config_parameter"].sudo()  # nosemgrep
        min_age_minutes = int(ICP.get_param(PENDING_SWEEP_MIN_AGE_MINUTES_PARAM, DEFAULT_PENDING_SWEEP_MIN_AGE_MINUTES))
        batch_size = int(ICP.get_param(PENDING_SWEEP_BATCH_SIZE_PARAM, DEFAULT_PENDING_SWEEP_BATCH_SIZE))
        max_attempts = int(ICP.get_param(PENDING_SWEEP_MAX_ATTEMPTS_PARAM, DEFAULT_PENDING_SWEEP_MAX_ATTEMPTS))

        if batch_size <= 0 or max_attempts <= 0:
            _logger.info("Pending scan sweep disabled (batch_size or max_attempts <= 0)")
            return

        cutoff_date = fields.Datetime.subtract(fields.Datetime.now(), minutes=min_age_minutes)
        sweep = self._pending_sweep_env()
        domain = self._pending_sweep_domain(cutoff_date)

        # Oldest stranded first, so successive runs advance through a backlog instead of
        # re-picking the head of it.
        stranded = sweep.search(
            domain + [("scan_queue_attempts", "<", max_attempts)],
            limit=batch_size,
            order="write_date asc, id asc",
        )

        if not stranded:
            _logger.debug("Pending scan sweep found nothing stranded older than %d minutes", min_age_minutes)
            return

        requeued_ids = []
        failed_ids = []

        for attachment in stranded:
            # Counted for every record the batch picks up, and counted even when the
            # enqueue succeeds: a job accepted by a queue whose worker never runs it
            # strands the record just as thoroughly as a rejected one. Counting first
            # also guarantees the batch makes progress — an unreadable record that never
            # bumped its counter would sort to the head of every run forever and eat a
            # slot each time.
            attachment.with_context(skip_av_scan_queue=True).write(
                {"scan_queue_attempts": attachment.scan_queue_attempts + 1}
            )

            # The payload is read only to prove it is readable — the queued job re-reads
            # the bytes in its own transaction. Evict it immediately: binary fields are
            # never evicted on their own, so a full batch would otherwise hold every
            # payload in this one transaction's cache simultaneously.
            readable = bool(attachment.datas)
            attachment.invalidate_recordset(["datas", "raw"])
            if not readable:
                # ``file_size`` says there are bytes but they cannot be read — a lost
                # filestore file. Nothing to scan, and the attempt cap will retire it.
                failed_ids.append(attachment.id)
                _logger.debug(
                    "Pending scan sweep found no readable data on attachment ID %s",
                    attachment.id,
                )
                continue

            try:
                attachment.with_delay(
                    description=f"Sweep re-queue of stranded attachment {attachment.id} for malware scan",
                    priority=30,
                )._scan_for_malware()
                requeued_ids.append(attachment.id)
                _logger.debug("Pending scan sweep re-queued attachment ID %s", attachment.id)
            except _MUST_NOT_SWALLOW:
                # Never swallow: see ``_MUST_NOT_SWALLOW``. The transaction is unusable,
                # so continuing the loop would only bury the real cause.
                raise
            except Exception as error:
                failed_ids.append(attachment.id)
                _logger.debug(
                    "Pending scan sweep could not re-queue attachment ID %s: %s",
                    attachment.id,
                    str(error),
                )

        if requeued_ids:
            _logger.info(
                "Pending scan sweep re-queued %d stranded attachment(s). IDs: %s",
                len(requeued_ids),
                requeued_ids,
            )

        # One line per run, not one per record per tick: a broken queue is reported, not
        # screamed about, and the attempt cap stops it recurring indefinitely.
        if failed_ids:
            _logger.warning(
                "Pending scan sweep could not re-queue %d stranded attachment(s). IDs: %s",
                len(failed_ids),
                failed_ids,
            )

        exhausted_count = sweep.search_count(domain + [("scan_queue_attempts", ">=", max_attempts)])
        if exhausted_count:
            _logger.warning(
                "%d attachment(s) remain unscanned after %d sweep attempts and will not be retried; "
                "use the Rescan action once the scan queue is healthy",
                exhausted_count,
                max_attempts,
            )
