# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRegistryViewHistory(TransactionCase):
    """Test cases for Registry View History model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test registrant (individual)
        cls.individual = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )
        # Create test registrant (group)
        cls.group = cls.env["res.partner"].create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )
        # Create non-registrant partner
        cls.non_registrant = cls.env["res.partner"].create(
            {
                "name": "Regular Partner",
                "is_registrant": False,
            }
        )
        cls.ViewHistory = cls.env["spp.registry.view.history"]

    def test_record_view_creates_history(self):
        """Test that viewing a registrant creates a history record."""
        result = self.ViewHistory.record_view(self.individual.id)
        self.assertTrue(result)

        # Check history was created
        history = self.ViewHistory.search(
            [
                ("user_id", "=", self.env.uid),
                ("partner_id", "=", self.individual.id),
            ]
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history.view_count, 1)

    def test_record_view_increments_count(self):
        """Test that viewing the same registrant again increments the count."""
        self.ViewHistory.record_view(self.individual.id)
        self.ViewHistory.record_view(self.individual.id)

        history = self.ViewHistory.search(
            [
                ("user_id", "=", self.env.uid),
                ("partner_id", "=", self.individual.id),
            ]
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history.view_count, 2)

    def test_record_view_non_registrant_fails(self):
        """Test that viewing a non-registrant does not create history."""
        result = self.ViewHistory.record_view(self.non_registrant.id)
        self.assertFalse(result)

        history = self.ViewHistory.search(
            [
                ("user_id", "=", self.env.uid),
                ("partner_id", "=", self.non_registrant.id),
            ]
        )
        self.assertEqual(len(history), 0)

    def test_record_view_invalid_partner_fails(self):
        """Test that viewing an invalid partner ID returns False."""
        result = self.ViewHistory.record_view(999999999)
        self.assertFalse(result)

        result = self.ViewHistory.record_view(None)
        self.assertFalse(result)

    def test_get_recent_registrants(self):
        """Test getting recently viewed registrants."""
        # View both registrants
        self.ViewHistory.record_view(self.individual.id)
        self.ViewHistory.record_view(self.group.id)

        recent = self.ViewHistory.get_recent_registrants(limit=10)
        self.assertEqual(len(recent), 2)

        # Check structure of returned data
        for item in recent:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIn("is_group", item)
            self.assertIn("avatar_128", item)
            self.assertIn("view_date", item)

    def test_get_recent_registrants_respects_limit(self):
        """Test that get_recent_registrants respects the limit parameter."""
        self.ViewHistory.record_view(self.individual.id)
        self.ViewHistory.record_view(self.group.id)

        recent = self.ViewHistory.get_recent_registrants(limit=1)
        self.assertEqual(len(recent), 1)

    def test_clear_user_history(self):
        """Test clearing user's view history."""
        self.ViewHistory.record_view(self.individual.id)
        self.ViewHistory.record_view(self.group.id)

        # Verify history exists
        history = self.ViewHistory.search([("user_id", "=", self.env.uid)])
        self.assertEqual(len(history), 2)

        # Clear history
        result = self.ViewHistory.clear_user_history()
        self.assertTrue(result)

        # Verify history is cleared
        history = self.ViewHistory.search([("user_id", "=", self.env.uid)])
        self.assertEqual(len(history), 0)

    def test_history_is_user_specific(self):
        """Test that history is specific to each user."""
        # Create history as current user
        self.ViewHistory.record_view(self.individual.id)

        # Check history exists for current user
        history_current_user = self.ViewHistory.search([("user_id", "=", self.env.uid)])
        self.assertEqual(len(history_current_user), 1)

        # get_recent_registrants should return only current user's history
        recent = self.ViewHistory.get_recent_registrants()
        self.assertEqual(len(recent), 1)

    def test_cleanup_old_records_removes_oldest(self):
        """Test that cleanup removes oldest records beyond limit."""
        # Create 5 registrants
        registrants = []
        for i in range(5):
            registrants.append(
                self.env["res.partner"].create(
                    {
                        "name": f"Cleanup Test Registrant {i}",
                        "is_registrant": True,
                    }
                )
            )

        # Record views (oldest first)
        for reg in registrants:
            self.ViewHistory.record_view(reg.id)

        # Force cleanup with max_records=3
        self.ViewHistory._cleanup_old_records(max_records=3)

        # Verify only 3 newest records remain
        history = self.ViewHistory.search([("user_id", "=", self.env.uid)])
        self.assertEqual(len(history), 3)

    def test_cleanup_triggered_on_new_record(self):
        """Test cleanup is triggered when creating new history record."""
        # Create 52 registrants and view them (exceeds 50 limit)
        for i in range(52):
            reg = self.env["res.partner"].create(
                {
                    "name": f"Bulk Test Registrant {i}",
                    "is_registrant": True,
                }
            )
            self.ViewHistory.record_view(reg.id)

        # Should have max 50 records due to automatic cleanup
        history = self.ViewHistory.search([("user_id", "=", self.env.uid)])
        self.assertLessEqual(len(history), 50)

    def test_get_recent_registrants_empty_history(self):
        """Test get_recent_registrants with no history."""
        # Clear any existing history first
        self.ViewHistory.clear_user_history()

        recent = self.ViewHistory.get_recent_registrants()
        self.assertEqual(recent, [])

    def test_get_recent_registrants_returns_newest_first(self):
        """Test that get_recent_registrants returns records in descending date order."""
        # Clear any existing history first
        self.ViewHistory.clear_user_history()

        # View individual first, then group
        self.ViewHistory.record_view(self.individual.id)
        self.ViewHistory.record_view(self.group.id)

        recent = self.ViewHistory.get_recent_registrants(limit=10)

        # Most recent (group) should be first
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0]["id"], self.group.id)
        self.assertEqual(recent[1]["id"], self.individual.id)

    def test_cascade_delete_on_partner_deletion(self):
        """Test that history is deleted when partner is deleted."""
        # Create a temporary registrant
        temp_reg = self.env["res.partner"].create(
            {
                "name": "Temp Registrant For Cascade Test",
                "is_registrant": True,
            }
        )
        self.ViewHistory.record_view(temp_reg.id)

        # Verify history exists
        history = self.ViewHistory.search([("partner_id", "=", temp_reg.id)])
        self.assertEqual(len(history), 1)

        # Delete partner
        temp_reg.unlink()

        # History should be cascade deleted
        history = self.ViewHistory.search([("partner_id", "=", temp_reg.id)])
        self.assertEqual(len(history), 0)


