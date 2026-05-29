# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI Receipt API endpoint."""

from datetime import UTC, datetime

from odoo import fields
from odoo.tests import tagged

from .common import DCIServerCommon


@tagged("post_install", "-at_install")
class TestDCIReceiptSchemas(DCIServerCommon):
    """Test Receipt API schemas."""

    def test_receipt_request_schema_valid(self):
        """Test ReceiptRequest schema accepts valid data."""
        from odoo.addons.spp_dci.schemas import ReceiptRequest, ReceiptType

        receipt_data = {
            "transaction_id": "txn-receipt-001",
            "receipt_information": {
                "receipt_type": "notification",
                "notification_id": "NOTIF-ABC123",
                "subscription_code": "SUB-XYZ789",
                "received_at": datetime.now(UTC).isoformat(),
            },
        }

        receipt = ReceiptRequest.model_validate(receipt_data)
        self.assertEqual(receipt.transaction_id, "txn-receipt-001")
        self.assertEqual(receipt.receipt_information.receipt_type, ReceiptType.NOTIFICATION)
        self.assertEqual(receipt.receipt_information.notification_id, "NOTIF-ABC123")

    def test_receipt_response_schema(self):
        """Test ReceiptResponse schema."""
        from odoo.addons.spp_dci.schemas import ReceiptResponse, ReceiptResponseItem

        response = ReceiptResponse(
            transaction_id="txn-receipt-001",
            correlation_id="corr-001",
            receipt_response=[
                ReceiptResponseItem(
                    reference_id="ref-001",
                    timestamp=datetime.now(UTC),
                    status="succ",
                )
            ],
        )

        self.assertEqual(response.transaction_id, "txn-receipt-001")
        self.assertEqual(len(response.receipt_response), 1)
        self.assertEqual(response.receipt_response[0].status, "succ")

    def test_receipt_type_enum(self):
        """Test ReceiptType enum values."""
        from odoo.addons.spp_dci.schemas import ReceiptType

        # Verify expected values exist
        self.assertEqual(ReceiptType.REGISTER.value, "register")
        self.assertEqual(ReceiptType.PAYMENT.value, "payment")
        self.assertEqual(ReceiptType.DEREGISTER.value, "deregister")
        self.assertEqual(ReceiptType.NOTIFICATION.value, "notification")


@tagged("post_install", "-at_install")
class TestDCINotificationLogReceipt(DCIServerCommon):
    """Test notification log receipt tracking fields."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Subscription = cls.env["spp.dci.subscription"]
        cls.NotificationLog = cls.env["spp.dci.notification.log"]
        cls.test_sender = cls.create_test_sender()

    def test_notification_log_has_receipt_fields(self):
        """Test that notification log has receipt tracking fields."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        log = self.NotificationLog.create(
            {
                "subscription_id": sub.id,
                "event_type": "registration",
                "record_count": 1,
                "status": "sent",
            }
        )

        # Verify notification_id is auto-generated
        self.assertTrue(log.notification_id)
        self.assertTrue(log.notification_id.startswith("NOTIF-"))

        # Odoo returns False (not None) for unset Datetime / Char fields.
        self.assertFalse(log.receipt_received)
        self.assertFalse(log.receipt_timestamp)
        self.assertFalse(log.receipt_transaction_id)

    def test_notification_log_receipt_update(self):
        """Test updating notification log with receipt information."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        log = self.NotificationLog.create(
            {
                "subscription_id": sub.id,
                "event_type": "registration",
                "record_count": 1,
                "status": "sent",
            }
        )

        # Simulate receiving a receipt. Odoo Datetime fields reject
        # tz-aware values, so use the framework helper which returns a
        # naive UTC datetime.
        log.write(
            {
                "receipt_received": True,
                "receipt_timestamp": fields.Datetime.now(),
                "receipt_transaction_id": "txn-receipt-001",
                "status": "received",
            }
        )

        self.assertTrue(log.receipt_received)
        self.assertEqual(log.receipt_transaction_id, "txn-receipt-001")
        self.assertEqual(log.status, "received")

    def test_notification_id_unique(self):
        """Test that notification_id is unique."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        # Create first log
        log1 = self.NotificationLog.create(
            {
                "subscription_id": sub.id,
                "event_type": "registration",
                "record_count": 1,
                "status": "sent",
            }
        )

        # Create second log
        log2 = self.NotificationLog.create(
            {
                "subscription_id": sub.id,
                "event_type": "registration",
                "record_count": 2,
                "status": "sent",
            }
        )

        # Verify different notification IDs
        self.assertNotEqual(log1.notification_id, log2.notification_id)


