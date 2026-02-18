# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI Transaction model."""

import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import DCIServerCommon


@tagged("post_install", "-at_install")
class TestDCITransaction(DCIServerCommon):
    """Test DCI Transaction model functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Create models
        cls.Transaction = cls.env["spp.dci.transaction"]

        # Create a test sender
        cls.test_sender = cls.create_test_sender()

        # Sample request payload
        cls.sample_request = {
            "signature": "test-sig",
            "header": {
                "version": "1.0.0",
                "message_id": "msg-001",
                "action": "search",
                "sender_id": cls.test_sender_id,
            },
            "message": {
                "transaction_id": "txn-001",
                "search_request": [{"reference_id": "ref-001"}],
            },
        }

    def test_create_transaction(self):
        """Test basic transaction creation."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "test-txn-001",
                "message_id": "msg-001",
                "action": "search",
                "reg_type": "SOCIAL_REGISTRY",
                "sender_id": self.test_sender.id,
                "sender_uri": self.test_sender_id,
                "request_payload": json.dumps(self.sample_request),
                "state": "received",
            }
        )

        self.assertEqual(transaction.transaction_id, "test-txn-001")
        self.assertEqual(transaction.action, "search")
        self.assertEqual(transaction.state, "received")
        self.assertTrue(transaction.correlation_id)  # Auto-generated

    def test_transaction_uniqueness_per_sender(self):
        """Test that transaction_id must be unique per sender."""
        self.Transaction.create(
            {
                "transaction_id": "unique-txn-001",
                "message_id": "msg-001",
                "action": "search",
                "sender_uri": self.test_sender_id,
            }
        )

        # Same transaction_id, same sender - should fail
        with self.assertRaises(ValidationError):
            self.Transaction.create(
                {
                    "transaction_id": "unique-txn-001",
                    "message_id": "msg-002",
                    "action": "search",
                    "sender_uri": self.test_sender_id,
                }
            )

    def test_transaction_same_id_different_sender_allowed(self):
        """Test that same transaction_id is allowed for different senders."""
        txn1 = self.Transaction.create(
            {
                "transaction_id": "shared-txn-001",
                "message_id": "msg-001",
                "action": "search",
                "sender_uri": "sender-a.gov",
            }
        )

        # Same transaction_id, different sender - should succeed
        txn2 = self.Transaction.create(
            {
                "transaction_id": "shared-txn-001",
                "message_id": "msg-002",
                "action": "search",
                "sender_uri": "sender-b.gov",
            }
        )

        self.assertNotEqual(txn1.id, txn2.id)

    def test_dci_status_mapping_received(self):
        """Test DCI status mapping for received state."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "status-test-001",
                "message_id": "msg-001",
                "action": "search",
                "state": "received",
            }
        )
        self.assertEqual(transaction.dci_status, "rcvd")

    def test_dci_status_mapping_pending(self):
        """Test DCI status mapping for pending state."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "status-test-002",
                "message_id": "msg-001",
                "action": "search",
                "state": "pending",
            }
        )
        self.assertEqual(transaction.dci_status, "pdng")

    def test_dci_status_mapping_processing(self):
        """Test DCI status mapping for processing state."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "status-test-003",
                "message_id": "msg-001",
                "action": "search",
                "state": "processing",
            }
        )
        self.assertEqual(transaction.dci_status, "pdng")

    def test_dci_status_mapping_success(self):
        """Test DCI status mapping for success state."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "status-test-004",
                "message_id": "msg-001",
                "action": "search",
                "state": "success",
            }
        )
        self.assertEqual(transaction.dci_status, "succ")

    def test_dci_status_mapping_rejected(self):
        """Test DCI status mapping for rejected state."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "status-test-005",
                "message_id": "msg-001",
                "action": "search",
                "state": "rejected",
            }
        )
        self.assertEqual(transaction.dci_status, "rjct")

    def test_dci_status_mapping_callback_sent(self):
        """Test DCI status mapping for callback_sent state."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "status-test-006",
                "message_id": "msg-001",
                "action": "search",
                "state": "callback_sent",
            }
        )
        # callback_sent means processing succeeded
        self.assertEqual(transaction.dci_status, "succ")

    def test_dci_status_mapping_callback_failed(self):
        """Test DCI status mapping for callback_failed state."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "status-test-007",
                "message_id": "msg-001",
                "action": "search",
                "state": "callback_failed",
            }
        )
        # callback_failed means processing succeeded, only delivery failed
        self.assertEqual(transaction.dci_status, "succ")

    def test_build_callback_envelope_from_dict(self):
        """Test callback envelope building from dict."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "envelope-test-001",
                "message_id": "msg-001",
                "action": "search",
                "sender_uri": self.test_sender_id,
                "state": "success",
            }
        )

        response_data = {"result": "test_data"}
        envelope = transaction._build_callback_envelope_from_dict(response_data)

        self.assertIn("signature", envelope)
        self.assertIn("header", envelope)
        self.assertIn("message", envelope)
        self.assertEqual(envelope["header"]["action"], "on-search")
        self.assertEqual(envelope["header"]["status"], "succ")
        self.assertEqual(envelope["header"]["receiver_id"], self.test_sender_id)
        self.assertEqual(envelope["message"], response_data)

    @patch("odoo.addons.spp_dci_server.models.transaction.validate_callback_url")
    @patch("requests.post")
    def test_send_callback_success(self, mock_post, mock_validate):
        """Test successful callback delivery."""
        mock_validate.return_value = "https://callback.example.com/dci"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        transaction = self.Transaction.create(
            {
                "transaction_id": "callback-test-001",
                "message_id": "msg-001",
                "action": "search",
                "sender_uri": self.test_sender_id,
                "callback_uri": "https://callback.example.com/dci",
                "state": "success",
                "response_payload": json.dumps({"result": "ok"}),
            }
        )

        # Create a mock response object that matches Pydantic's model_dump signature
        class MockResponse:
            def model_dump(self, mode="python", by_alias=False, exclude_none=False):
                return {"result": "ok"}

        transaction._send_callback(MockResponse())

        self.assertEqual(transaction.state, "callback_sent")
        self.assertTrue(transaction.callback_sent_at)
        mock_post.assert_called_once()

    @patch("odoo.addons.spp_dci_server.models.transaction.validate_callback_url")
    def test_send_callback_ssrf_blocked(self, mock_validate):
        """Test that SSRF attacks via callback URLs are blocked."""
        mock_validate.side_effect = ValidationError("Blocked IP")

        transaction = self.Transaction.create(
            {
                "transaction_id": "ssrf-test-001",
                "message_id": "msg-001",
                "action": "search",
                "callback_uri": "https://169.254.169.254/metadata",
                "state": "success",
            }
        )

        transaction._send_callback(MagicMock())

        self.assertEqual(transaction.state, "callback_failed")
        # SPDCI-compliant error code
        self.assertEqual(transaction.error_code, "rjct.reference_id.invalid")

    @patch("odoo.addons.spp_dci_server.models.transaction.validate_callback_url")
    @patch("requests.post")
    def test_send_callback_retry_on_failure(self, mock_post, mock_validate):
        """Test callback retry on network failure."""
        import requests

        mock_validate.return_value = "https://callback.example.com/dci"
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        transaction = self.Transaction.create(
            {
                "transaction_id": "retry-test-001",
                "message_id": "msg-001",
                "action": "search",
                "sender_uri": self.test_sender_id,
                "callback_uri": "https://callback.example.com/dci",
                "state": "success",
                "response_payload": json.dumps({"result": "ok"}),
                "max_retries": 3,
            }
        )

        # Create a mock response object that matches Pydantic's model_dump signature
        class MockResponse:
            def model_dump(self, mode="python", by_alias=False, exclude_none=False):
                return {"result": "ok"}

        # Mock with_delay at class level to avoid job_worker dependency in tests
        with patch.object(type(transaction), "with_delay") as mock_delay:
            mock_delay.return_value._retry_callback = MagicMock()
            transaction._send_callback(MockResponse())

        self.assertEqual(transaction.retry_count, 1)
        # State should not be callback_failed yet (retries remaining)
        self.assertNotEqual(transaction.state, "callback_failed")

    @patch("odoo.addons.spp_dci_server.models.transaction.validate_callback_url")
    @patch("requests.post")
    def test_send_callback_max_retries_exceeded(self, mock_post, mock_validate):
        """Test callback permanently fails after max retries."""
        import requests

        mock_validate.return_value = "https://callback.example.com/dci"
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        transaction = self.Transaction.create(
            {
                "transaction_id": "max-retry-test-001",
                "message_id": "msg-001",
                "action": "search",
                "sender_uri": self.test_sender_id,
                "callback_uri": "https://callback.example.com/dci",
                "state": "success",
                "response_payload": json.dumps({"result": "ok"}),
                "retry_count": 3,  # Already at max
                "max_retries": 3,
            }
        )

        # Create a mock response object that matches Pydantic's model_dump signature
        class MockResponse:
            def model_dump(self, mode="python", by_alias=False, exclude_none=False):
                return {"result": "ok"}

        transaction._send_callback(MockResponse())

        self.assertEqual(transaction.state, "callback_failed")

    def test_action_retry_callback_available_for_failed(self):
        """Test manual retry action is available for failed callbacks."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "manual-retry-001",
                "message_id": "msg-001",
                "action": "search",
                "state": "callback_failed",
                "response_payload": json.dumps({"result": "ok"}),
            }
        )

        # Should not raise - patch at class level to avoid read-only attribute issue
        with patch.object(type(transaction), "_retry_callback") as mock_retry:
            transaction.action_retry_callback()
            mock_retry.assert_called_once()

    def test_correlation_id_auto_generated(self):
        """Test that correlation_id is auto-generated on create."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "corr-test-001",
                "message_id": "msg-001",
                "action": "search",
            }
        )

        self.assertTrue(transaction.correlation_id)
        # Should be a valid UUID format
        import uuid

        uuid.UUID(transaction.correlation_id)  # Raises if invalid


@tagged("post_install", "-at_install")
class TestDCITransactionJobState(DCIServerCommon):
    """Test transaction job state computation."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Transaction = cls.env["spp.dci.transaction"]

    def test_job_state_na_without_uuid(self):
        """Test job_state is 'n/a' when no job_uuid."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "job-state-001",
                "message_id": "msg-001",
                "action": "search",
            }
        )

        self.assertEqual(transaction.job_state, "n/a")

    def test_job_state_unknown_with_invalid_uuid(self):
        """Test job_state is 'unknown' when job_uuid doesn't match a job."""
        transaction = self.Transaction.create(
            {
                "transaction_id": "job-state-002",
                "message_id": "msg-001",
                "action": "search",
                "job_uuid": "non-existent-uuid",
            }
        )

        self.assertEqual(transaction.job_state, "unknown")