@tagged("post_install", "-at_install")
class TestResPartnerViewTracking(TransactionCase):
    """Test view tracking in res.partner extension."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Partner Tracking Test Registrant",
                "is_registrant": True,
                "registration_date": "2024-01-01",
            }
        )
        cls.non_registrant = cls.env["res.partner"].create(
            {
                "name": "Regular Partner For Tracking",
                "is_registrant": False,
            }
        )
        cls.ViewHistory = cls.env["spp.registry.view.history"]

    def test_get_formview_action_records_view_for_registrant(self):
        """Test that get_formview_action records view for registrants."""
        # Clear history first
        self.ViewHistory.clear_user_history()

        # Call get_formview_action
        self.registrant.get_formview_action()

        # Should have created history
        history = self.ViewHistory.search(
            [
                ("user_id", "=", self.env.uid),
                ("partner_id", "=", self.registrant.id),
            ]
        )
        self.assertEqual(len(history), 1)

    def test_get_formview_action_no_record_for_non_registrant(self):
        """Test that get_formview_action does not record for non-registrants."""
        # Clear history first
        self.ViewHistory.clear_user_history()

        self.non_registrant.get_formview_action()

        history = self.ViewHistory.search(
            [
                ("user_id", "=", self.env.uid),
                ("partner_id", "=", self.non_registrant.id),
            ]
        )
        self.assertEqual(len(history), 0)
