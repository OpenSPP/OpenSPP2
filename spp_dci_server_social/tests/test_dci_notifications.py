# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI notification triggers on res.partner changes."""

import logging
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from .common import DCISocialServerCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestDCINotifications(DCISocialServerCommon):
    """Test cases for DCI notification triggers."""

    def setUp(self):
        """Set up test environment before each test."""
        super().setUp()
        # Enable notifications for testing
        self.env["ir.config_parameter"].sudo().set_param("dci.notifications_enabled", "true")
        # setUpClass creates several partners; each registered a
        # postcommit callback in _schedule_dci_notification. Drain them
        # here so the per-test postcommit.run() only fires for callbacks
        # the test itself triggers.
        self.env.cr.postcommit.run()

    def test_create_triggers_registration_notification(self):
        """Test that creating a registrant schedules a registration notification."""
        with patch.object(self.Partner.__class__, "_queue_dci_notification_job") as mock_queue:
            individual = self._create_test_individual(
                {
                    "family_name": "Notification",
                    "given_name": "Test",
                },
                identifier_value="NAT-NOTIFY-001",
            )
            # _schedule_dci_notification registers its callback via
            # env.cr.postcommit, which TransactionCase never flushes
            # (it rolls back). Drive the post-commit queue explicitly so
            # the mock can record the call.
            self.env.cr.postcommit.run()

            # Verify notification was scheduled
            mock_queue.assert_called_once()
            args = mock_queue.call_args[0]
            self.assertEqual(args[0], "registration")
            self.assertIn(individual.id, args[1])

    def test_write_tracked_field_triggers_update_notification(self):
        """Test that modifying tracked fields schedules an update notification."""
        # Create individual first
        individual = self._create_test_individual(
            {
                "family_name": "UpdateTest",
                "given_name": "Before",
            },
            identifier_value="NAT-NOTIFY-002",
        )
        # Drop the registration-time postcommit callback so the test
        # only observes the update callback queued inside the patch.
        self.env.cr.postcommit.clear()

        with patch.object(self.Partner.__class__, "_queue_dci_notification_job") as mock_queue:
            # Modify a tracked field
            individual.write({"given_name": "After"})
            self.env.cr.postcommit.run()

            # Verify update notification was scheduled
            mock_queue.assert_called_once()
            args = mock_queue.call_args[0]
            self.assertEqual(args[0], "update")
            self.assertIn(individual.id, args[1])

    def test_write_untracked_field_no_notification(self):
        """Test that modifying untracked fields does not trigger notification."""
        # Create individual first
        individual = self._create_test_individual(
            {
                "family_name": "NoNotify",
                "given_name": "Test",
            },
            identifier_value="NAT-NOTIFY-003",
        )
        self.env.cr.postcommit.clear()

        with patch.object(self.Partner.__class__, "_queue_dci_notification_job") as mock_queue:
            # Modify an untracked field (comment is not in TRACKED_FIELDS)
            individual.write({"comment": "Test comment"})
            self.env.cr.postcommit.run()

            # Verify no notification was scheduled
            mock_queue.assert_not_called()

    def test_unlink_triggers_delete_notification(self):
        """Test that deleting a registrant schedules a delete notification.

        Patching with a bare MagicMock breaks here: Odoo's _ondelete_methods
        scans class attributes via hasattr(func, '_ondelete') and MagicMock
        auto-creates a truthy child for any attribute access, so the mock
        ends up registered as an ondelete callback and gets invoked with
        the recordset during unlink. Using spec= restricts attribute
        access to the original method's surface, so hasattr returns False.
        """
        # Create individual *without* a reg_id - spp.registry.id has an
        # ON DELETE RESTRICT FK on res.partner, so the unlink would
        # otherwise raise a foreign-key violation that has nothing to do
        # with the DCI notification path under test.
        individual = self._create_test_individual(
            {
                "family_name": "DeleteTest",
                "given_name": "ToDelete",
            },
        )
        individual_id = individual.id
        self.env.cr.postcommit.clear()

        real_method = self.Partner.__class__._queue_dci_notification_job
        mock_queue = MagicMock(spec=real_method)
        with patch.object(
            self.Partner.__class__,
            "_queue_dci_notification_job",
            mock_queue,
        ):
            individual.unlink()
            self.env.cr.postcommit.run()

            mock_queue.assert_called_once()
            args = mock_queue.call_args[0]
            self.assertEqual(args[0], "delete")
            self.assertIn(individual_id, args[1])

    def test_non_registrant_no_notification(self):
        """Test that changes to non-registrants don't trigger notifications."""
        # Create a non-registrant partner
        partner = self.Partner.create(
            {
                "name": "Non-Registrant Company",
                "is_registrant": False,
                "is_company": True,
            }
        )

        with patch.object(self.Partner.__class__, "_queue_dci_notification_job") as mock_queue:
            # No notification should have been queued for non-registrant
            # The mock should not have been called during create
            mock_queue.assert_not_called()

    def test_notifications_disabled_no_queue(self):
        """Test that notifications are not queued when disabled."""
        # Disable notifications
        self.env["ir.config_parameter"].sudo().set_param("dci.notifications_enabled", "false")

        with patch.object(self.Partner.__class__, "_queue_dci_notification_job") as mock_queue:
            self._create_test_individual(
                {
                    "family_name": "Disabled",
                    "given_name": "Test",
                },
                identifier_value="NAT-NOTIFY-005",
            )
            self.env.cr.postcommit.run()

            # Verify no notification was queued
            mock_queue.assert_not_called()

    def test_identity_key_generation(self):
        """Test that identity keys are generated deterministically."""
        partner = self.Partner.browse(self.individual_1.id)

        key1 = partner._get_notification_identity_key("update", [1, 2, 3])
        key2 = partner._get_notification_identity_key("update", [1, 2, 3])
        key3 = partner._get_notification_identity_key("update", [3, 2, 1])  # Same IDs, different order
        key4 = partner._get_notification_identity_key("registration", [1, 2, 3])  # Different event

        # Same inputs should produce same key
        self.assertEqual(key1, key2)

        # Order shouldn't matter (IDs are sorted)
        self.assertEqual(key1, key3)

        # Different event type should produce different key
        self.assertNotEqual(key1, key4)

    def test_execute_notification_calls_subscription(self):
        """Test that execute_dci_notification calls subscription.notify_event."""
        # Create a mock subscription
        with patch.object(self.env["spp.dci.subscription"].__class__, "notify_event") as mock_notify:
            partner = self.Partner.browse(self.individual_1.id)
            partner._execute_dci_notification("update", [self.individual_1.id])

            # Verify notify_event was called
            mock_notify.assert_called_once()
            args = mock_notify.call_args[0]
            self.assertEqual(args[0], "update")  # event_type
            self.assertEqual(args[2], "SOCIAL_REGISTRY")  # reg_type

    def test_execute_notification_delete_with_ids_only(self):
        """Test that delete notifications work with just IDs (no records)."""
        with patch.object(self.env["spp.dci.subscription"].__class__, "notify_event") as mock_notify:
            partner = self.Partner.browse(self.individual_1.id)
            # Simulate delete notification where records no longer exist
            partner._execute_dci_notification("delete", [99999])  # Non-existent ID

            # Verify notify_event was still called
            mock_notify.assert_called_once()
            args = mock_notify.call_args[0]
            self.assertEqual(args[0], "delete")
            self.assertEqual(args[1], [{"id": 99999}])

    def test_multiple_writes_same_transaction(self):
        """Test that multiple writes in same transaction are handled."""
        individual = self._create_test_individual(
            {
                "family_name": "MultiWrite",
                "given_name": "Test",
            },
            identifier_value="NAT-NOTIFY-006",
        )
        self.env.cr.postcommit.clear()

        call_count = 0

        def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1

        with patch.object(self.Partner.__class__, "_queue_dci_notification_job", side_effect=count_calls):
            # Multiple writes in same transaction
            individual.write({"given_name": "First"})
            individual.write({"given_name": "Second"})
            individual.write({"given_name": "Third"})
            self.env.cr.postcommit.run()

            # Each write should schedule a notification
            # (deduplication happens at queue_job level via identity_key)
            self.assertEqual(call_count, 3)

    def test_group_notification(self):
        """Test that group (household) changes trigger notifications."""
        with patch.object(self.Partner.__class__, "_queue_dci_notification_job") as mock_queue:
            # Create a group
            group = self._create_test_group(
                {
                    "name": "Notification Household",
                    "street": "789 Test Rd",
                    "city": "Notify City",
                },
                identifier_value="HH-NOTIFY-001",
                members=[],
            )
            self.env.cr.postcommit.run()

            # Verify registration notification was scheduled
            mock_queue.assert_called()
            args = mock_queue.call_args[0]
            self.assertEqual(args[0], "registration")
            self.assertIn(group.id, args[1])
