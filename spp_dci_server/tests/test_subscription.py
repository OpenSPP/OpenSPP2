# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI Subscription model."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import DCIServerCommon


@tagged("post_install", "-at_install")
class TestDCISubscription(DCIServerCommon):
    """Test DCI Subscription model functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Create models
        cls.Subscription = cls.env["spp.dci.subscription"]

        # Create a test sender
        cls.test_sender = cls.create_test_sender()

    def test_create_subscription_basic(self):
        """Test basic subscription creation."""
        subscription = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        self.assertTrue(subscription.subscription_code)
        self.assertTrue(subscription.subscription_code.startswith("SUB-"))
        self.assertEqual(subscription.state, "pending")
        self.assertTrue(subscription.active)

    def test_subscription_code_unique(self):
        """Test that subscription codes are generated uniquely."""
        # Create multiple subscriptions and verify each gets a unique code
        sub1 = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify1",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        sub2 = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify2",
                "event_type": "update",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        # Verify each subscription got a unique code
        self.assertNotEqual(
            sub1.subscription_code,
            sub2.subscription_code,
            "Each subscription should have a unique code",
        )

        # Verify codes follow expected format
        self.assertTrue(sub1.subscription_code.startswith("SUB-"))
        self.assertTrue(sub2.subscription_code.startswith("SUB-"))

    @patch("odoo.addons.spp_dci_server.utils.url_validator.validate_callback_url")
    def test_callback_url_validated_on_create(self, mock_validate):
        """Test that callback URL is validated on creation."""
        mock_validate.side_effect = ValidationError("Blocked URL")

        with self.assertRaises(ValidationError):
            self.Subscription.create(
                {
                    "sender_id": self.test_sender.id,
                    "callback_uri": "https://localhost/notify",
                    "event_type": "registration",
                    "reg_type": "SOCIAL_REGISTRY",
                }
            )

    def test_subscription_limit_enforced(self):
        """Test that subscription limits are enforced."""
        # Set a low limit for testing
        self.env["ir.config_parameter"].sudo().set_param("dci.max_subscriptions_per_sender", "3")

        # Create subscriptions up to limit
        for i in range(3):
            self.Subscription.create(
                {
                    "sender_id": self.test_sender.id,
                    "callback_uri": f"https://callback.example.com/notify{i}",
                    "event_type": "registration",
                    "reg_type": "SOCIAL_REGISTRY",
                }
            )

        # Next one should fail
        with self.assertRaises(ValidationError) as ctx:
            self.Subscription.create(
                {
                    "sender_id": self.test_sender.id,
                    "callback_uri": "https://callback.example.com/notify_extra",
                    "event_type": "update",
                    "reg_type": "SOCIAL_REGISTRY",
                }
            )
        self.assertIn("limit", str(ctx.exception).lower())

        # Clean up
        self.env["ir.config_parameter"].sudo().set_param("dci.max_subscriptions_per_sender", "100")

    def test_subscription_limit_excludes_cancelled(self):
        """Test that cancelled subscriptions don't count toward limit."""
        self.env["ir.config_parameter"].sudo().set_param("dci.max_subscriptions_per_sender", "2")

        # Create and cancel first subscription
        sub1 = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify1",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )
        sub1.action_cancel()

        # Should be able to create 2 more (cancelled doesn't count)
        for i in range(2):
            self.Subscription.create(
                {
                    "sender_id": self.test_sender.id,
                    "callback_uri": f"https://callback.example.com/notify{i + 2}",
                    "event_type": "registration",
                    "reg_type": "SOCIAL_REGISTRY",
                }
            )

        # Clean up
        self.env["ir.config_parameter"].sudo().set_param("dci.max_subscriptions_per_sender", "100")

    def test_action_confirm(self):
        """Test subscription confirmation action."""
        subscription = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "pending",
            }
        )

        subscription.action_confirm()

        self.assertEqual(subscription.state, "active")

    def test_action_cancel(self):
        """Test subscription cancellation action."""
        subscription = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )
        subscription.action_confirm()

        subscription.action_cancel()

        self.assertEqual(subscription.state, "cancelled")
        self.assertFalse(subscription.active)

    def test_action_reactivate(self):
        """Test subscription reactivation action."""
        subscription = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )
        subscription.action_cancel()

        subscription.action_reactivate()

        self.assertEqual(subscription.state, "active")
        self.assertTrue(subscription.active)
        self.assertEqual(subscription.failed_count, 0)

    def test_expired_subscription_cleanup(self):
        """Test that expired subscriptions are deactivated by cron."""
        # Create an expired subscription
        expired_sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "active",
                "expires": fields.Datetime.now() - timedelta(hours=1),
            }
        )

        # Run cron job
        self.Subscription.check_expired_subscriptions()

        # Subscription should be expired
        expired_sub.invalidate_recordset()
        self.assertEqual(expired_sub.state, "expired")
        self.assertFalse(expired_sub.active)

    def test_non_expired_subscription_not_affected(self):
        """Test that non-expired subscriptions are not affected by cron."""
        # Create a valid subscription with future expiry
        valid_sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "active",
                "expires": fields.Datetime.now() + timedelta(days=7),
            }
        )

        # Run cron job
        self.Subscription.check_expired_subscriptions()

        # Subscription should still be active
        valid_sub.invalidate_recordset()
        self.assertEqual(valid_sub.state, "active")
        self.assertTrue(valid_sub.active)


