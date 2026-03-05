# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests.common import TransactionCase


class TestAttendance(TransactionCase):
    """Test session attendance tracking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env["spp.session"]
        cls.SessionType = cls.env["spp.session.type"]
        cls.Attendance = cls.env["spp.session.attendance"]
        cls.Partner = cls.env["res.partner"]

        cls.session_type = cls.SessionType.create(
            {
                "name": "Training",
                "code": "TRAIN",
            }
        )

        cls.facilitator = cls.env.user

        cls.participant1 = cls.Partner.create({"name": "John Doe"})
        cls.participant2 = cls.Partner.create({"name": "Jane Doe"})

        cls.session = cls.Session.create(
            {
                "name": "Test Training",
                "session_type_id": cls.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": cls.facilitator.id,
                "expected_participant_ids": [
                    (4, cls.participant1.id),
                    (4, cls.participant2.id),
                ],
            }
        )

    def test_attendance_creation(self):
        """Test attendance record can be created."""
        attendance = self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        self.assertTrue(attendance.is_attended)

    def test_attendance_count_computation(self):
        """Test attendance count is computed correctly."""
        self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant2.id,
                "is_attended": False,
            }
        )

        self.session.invalidate_recordset(["attendance_count", "attendance_rate"])
        self.assertEqual(self.session.attendance_count, 1)

    def test_attendance_rate_computation(self):
        """Test attendance rate is computed correctly."""
        self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant2.id,
                "is_attended": True,
            }
        )

        self.session.invalidate_recordset(["attendance_count", "attendance_rate"])
        self.assertEqual(self.session.attendance_rate, 100.0)

    def test_partial_attendance_rate(self):
        """Test partial attendance rate calculation."""
        self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant2.id,
                "is_attended": False,
            }
        )

        self.session.invalidate_recordset(["attendance_count", "attendance_rate"])
        self.assertEqual(self.session.attendance_rate, 50.0)

    def test_attendance_with_notes(self):
        """Test attendance with notes."""
        attendance = self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant1.id,
                "is_attended": False,
                "notes": "Called in sick",
            }
        )
        self.assertEqual(attendance.notes, "Called in sick")
