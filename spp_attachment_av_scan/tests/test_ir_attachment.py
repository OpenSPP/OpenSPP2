import base64
import logging
from unittest.mock import MagicMock, patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestIrAttachment(TransactionCase):
    """Test cases for ir.attachment with AV scanning."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attachment_model = cls.env["ir.attachment"]
        cls.scanner_backend_model = cls.env["spp.av.scanner.backend"]

        # Create a test scanner backend
        cls.scanner_backend = cls.scanner_backend_model.create(
            {
                "name": "Test Scanner",
                "backend_type": "clamd_socket",
                "is_active": True,
            }
        )

    def test_attachment_default_scan_status(self):
        """Test that new attachments have pending scan status."""
        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "datas": base64.b64encode(b"test content"),
            }
        )

        self.assertEqual(attachment.scan_status, "pending")
        self.assertFalse(attachment.is_quarantined)

    def test_create_attachment_queues_scan(self):
        """Test that creating binary attachment queues/processes scan."""
        # When job_worker is installed, the scan is queued automatically
        # In test mode, the job may run synchronously
        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "type": "binary",
                "datas": base64.b64encode(b"test content"),
            }
        )

        # The attachment should be created successfully
        self.assertTrue(attachment.exists())
        # Status should be pending (queued) or already processed
        self.assertIn(attachment.scan_status, ["pending", "clean", "error", "skipped"])

    def test_scan_non_binary_attachment(self):
        """Test that non-binary attachments are skipped."""
        attachment = self.attachment_model.create(
            {
                "name": "test.url",
                "type": "url",
                "url": "https://example.com",
            }
        )

        attachment._scan_for_malware()

        self.assertEqual(attachment.scan_status, "skipped")
        self.assertIn("Not a binary attachment", attachment.scan_result)

    def test_scan_no_active_backend(self):
        """Test scanning when no active backend is configured."""
        # Deactivate all backends
        self.scanner_backend.is_active = False

        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "type": "binary",
                "datas": base64.b64encode(b"test content"),
            }
        )

        attachment._scan_for_malware()

        self.assertEqual(attachment.scan_status, "skipped")
        self.assertIn("No active scanner", attachment.scan_result)

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_scan_clean_file(self, mock_pyclamd):
        """Test scanning a clean file."""
        # Mock ClamAV scanner
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = None  # Clean
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        attachment = self.attachment_model.create(
            {
                "name": "clean.txt",
                "type": "binary",
                "datas": base64.b64encode(b"clean content"),
            }
        )

        attachment._scan_for_malware()

        self.assertEqual(attachment.scan_status, "clean")
        self.assertFalse(attachment.is_quarantined)
        self.assertFalse(attachment.threat_name)  # Odoo Char fields are False when empty
        self.assertTrue(attachment.scan_date)

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_scan_infected_file(self, mock_pyclamd):
        """Test scanning an infected file."""
        # Mock ClamAV scanner
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Eicar-Test-Signature")}
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        attachment = self.attachment_model.create(
            {
                "name": "virus.exe",
                "type": "binary",
                "datas": base64.b64encode(b"virus content"),
            }
        )

        attachment._scan_for_malware()

        self.assertEqual(attachment.scan_status, "infected")
        self.assertTrue(attachment.is_quarantined)
        self.assertEqual(attachment.threat_name, "Eicar-Test-Signature")
        self.assertIsNotNone(attachment.scan_date)

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_scan_error_handling(self, mock_pyclamd):
        """Test error handling during scan."""
        # Mock ClamAV scanner to raise exception
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.side_effect = Exception("Scan failed")
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "type": "binary",
                "datas": base64.b64encode(b"test content"),
            }
        )

        attachment._scan_for_malware()

        self.assertEqual(attachment.scan_status, "error")
        self.assertIn("error", attachment.scan_result.lower())

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_quarantined_file_read_blocked(self, mock_pyclamd):
        """Test that quarantined files cannot be read."""
        # Mock ClamAV scanner
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Eicar-Test-Signature")}
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        attachment = self.attachment_model.create(
            {
                "name": "virus.exe",
                "type": "binary",
                "datas": base64.b64encode(b"virus content"),
            }
        )

        attachment._scan_for_malware()

        # Try to read the attachment
        result = attachment.read(["datas"])

        # Verify datas is blocked
        self.assertFalse(result[0]["datas"])

    def test_action_rescan(self):
        """Test manual rescan action."""
        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "type": "binary",
                "datas": base64.b64encode(b"test content"),
            }
        )
        # Set to clean to simulate previous scan
        attachment.with_context(skip_av_scan_queue=True).write(
            {
                "scan_status": "clean",
            }
        )

        result = attachment.action_rescan()

        # Verify scan was queued - status should be pending
        self.assertEqual(attachment.scan_status, "pending")
        self.assertEqual(result["type"], "ir.actions.client")

    def test_action_rescan_non_binary(self):
        """Test that rescanning non-binary attachment raises error."""
        attachment = self.attachment_model.create(
            {
                "name": "test.url",
                "type": "url",
                "url": "https://example.com",
            }
        )

        with self.assertRaises(UserError):
            attachment.action_rescan()

    def test_write_datas_queues_rescan(self):
        """Test that updating datas field queues rescan."""
        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "type": "binary",
                "datas": base64.b64encode(b"original content"),
            }
        )
        # Set to clean to simulate previous scan
        attachment.with_context(skip_av_scan_queue=True).write(
            {
                "scan_status": "clean",
            }
        )

        # Update the datas field
        attachment.write(
            {
                "datas": base64.b64encode(b"updated content"),
            }
        )

        # Verify rescan was queued - status should be pending
        self.assertEqual(attachment.scan_status, "pending")


@tagged("post_install", "-at_install")
class TestEncryptedQuarantine(TransactionCase):
    """Test cases for encrypted quarantine functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attachment_model = cls.env["ir.attachment"]
        cls.scanner_backend_model = cls.env["spp.av.scanner.backend"]
        cls.encryption_provider_model = cls.env["spp.encryption.provider"]

        # Create a test scanner backend
        cls.scanner_backend = cls.scanner_backend_model.create(
            {
                "name": "Test Scanner",
                "backend_type": "clamd_socket",
                "is_active": True,
            }
        )

        # Create AV admin user for testing admin actions
        cls.av_admin_group = cls.env.ref("spp_attachment_av_scan.group_av_admin")
        cls.av_admin_user = cls.env["res.users"].create(
            {
                "name": "AV Admin",
                "login": "av_admin_test",
                "group_ids": [Command.link(cls.av_admin_group.id), Command.link(cls.env.ref("base.group_user").id)],
            }
        )

        # Create regular user without AV admin access
        cls.regular_user = cls.env["res.users"].create(
            {
                "name": "Regular User",
                "login": "regular_user_test",
                "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_quarantine_stores_hash(self, mock_pyclamd):
        """Test that quarantine stores file hash correctly."""
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Test-Virus")}
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        original_content = b"infected file content"
        attachment = self.attachment_model.create(
            {
                "name": "virus.exe",
                "type": "binary",
                "datas": base64.b64encode(original_content),
            }
        )

        attachment._scan_for_malware()

        self.assertTrue(attachment.is_quarantined)
        self.assertTrue(attachment.quarantine_hash)
        self.assertTrue(attachment.quarantine_date)
        self.assertEqual(attachment.original_file_size, len(original_content))

        # Verify hash is correct
        import hashlib

        expected_hash = hashlib.sha256(original_content).hexdigest()
        self.assertEqual(attachment.quarantine_hash, expected_hash)

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_quarantine_clears_original_datas(self, mock_pyclamd):
        """Test that quarantine clears the original file data."""
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Test-Virus")}
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        attachment = self.attachment_model.create(
            {
                "name": "virus.exe",
                "type": "binary",
                "datas": base64.b64encode(b"infected content"),
            }
        )

        attachment._scan_for_malware()

        # Original datas should be cleared
        self.assertFalse(attachment.datas)

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_restore_quarantined_admin_only(self, mock_pyclamd):
        """Test that only AV admins can restore quarantined files."""
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Test-Virus")}
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        attachment = self.attachment_model.create(
            {
                "name": "virus.exe",
                "type": "binary",
                "datas": base64.b64encode(b"infected content"),
            }
        )

        attachment._scan_for_malware()

        # Regular user should not be able to restore
        with self.assertRaises(AccessError):
            attachment.with_user(self.regular_user).action_restore_quarantined()

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_permanently_delete_quarantined(self, mock_pyclamd):
        """Test permanently deleting a quarantined file."""
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Test-Virus")}
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        attachment = self.attachment_model.create(
            {
                "name": "virus.exe",
                "type": "binary",
                "datas": base64.b64encode(b"infected content"),
            }
        )

        attachment._scan_for_malware()
        attachment_id = attachment.id

        # Delete as admin
        attachment.with_user(self.av_admin_user).action_permanently_delete_quarantined()

        # Attachment should no longer exist
        self.assertFalse(self.attachment_model.browse(attachment_id).exists())

    def test_action_rescan_quarantined_blocked(self):
        """Test that rescanning a quarantined file is blocked."""
        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "type": "binary",
                "datas": base64.b64encode(b"test content"),
            }
        )
        # Simulate quarantined state
        attachment.with_context(skip_av_scan_queue=True).write(
            {
                "is_quarantined": True,
                "scan_status": "infected",
            }
        )

        with self.assertRaises(UserError):
            attachment.action_rescan()

    def test_cron_purge_old_quarantined(self):
        """Test scheduled purge of old quarantined files."""
        from datetime import timedelta

        attachment = self.attachment_model.create(
            {
                "name": "old_virus.exe",
                "type": "binary",
                "datas": base64.b64encode(b"test"),
            }
        )

        # Simulate old quarantine
        old_date = fields.Datetime.now() - timedelta(days=100)
        attachment.with_context(skip_av_scan_queue=True).write(
            {
                "is_quarantined": True,
                "quarantine_date": old_date,
                "quarantine_data": base64.b64encode(b"encrypted_data"),
                "scan_status": "infected",
            }
        )

        # Set retention to 90 days
        self.env["ir.config_parameter"].sudo().set_param("spp_attachment_av_scan.quarantine_retention_days", "90")

        # Run purge
        self.attachment_model._cron_purge_old_quarantined_files()

        # Quarantine data should be cleared
        attachment.invalidate_recordset()
        self.assertFalse(attachment.quarantine_data)

    def test_calculate_file_hash(self):
        """Test file hash calculation."""
        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "type": "binary",
                "datas": base64.b64encode(b"test content"),
            }
        )

        test_data = b"test content for hashing"
        calculated_hash = attachment._calculate_file_hash(test_data)

        import hashlib

        expected_hash = hashlib.sha256(test_data).hexdigest()
        self.assertEqual(calculated_hash, expected_hash)

    def test_restore_not_quarantined_error(self):
        """Test that restoring non-quarantined file raises error."""
        attachment = self.attachment_model.create(
            {
                "name": "clean.txt",
                "type": "binary",
                "datas": base64.b64encode(b"clean content"),
            }
        )
        attachment.with_context(skip_av_scan_queue=True).write(
            {
                "scan_status": "clean",
                "is_quarantined": False,
            }
        )

        with self.assertRaises(UserError):
            attachment.with_user(self.av_admin_user).action_restore_quarantined()

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_notification_sent_on_infection(self, mock_pyclamd):
        """Test that security admins are notified when malware is detected."""
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Test-Malware")}
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        # Ensure we have the AV admin group with users
        av_admin_group = self.env.ref("spp_attachment_av_scan.group_av_admin")
        self.assertTrue(av_admin_group.user_ids, "AV admin group should have users")

        attachment = self.attachment_model.create(
            {
                "name": "malware.exe",
                "type": "binary",
                "datas": base64.b64encode(b"malicious content"),
            }
        )

        # Count messages before scan
        messages_before = self.env["mail.message"].search_count(
            [("model", "=", "ir.attachment"), ("res_id", "=", attachment.id)]
        )

        attachment._scan_for_malware()

        # Count messages after scan
        messages_after = self.env["mail.message"].search_count(
            [("model", "=", "ir.attachment"), ("res_id", "=", attachment.id)]
        )

        # A notification message should have been created
        self.assertGreater(messages_after, messages_before)

    def test_forensic_download_marked(self):
        """Test that forensic downloads are marked with is_forensic_download flag."""
        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "type": "binary",
                "datas": base64.b64encode(b"test"),
            }
        )

        # Simulate quarantine state with encrypted data
        # First create an encryption provider with a key
        encryption_provider = self.env["spp.encryption.provider"].sudo().search([("type", "=", "jwcrypto")], limit=1)

        if not encryption_provider:
            _logger.info("Skipping test_forensic_download_marked: no encryption provider available")
            return

        try:
            original_content = b"quarantined content"
            encrypted_data = encryption_provider.encrypt_data(original_content)
            file_hash = attachment._calculate_file_hash(original_content)

            attachment.with_context(skip_av_scan_queue=True).write(
                {
                    "is_quarantined": True,
                    "scan_status": "infected",
                    "quarantine_data": base64.b64encode(encrypted_data),
                    "quarantine_hash": file_hash,
                    "original_file_size": len(original_content),
                    "datas": False,
                }
            )

            # Download for analysis as admin
            attachment.with_user(self.av_admin_user).action_download_quarantined_for_analysis()

            # Find the created download attachment
            download_attachment = self.attachment_model.search([("name", "=", f"QUARANTINED_{attachment.name}")])

            self.assertTrue(download_attachment.exists())
            self.assertTrue(download_attachment.is_forensic_download)
            self.assertEqual(download_attachment.scan_status, "skipped")
        except ValueError as e:
            if "No encryption key" in str(e):
                _logger.info("Skipping test_forensic_download_marked: %s", e)
            else:
                raise

    def test_cron_cleanup_forensic_downloads(self):
        """Test scheduled cleanup of old forensic download attachments."""
        from datetime import timedelta

        # Create a forensic download attachment
        attachment = self.attachment_model.create(
            {
                "name": "QUARANTINED_old_file.exe",
                "type": "binary",
                "datas": base64.b64encode(b"test"),
                "is_forensic_download": True,
            }
        )

        # Simulate old create_date (25 hours ago)
        old_date = fields.Datetime.now() - timedelta(hours=25)
        self.env.cr.execute(
            "UPDATE ir_attachment SET create_date = %s WHERE id = %s",
            (old_date, attachment.id),
        )
        attachment.invalidate_recordset()

        # Set retention to 24 hours
        self.env["ir.config_parameter"].sudo().set_param(
            "spp_attachment_av_scan.forensic_download_retention_hours", "24"
        )

        attachment_id = attachment.id

        # Run cleanup
        self.attachment_model._cron_cleanup_forensic_downloads()

        # Attachment should be deleted
        self.assertFalse(self.attachment_model.browse(attachment_id).exists())

    def test_cron_cleanup_keeps_recent_forensic_downloads(self):
        """Test that recent forensic downloads are not cleaned up."""
        # Create a recent forensic download attachment
        attachment = self.attachment_model.create(
            {
                "name": "QUARANTINED_recent_file.exe",
                "type": "binary",
                "datas": base64.b64encode(b"test"),
                "is_forensic_download": True,
            }
        )

        # Set retention to 24 hours
        self.env["ir.config_parameter"].sudo().set_param(
            "spp_attachment_av_scan.forensic_download_retention_hours", "24"
        )

        attachment_id = attachment.id

        # Run cleanup
        self.attachment_model._cron_cleanup_forensic_downloads()

        # Attachment should still exist (it's recent)
        self.assertTrue(self.attachment_model.browse(attachment_id).exists())

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_large_file_skipped_during_scan(self, mock_pyclamd):
        """Test that files exceeding max_file_size_mb are skipped."""
        # Configure scanner with 1 MB limit
        self.scanner_backend.write({"max_file_size_mb": 1})

        # Create attachment with 2 MB of data
        large_content = b"x" * (2 * 1024 * 1024)
        attachment = self.attachment_model.create(
            {
                "name": "large_file.bin",
                "type": "binary",
                "datas": base64.b64encode(large_content),
            }
        )

        # Run scan
        attachment._scan_for_malware()

        # Should be skipped due to size
        self.assertEqual(attachment.scan_status, "skipped")
        self.assertIn("exceeds maximum", attachment.scan_result)

    def test_size_validation_on_restore(self):
        """Test that size validation catches corrupted restored files."""
        attachment = self.attachment_model.create(
            {
                "name": "test.txt",
                "type": "binary",
                "datas": base64.b64encode(b"test"),
            }
        )

        encryption_provider = self.env["spp.encryption.provider"].sudo().search([("type", "=", "jwcrypto")], limit=1)

        if not encryption_provider:
            _logger.info("Skipping test_size_validation_on_restore: no encryption provider available")
            return

        try:
            original_content = b"original content here"
            # Encrypt different data than what original_file_size indicates
            different_content = b"different"
            encrypted_data = encryption_provider.encrypt_data(different_content)
            file_hash = attachment._calculate_file_hash(different_content)

            attachment.with_context(skip_av_scan_queue=True).write(
                {
                    "is_quarantined": True,
                    "scan_status": "infected",
                    "quarantine_data": base64.b64encode(encrypted_data),
                    "quarantine_hash": file_hash,
                    # Set wrong size to simulate corruption
                    "original_file_size": len(original_content),
                    "datas": False,
                }
            )

            # Restore should fail due to size mismatch
            with self.assertRaises(UserError) as context:
                attachment.with_user(self.av_admin_user).action_restore_quarantined()

            self.assertIn("size mismatch", str(context.exception).lower())
        except ValueError as e:
            if "No encryption key" in str(e):
                _logger.info("Skipping test_size_validation_on_restore: %s", e)
            else:
                raise

    @patch("odoo.addons.spp_attachment_av_scan.models.av_scanner_backend.pyclamd")
    def test_full_restore_flow_with_encryption(self, mock_pyclamd):
        """Test complete quarantine and restore flow with encryption."""
        mock_scanner = MagicMock()
        mock_scanner.ping.return_value = True
        mock_scanner.scan_stream.return_value = {"stream": ("FOUND", "Test-Virus")}
        mock_pyclamd.ClamdUnixSocket.return_value = mock_scanner

        original_content = b"this was falsely detected as malware"
        attachment = self.attachment_model.create(
            {
                "name": "false_positive.doc",
                "type": "binary",
                "datas": base64.b64encode(original_content),
            }
        )

        # Scan and quarantine
        attachment._scan_for_malware()

        self.assertTrue(attachment.is_quarantined)
        self.assertEqual(attachment.scan_status, "infected")
        self.assertFalse(attachment.datas)  # Original data cleared
        self.assertTrue(attachment.quarantine_hash)
        self.assertEqual(attachment.original_file_size, len(original_content))

        # Check if encryption provider exists for restore test
        encryption_provider = self.env["spp.encryption.provider"].sudo().search([("type", "=", "jwcrypto")], limit=1)

        if encryption_provider and attachment.quarantine_data:
            # Restore as admin
            attachment.with_user(self.av_admin_user).action_restore_quarantined()

            # Verify restoration
            self.assertFalse(attachment.is_quarantined)
            self.assertEqual(attachment.scan_status, "clean")
            self.assertTrue(attachment.datas)

            # Verify restored content matches original
            restored_content = base64.b64decode(attachment.datas)
            self.assertEqual(restored_content, original_content)
