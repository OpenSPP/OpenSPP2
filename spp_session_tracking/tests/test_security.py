# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSessionSecurity(TransactionCase):
    """Test access control for session tracking module."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SessionType = cls.env["spp.session.type"]
        cls.Session = cls.env["spp.session"]
        cls.Attendance = cls.env["spp.session.attendance"]
        cls.Partner = cls.env["res.partner"]

        cls.session_user = cls.env["res.users"].create(
            {
                "name": "Session User",
                "login": "test_session_user",
                "group_ids": [
                    Command.link(cls.env.ref("spp_session_tracking.group_session_user").id),
                ],
            }
        )
        cls.session_manager = cls.env["res.users"].create(
            {
                "name": "Session Manager",
                "login": "test_session_manager",
                "group_ids": [
                    Command.link(cls.env.ref("spp_session_tracking.group_session_manager").id),
                ],
            }
        )

        cls.session_type = cls.SessionType.create(
            {
                "name": "Security Test Type",
                "code": "SECTEST",
            }
        )

        cls.participant1 = cls.Partner.create({"name": "Security Participant 1"})
        cls.participant2 = cls.Partner.create({"name": "Security Participant 2"})

        # Session facilitated by session_user
        cls.own_session = cls.Session.create(
            {
                "name": "Own Facilitated Session",
                "session_type_id": cls.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": cls.session_user.id,
            }
        )

        # Session where session_user is co-facilitator
        cls.co_facilitated_session = cls.Session.create(
            {
                "name": "Co-Facilitated Session",
                "session_type_id": cls.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": cls.session_manager.id,
                "co_facilitator_ids": [Command.link(cls.session_user.id)],
            }
        )

        # Session facilitated by someone else entirely (manager)
        cls.other_session = cls.Session.create(
            {
                "name": "Another Facilitator Session",
                "session_type_id": cls.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": cls.session_manager.id,
            }
        )

        # Second company for multi-company tests
        cls.company_b = cls.env["res.company"].create({"name": "Company B"})

        cls.company_b_session = cls.Session.create(
            {
                "name": "Company B Session",
                "session_type_id": cls.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": cls.session_manager.id,
                "company_id": cls.company_b.id,
            }
        )

    def test_group_hierarchy_manager_has_user(self):
        """Test manager group implies user group permissions."""
        self.assertTrue(
            self.session_manager.has_group("spp_session_tracking.group_session_user"),
            "Manager should have user group permissions",
        )

    def test_admin_has_manager(self):
        """Test OpenSPP admin has session manager access."""
        admin = self.env["res.users"].create(
            {
                "name": "Admin Test User",
                "login": "test_admin_session",
                "group_ids": [
                    Command.link(self.env.ref("spp_security.group_spp_admin").id),
                ],
            }
        )
        self.assertTrue(
            admin.has_group("spp_session_tracking.group_session_manager"),
            "SPP admin should have session manager access",
        )

    def test_user_can_read_all_sessions(self):
        """Test session user can read all sessions including ones they don't facilitate."""
        sessions_as_user = self.Session.with_user(self.session_user).search([])
        session_ids = sessions_as_user.ids
        self.assertIn(self.own_session.id, session_ids, "User should read own session")
        self.assertIn(self.other_session.id, session_ids, "User should read sessions from other facilitators")
        self.assertIn(self.co_facilitated_session.id, session_ids, "User should read co-facilitated sessions")

    def test_user_can_read_session_not_facilitated(self):
        """Test session user can read a session where they have no facilitation role."""
        session_as_user = self.other_session.with_user(self.session_user)
        # Reading a field should not raise
        self.assertEqual(session_as_user.name, "Another Facilitator Session")

    def test_user_can_write_own_facilitated_session(self):
        """Test session user can write a session they facilitate."""
        self.own_session.with_user(self.session_user).write({"location": "Room A"})
        self.assertEqual(self.own_session.location, "Room A")

    def test_user_can_write_co_facilitated_session(self):
        """Test session user can write a session where they are co-facilitator."""
        self.co_facilitated_session.with_user(self.session_user).write({"location": "Room B"})
        self.assertEqual(self.co_facilitated_session.location, "Room B")

    def test_user_cannot_write_other_facilitator_session(self):
        """Test session user cannot write a session they do not facilitate or co-facilitate."""
        with self.assertRaises(AccessError):
            self.other_session.with_user(self.session_user).write({"location": "Unauthorized"})

    def test_user_can_create_attendance_on_own_session(self):
        """Test session user can create attendance records on their own facilitated session."""
        attendance = self.Attendance.with_user(self.session_user).create(
            {
                "session_id": self.own_session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        self.assertTrue(attendance.is_attended)

    def test_user_can_create_attendance_on_co_facilitated_session(self):
        """Test session user can create attendance records on a co-facilitated session."""
        attendance = self.Attendance.with_user(self.session_user).create(
            {
                "session_id": self.co_facilitated_session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        self.assertTrue(attendance.is_attended)

    def test_user_cannot_create_attendance_on_other_session(self):
        """Test session user cannot create attendance on a session they do not facilitate."""
        with self.assertRaises(AccessError):
            self.Attendance.with_user(self.session_user).create(
                {
                    "session_id": self.other_session.id,
                    "participant_id": self.participant1.id,
                    "is_attended": True,
                }
            )

    def test_manager_can_create_session(self):
        """Test session manager can create sessions."""
        session = self.Session.with_user(self.session_manager).create(
            {
                "name": "Manager Created Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.session_manager.id,
            }
        )
        self.assertEqual(session.name, "Manager Created Session")

    def test_manager_can_read_all_sessions(self):
        """Test session manager can read all sessions."""
        sessions_as_manager = self.Session.with_user(self.session_manager).search([])
        session_ids = sessions_as_manager.ids
        self.assertIn(self.own_session.id, session_ids, "Manager should read user-facilitated session")
        self.assertIn(self.other_session.id, session_ids, "Manager should read all sessions")

    def test_manager_can_write_any_session(self):
        """Test session manager can write sessions regardless of facilitator."""
        self.own_session.with_user(self.session_manager).write({"location": "Manager Edit"})
        self.assertEqual(self.own_session.location, "Manager Edit")

    def test_manager_can_delete_session(self):
        """Test session manager can delete sessions."""
        session_to_delete = self.Session.create(
            {
                "name": "Session To Delete",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.session_manager.id,
            }
        )
        session_to_delete.with_user(self.session_manager).unlink()
        self.assertFalse(session_to_delete.exists(), "Session should have been deleted")

    def test_manager_can_create_session_type(self):
        """Test session manager can create session types."""
        session_type = self.SessionType.with_user(self.session_manager).create(
            {
                "name": "Manager Created Type",
                "code": "MGRTYPE",
            }
        )
        self.assertEqual(session_type.name, "Manager Created Type")

    def test_user_cannot_create_session_type(self):
        """Test session user cannot create session types."""
        with self.assertRaises(AccessError):
            self.SessionType.with_user(self.session_user).create(
                {
                    "name": "User Created Type",
                    "code": "USRTYPE",
                }
            )

    def test_user_cannot_create_session(self):
        """Test session user cannot create sessions (manager-only)."""
        with self.assertRaises(AccessError):
            self.Session.with_user(self.session_user).create(
                {
                    "name": "User Created Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.session_user.id,
                }
            )

    def test_user_cannot_delete_session(self):
        """Test session user cannot delete sessions."""
        with self.assertRaises(AccessError):
            self.own_session.with_user(self.session_user).unlink()

    def test_user_cannot_delete_attendance(self):
        """Test session user cannot delete attendance records."""
        attendance = self.Attendance.create(
            {
                "session_id": self.own_session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        with self.assertRaises(AccessError):
            attendance.with_user(self.session_user).unlink()

    def test_multi_company_user_cannot_read_other_company_session(self):
        """Test user in company A cannot see sessions belonging to company B."""
        # session_user belongs to the default company (company A)
        # company_b_session belongs to company B
        sessions_as_user = self.Session.with_user(self.session_user).search([])
        self.assertNotIn(
            self.company_b_session.id,
            sessions_as_user.ids,
            "User should not see sessions from a company they do not belong to",
        )
