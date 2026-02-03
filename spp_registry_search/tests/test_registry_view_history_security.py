# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRegistryViewHistorySecurity(TransactionCase):
    """Security tests for Registry View History - user isolation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test users with registry read access and base user group
        cls.user_1 = cls.env["res.users"].create(
            {
                "name": "Test User 1",
                "login": "test_user_1_security",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("spp_registry.group_registry_read").id,
                        ],
                    )
                ],
            }
        )
        cls.user_2 = cls.env["res.users"].create(
            {
                "name": "Test User 2",
                "login": "test_user_2_security",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("spp_registry.group_registry_read").id,
                        ],
                    )
                ],
            }
        )

        # Create test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Security Test Registrant",
                "is_registrant": True,
            }
        )

        cls.ViewHistory = cls.env["spp.registry.view.history"]

    def test_user_cannot_read_other_users_history(self):
        """Test record rule: users can only read their own history."""
        # User 1 creates history
        self.ViewHistory.with_user(self.user_1).record_view(self.registrant.id)

        # User 2 should not see user 1's history
        history_as_user_2 = self.ViewHistory.with_user(self.user_2).search([])
        self.assertEqual(len(history_as_user_2), 0)

        # User 1 should see their own history
        history_as_user_1 = self.ViewHistory.with_user(self.user_1).search([])
        self.assertEqual(len(history_as_user_1), 1)

    def test_user_cannot_write_other_users_history(self):
        """Test that users cannot modify other users' history."""
        # User 1 creates history
        self.ViewHistory.with_user(self.user_1).record_view(self.registrant.id)

        # Get the history record as superuser to find it
        history = self.ViewHistory.sudo().search(
            [
                ("user_id", "=", self.user_1.id),
            ]
        )

        # User 2 should not be able to write to it
        with self.assertRaises(AccessError):
            history.with_user(self.user_2).write({"view_count": 999})

    def test_user_cannot_delete_other_users_history(self):
        """Test that users cannot delete other users' history."""
        # User 1 creates history
        self.ViewHistory.with_user(self.user_1).record_view(self.registrant.id)

        history = self.ViewHistory.sudo().search(
            [
                ("user_id", "=", self.user_1.id),
            ]
        )

        # User 2 should not be able to delete it
        with self.assertRaises(AccessError):
            history.with_user(self.user_2).unlink()

    def test_clear_history_only_affects_own_records(self):
        """Test that clear_user_history only clears own records."""
        # Both users create history
        self.ViewHistory.with_user(self.user_1).record_view(self.registrant.id)
        self.ViewHistory.with_user(self.user_2).record_view(self.registrant.id)

        # User 1 clears their history
        self.ViewHistory.with_user(self.user_1).clear_user_history()

        # User 1's history should be empty
        history_user_1 = self.ViewHistory.sudo().search([("user_id", "=", self.user_1.id)])
        self.assertEqual(len(history_user_1), 0)

        # User 2's history should still exist
        history_user_2 = self.ViewHistory.sudo().search([("user_id", "=", self.user_2.id)])
        self.assertEqual(len(history_user_2), 1)

    def test_get_recent_only_returns_own_records(self):
        """Test that get_recent_registrants only returns user's own records."""
        # Both users view the same registrant
        self.ViewHistory.with_user(self.user_1).record_view(self.registrant.id)
        self.ViewHistory.with_user(self.user_2).record_view(self.registrant.id)

        # User 1's recent should only contain their own
        recent_user_1 = self.ViewHistory.with_user(self.user_1).get_recent_registrants()
        self.assertEqual(len(recent_user_1), 1)

        # User 2's recent should only contain their own
        recent_user_2 = self.ViewHistory.with_user(self.user_2).get_recent_registrants()
        self.assertEqual(len(recent_user_2), 1)

    def test_record_view_creates_for_current_user(self):
        """Test that record_view creates history for the calling user."""
        # User 1 records a view
        self.ViewHistory.with_user(self.user_1).record_view(self.registrant.id)

        # Should be attributed to user 1
        history = self.ViewHistory.sudo().search([("partner_id", "=", self.registrant.id)])
        self.assertEqual(len(history), 1)
        self.assertEqual(history.user_id.id, self.user_1.id)
