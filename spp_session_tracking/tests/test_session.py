# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields
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
                    (4, self.participant1.id),
                    (4, self.participant2.id),
                ],
            }
        )
        self.assertEqual(len(session.expected_participant_ids), 2)