@tagged("post_install", "-at_install")
class TestDCIBuildNotificationWithId(DCIServerCommon):
    """Test notification building includes notification_id."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Subscription = cls.env["spp.dci.subscription"]
        cls.test_sender = cls.create_test_sender()

    def test_build_notification_without_id(self):
        """Test _build_notification works without notification_id (backward compat)."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        notification = sub._build_notification("registration", [{"id": "1"}])

        self.assertIn("header", notification)
        self.assertIn("message", notification)
        self.assertNotIn("notification_id", notification["header"])
        self.assertNotIn("notification_id", notification["message"])

    def test_build_notification_with_id(self):
        """Test _build_notification includes notification_id when provided."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        notification = sub._build_notification("registration", [{"id": "1"}], notification_id="NOTIF-TEST123")

        self.assertEqual(notification["header"]["notification_id"], "NOTIF-TEST123")
        self.assertEqual(notification["message"]["notification_id"], "NOTIF-TEST123")


@tagged("post_install", "-at_install")
class TestDCIReceiptRouter(DCIServerCommon):
    """Test Receipt API router functions."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Subscription = cls.env["spp.dci.subscription"]
        cls.NotificationLog = cls.env["spp.dci.notification.log"]
        cls.test_sender = cls.create_test_sender()

    def test_receipt_find_by_notification_id(self):
        """Test finding notification log by notification_id."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        log = self.NotificationLog.create(
            {
                "subscription_id": sub.id,
                "event_type": "registration",
                "record_count": 1,
                "status": "sent",
            }
        )

        # Find by notification_id
        found = self.NotificationLog.search(
            [("notification_id", "=", log.notification_id)],
            limit=1,
        )

        self.assertEqual(found.id, log.id)

    def test_receipt_find_by_subscription_code(self):
        """Test finding unacknowledged notification by subscription code."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        # Create an unacknowledged notification
        log = self.NotificationLog.create(
            {
                "subscription_id": sub.id,
                "event_type": "registration",
                "record_count": 1,
                "status": "sent",
                "receipt_received": False,
            }
        )

        # Find by subscription
        found = self.NotificationLog.search(
            [
                ("subscription_id", "=", sub.id),
                ("receipt_received", "=", False),
                ("status", "=", "sent"),
            ],
            order="sent_at desc",
            limit=1,
        )

        self.assertEqual(found.id, log.id)

    def test_receipt_update_marks_received(self):
        """Test that receipt processing marks notification as received."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        log = self.NotificationLog.create(
            {
                "subscription_id": sub.id,
                "event_type": "registration",
                "record_count": 1,
                "status": "sent",
            }
        )

        # Simulate receipt processing
        log.write(
            {
                "receipt_received": True,
                "receipt_timestamp": fields.Datetime.now(),
                "receipt_transaction_id": "txn-001",
                "status": "received",
            }
        )

        # Verify the update
        log.invalidate_recordset()
        self.assertTrue(log.receipt_received)
        self.assertEqual(log.status, "received")


@tagged("post_install", "-at_install")
class TestDCIReceiptStatusSelection(DCIServerCommon):
    """Test notification log status selection includes 'received'."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.NotificationLog = cls.env["spp.dci.notification.log"]

    def test_status_selection_has_received(self):
        """Test that status selection includes 'received' option."""
        status_field = self.NotificationLog._fields["status"]
        selection = status_field.selection

        # Find 'received' in selection
        received_option = [s for s in selection if s[0] == "received"]
        self.assertEqual(len(received_option), 1)
        self.assertEqual(received_option[0], ("received", "Receipt Received"))