@tagged("post_install", "-at_install")
class TestDCISubscriptionNotifications(DCIServerCommon):
    """Test subscription notification functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Subscription = cls.env["spp.dci.subscription"]
        cls.test_sender = cls.create_test_sender()

    def test_notify_event_finds_matching_subscriptions(self):
        """Test that notify_event finds subscriptions by event type."""
        # Create active subscription
        self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "active",
            }
        )

        # notify_event now scopes per subscription: it queues a job only when the
        # subscription's sender is eligible AND records can be built. The generic
        # layer builds no records (registry modules do), so stub those hooks to
        # verify the matching/queueing orchestration.
        with (
            patch.object(type(self.Subscription), "with_delay") as mock_delay,
            patch.object(type(self.Subscription), "_eligible_partner_ids", return_value=[1]),
            patch.object(type(self.Subscription), "_build_notification_records", return_value=[{"id": "rec-001"}]),
        ):
            mock_delay.return_value = MagicMock()

            # Trigger notification
            self.Subscription.notify_event(
                event_type="registration",
                partner_ids=[1],
                reg_type="SOCIAL_REGISTRY",
            )

            mock_delay.assert_called()

    def test_notify_event_ignores_inactive(self):
        """Test that inactive subscriptions don't receive notifications."""
        # Create inactive subscription
        self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "active",
                "active": False,
            }
        )

        # Patch with_delay at the model class level
        with patch.object(type(self.Subscription), "with_delay") as mock_delay:
            # Trigger notification
            self.Subscription.notify_event(
                event_type="registration",
                partner_ids=[1],
                reg_type="SOCIAL_REGISTRY",
            )

            # Should not have been called for inactive subscription
            mock_delay.assert_not_called()

    def test_build_notification_structure(self):
        """Test notification envelope structure."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "active",
            }
        )

        records = [{"id": "rec-001", "name": "Test Record"}]
        notification = sub._build_notification("registration", records)

        # Check structure
        self.assertIn("signature", notification)
        self.assertIn("header", notification)
        self.assertIn("message", notification)

        # Check header
        header = notification["header"]
        self.assertEqual(header["action"], "notify")
        self.assertEqual(header["version"], "1.0.0")
        self.assertEqual(header["total_count"], 1)

        # Check message
        message = notification["message"]
        self.assertEqual(message["subscription_code"], sub.subscription_code)
        self.assertEqual(len(message["notify_event"]), 1)
        self.assertEqual(message["notify_event"][0]["event_type"], "REGISTRATION")
        self.assertEqual(message["notify_event"][0]["reg_type"], "SOCIAL_REGISTRY")

    @patch("odoo.addons.spp_dci_server.models.subscription.validate_callback_url")
    @patch("requests.post")
    def test_send_notification_success(self, mock_post, mock_validate):
        """Test successful notification delivery."""
        mock_validate.return_value = "https://callback.example.com/notify"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "active",
            }
        )

        sub._send_notification("registration", [{"id": "rec-001"}])

        self.assertTrue(sub.last_notification)
        mock_post.assert_called_once()

    def test_send_notification_ssrf_blocked(self):
        """Test that SSRF attacks via notification URLs are blocked."""
        # Create subscription with valid URL first (bypassing validation for test)
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "active",
            }
        )

        # Patch validation to block SSRF during _send_notification
        with patch("odoo.addons.spp_dci_server.models.subscription.validate_callback_url") as mock_validate:
            mock_validate.side_effect = ValidationError("Blocked IP")

            sub._send_notification("registration", [{"id": "rec-001"}])

            self.assertEqual(sub.failed_count, 1)

    @patch("odoo.addons.spp_dci_server.models.subscription.validate_callback_url")
    @patch("requests.post")
    def test_send_notification_failure_increments_count(self, mock_post, mock_validate):
        """Test that failed notifications increment failed_count."""
        import requests

        mock_validate.return_value = "https://callback.example.com/notify"
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "active",
            }
        )

        sub._send_notification("registration", [{"id": "rec-001"}])

        self.assertEqual(sub.failed_count, 1)

    @patch("odoo.addons.spp_dci_server.models.subscription.validate_callback_url")
    @patch("requests.post")
    def test_subscription_deactivated_after_10_failures(self, mock_post, mock_validate):
        """Test that subscription is deactivated after 10 consecutive failures."""
        import requests

        mock_validate.return_value = "https://callback.example.com/notify"
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "state": "active",
                "failed_count": 9,  # One more failure will hit limit
            }
        )

        sub._send_notification("registration", [{"id": "rec-001"}])

        self.assertEqual(sub.failed_count, 10)
        self.assertEqual(sub.state, "error")
        self.assertFalse(sub.active)


@tagged("post_install", "-at_install")
class TestDCISubscriptionStats(DCIServerCommon):
    """Test subscription statistics computation."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Subscription = cls.env["spp.dci.subscription"]
        cls.NotificationLog = cls.env["spp.dci.notification.log"]
        cls.test_sender = cls.create_test_sender()

    def test_compute_stats_empty(self):
        """Test notification_count is 0 with no logs."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        self.assertEqual(sub.notification_count, 0)

    def test_compute_stats_with_logs(self):
        """Test notification_count reflects actual log count."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )

        # Create some notification logs
        for _i in range(5):
            self.NotificationLog.create(
                {
                    "subscription_id": sub.id,
                    "event_type": "registration",
                    "record_count": 1,
                    "status": "sent",
                }
            )

        # Invalidate cache to force recompute
        sub.invalidate_recordset()

        self.assertEqual(sub.notification_count, 5)

    def test_compute_stats_batch_efficient(self):
        """Test that stats computation is batch efficient (uses read_group)."""
        subs = self.Subscription.browse()

        # Create multiple subscriptions
        for i in range(3):
            sub = self.Subscription.create(
                {
                    "sender_id": self.test_sender.id,
                    "callback_uri": f"https://callback.example.com/notify{i}",
                    "event_type": "registration",
                    "reg_type": "SOCIAL_REGISTRY",
                }
            )
            subs |= sub

            # Add logs for each
            for _j in range(i + 1):
                self.NotificationLog.create(
                    {
                        "subscription_id": sub.id,
                        "event_type": "registration",
                        "record_count": 1,
                        "status": "sent",
                    }
                )

        # Force recompute
        subs.invalidate_recordset()

        # Verify counts - sub0: 1, sub1: 2, sub2: 3
        counts = [s.notification_count for s in subs]
        self.assertEqual(counts, [1, 2, 3])
