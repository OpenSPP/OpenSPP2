# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestSession(TransactionCase):
    """Test session management."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env["spp.session"]
        cls.SessionType = cls.env["spp.session.type"]
        cls.Partner = cls.env["res.partner"]

        cls.session_type = cls.SessionType.create(
            {
                "name": "Training Session",
                "code": "TRAIN",
            }
        )

        cls.facilitator = cls.env.user

        cls.participant1 = cls.Partner.create(
            {
                "name": "Participant 1",
            }
        )
        cls.participant2 = cls.Partner.create(
            {
                "name": "Participant 2",
            }
        )

    def test_session_creation(self):
        """Test session can be created."""
        session = self.Session.create(
            {
                "name": "Test Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        self.assertEqual(session.state, "scheduled")
        self.assertEqual(session.attendance_count, 0)

    def test_session_duration_computation(self):
        """Test session duration is computed correctly."""
        session = self.Session.create(
            {
                "name": "Morning Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
                "start_time": 9.0,  # 9:00 AM
                "end_time": 12.0,  # 12:00 PM
            }
        )
        self.assertEqual(session.duration_hours, 3.0)

    def test_session_state_workflow(self):
        """Test session state transitions."""
        session = self.Session.create(
            {
                "name": "Workflow Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )

        self.assertEqual(session.state, "scheduled")

        session.action_start()
        self.assertEqual(session.state, "in_progress")

        session.action_complete()
        self.assertEqual(session.state, "completed")

    def test_session_cancel(self):
        """Test session cancellation."""
        session = self.Session.create(
            {
                "name": "Cancel Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )

        session.action_cancel()
        self.assertEqual(session.state, "cancelled")

    def test_session_with_expected_participants(self):
        """Test session with expected participants."""
        session = self.Session.create(
            {
                "name": "Group Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
                "expected_participant_ids": [
                    Command.link(self.participant1.id),
                    Command.link(self.participant2.id),
                ],
            }
        )
        self.assertEqual(len(session.expected_participant_ids), 2)

    # --- State transition tests ---

    def test_valid_transition_start(self):
        """Test valid transition from scheduled to in_progress."""
        session = self.Session.create(
            {
                "name": "Start Transition Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        self.assertEqual(session.state, "scheduled")
        session.action_start()
        self.assertEqual(session.state, "in_progress")

    def test_valid_transition_complete(self):
        """Test valid transition from in_progress to completed."""
        session = self.Session.create(
            {
                "name": "Complete Transition Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        session.action_start()
        session.action_complete()
        self.assertEqual(session.state, "completed")

    def test_valid_transition_cancel_from_scheduled(self):
        """Test valid transition from scheduled to cancelled."""
        session = self.Session.create(
            {
                "name": "Cancel From Scheduled Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        session.action_cancel()
        self.assertEqual(session.state, "cancelled")

    def test_valid_transition_cancel_from_in_progress(self):
        """Test valid transition from in_progress to cancelled."""
        session = self.Session.create(
            {
                "name": "Cancel From In Progress Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        session.action_start()
        session.action_cancel()
        self.assertEqual(session.state, "cancelled")

    def test_invalid_transition_start_from_completed(self):
        """Test that starting a completed session raises UserError."""
        session = self.Session.create(
            {
                "name": "Start From Completed Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        session.action_start()
        session.action_complete()
        with self.assertRaises(UserError):
            session.action_start()

    def test_invalid_transition_start_from_cancelled(self):
        """Test that starting a cancelled session raises UserError."""
        session = self.Session.create(
            {
                "name": "Start From Cancelled Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        session.action_cancel()
        with self.assertRaises(UserError):
            session.action_start()

    def test_invalid_transition_complete_from_scheduled(self):
        """Test that completing a scheduled session raises UserError."""
        session = self.Session.create(
            {
                "name": "Complete From Scheduled Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        with self.assertRaises(UserError):
            session.action_complete()

    def test_invalid_transition_cancel_from_completed(self):
        """Test that cancelling a completed session raises UserError."""
        session = self.Session.create(
            {
                "name": "Cancel From Completed Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        session.action_start()
        session.action_complete()
        with self.assertRaises(UserError):
            session.action_cancel()

    def test_invalid_transition_cancel_from_cancelled(self):
        """Test that cancelling an already cancelled session raises UserError."""
        session = self.Session.create(
            {
                "name": "Cancel From Cancelled Test",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        session.action_cancel()
        with self.assertRaises(UserError):
            session.action_cancel()

    # --- Computed field edge cases ---

    def test_duration_only_start_time(self):
        """Test that duration is 0.0 when only start_time is set."""
        session = self.Session.create(
            {
                "name": "Only Start Time Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
                "start_time": 9.0,
            }
        )
        self.assertEqual(session.duration_hours, 0.0)

    def test_duration_only_end_time(self):
        """Test that duration is 0.0 when only end_time is set."""
        session = self.Session.create(
            {
                "name": "Only End Time Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
                "end_time": 12.0,
            }
        )
        self.assertEqual(session.duration_hours, 0.0)

    def test_session_type_session_count(self):
        """Test that session_count on session type reflects actual sessions."""
        dedicated_type = self.SessionType.create(
            {
                "name": "Counted Type",
                "code": "CNTTYPE",
            }
        )
        initial_count = dedicated_type.session_count
        self.Session.create(
            {
                "name": "Count Session 1",
                "session_type_id": dedicated_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        self.Session.create(
            {
                "name": "Count Session 2",
                "session_type_id": dedicated_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        dedicated_type.invalidate_recordset(["session_count"])
        self.assertEqual(dedicated_type.session_count, initial_count + 2)

    def test_action_view_sessions(self):
        """Test action_view_sessions returns correct action dictionary."""
        action = self.session_type.action_view_sessions()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.session")
        self.assertEqual(action["domain"], [("session_type_id", "=", self.session_type.id)])
        self.assertEqual(action["context"]["default_session_type_id"], self.session_type.id)

    def test_session_type_frequency(self):
        """Test session type frequency field."""
        session_type = self.SessionType.create(
            {
                "name": "Weekly Type",
                "frequency": "weekly",
            }
        )
        self.assertEqual(session_type.frequency, "weekly")

    def test_session_type_archive(self):
        """Test session type can be archived."""
        session_type = self.SessionType.create({"name": "Archivable Type"})
        self.assertTrue(session_type.active)
        session_type.active = False
        self.assertFalse(session_type.active)

    def test_session_type_count_multiple_types(self):
        """Test session_count works correctly across multiple types simultaneously."""
        type_a = self.SessionType.create({"name": "Type A"})
        type_b = self.SessionType.create({"name": "Type B"})
        self.Session.create(
            {
                "name": "S1",
                "session_type_id": type_a.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        self.Session.create(
            {
                "name": "S2",
                "session_type_id": type_a.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        self.Session.create(
            {
                "name": "S3",
                "session_type_id": type_b.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        (type_a | type_b).invalidate_recordset(["session_count"])
        self.assertEqual(type_a.session_count, 2)
        self.assertEqual(type_b.session_count, 1)

    def test_write_state_multi_record_invalid(self):
        """Test that write() on multiple records rejects invalid transition for any record."""
        session1 = self.Session.create(
            {
                "name": "Multi 1",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        session2 = self.Session.create(
            {
                "name": "Multi 2",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        session1.action_start()
        session1.action_complete()
        # session1 is completed, session2 is scheduled
        # Both to in_progress should fail because session1 cannot transition
        with self.assertRaises(UserError):
            (session1 | session2).write({"state": "in_progress"})
