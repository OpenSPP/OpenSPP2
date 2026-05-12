# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSessionConstraints(TransactionCase):
    """Test database and model constraints for session tracking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env["spp.session"]
        cls.SessionType = cls.env["spp.session.type"]
        cls.Attendance = cls.env["spp.session.attendance"]
        cls.Partner = cls.env["res.partner"]

        cls.session_type = cls.SessionType.create(
            {
                "name": "Constraint Test Type",
                "code": "CONSTR",
            }
        )

        cls.facilitator = cls.env.user

        cls.participant1 = cls.Partner.create({"name": "Constraint Participant 1"})
        cls.participant2 = cls.Partner.create({"name": "Constraint Participant 2"})

        cls.session = cls.Session.create(
            {
                "name": "Constraint Test Session",
                "session_type_id": cls.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": cls.facilitator.id,
            }
        )

    def test_duplicate_attendance_raises_integrity_error(self):
        """Test that creating two attendance records for the same participant and session raises IntegrityError."""
        self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.Attendance.create(
                {
                    "session_id": self.session.id,
                    "participant_id": self.participant1.id,
                    "is_attended": False,
                }
            )

    def test_end_time_before_start_time_raises_validation_error(self):
        """Test that setting end_time before start_time raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.Session.create(
                {
                    "name": "Invalid Time Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                    "start_time": 14.0,
                    "end_time": 10.0,
                }
            )

    def test_end_time_before_start_time_on_write_raises_validation_error(self):
        """Test that writing end_time before start_time raises ValidationError."""
        session = self.Session.create(
            {
                "name": "Valid Time Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
                "start_time": 9.0,
                "end_time": 11.0,
            }
        )
        with self.assertRaises(ValidationError):
            session.write({"end_time": 8.0})

    def test_delete_session_type_with_sessions_raises_integrity_error(self):
        """Test that deleting a session type that has sessions raises IntegrityError."""
        session_type_to_delete = self.SessionType.create(
            {
                "name": "Type With Sessions",
                "code": "TWSESS",
            }
        )
        self.Session.create(
            {
                "name": "Session Blocking Deletion",
                "session_type_id": session_type_to_delete.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            session_type_to_delete.unlink()

    def test_delete_participant_with_attendance_raises_integrity_error(self):
        """Test that deleting a participant who has attendance records raises IntegrityError."""
        participant_to_delete = self.Partner.create({"name": "Participant With Attendance"})
        self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": participant_to_delete.id,
                "is_attended": True,
            }
        )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            participant_to_delete.unlink()

    def test_unique_session_type_code_raises_integrity_error(self):
        """Test that creating two session types with the same code raises IntegrityError."""
        self.SessionType.create(
            {
                "name": "Unique Code Type A",
                "code": "DUPCODE",
            }
        )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.SessionType.create(
                {
                    "name": "Unique Code Type B",
                    "code": "DUPCODE",
                }
            )
