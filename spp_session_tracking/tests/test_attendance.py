# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests.common import TransactionCase


class TestAttendance(TransactionCase):
    """Test session attendance tracking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env["spp.session"]
        cls.SessionType = cls.env["spp.session.type"]
        cls.SessionTopic = cls.env["spp.session.topic"]
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
                    Command.link(cls.participant1.id),
                    Command.link(cls.participant2.id),
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

    # --- Edge case tests ---

    def test_attendance_rate_zero_expected(self):
        """Test attendance rate is 0.0 when session has no expected participants."""
        empty_session = self.Session.create(
            {
                "name": "No Expected Participants Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
            }
        )
        self.Attendance.create(
            {
                "session_id": empty_session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        empty_session.invalidate_recordset(["attendance_count", "attendance_rate"])
        self.assertEqual(empty_session.attendance_rate, 0.0)

    def test_attendance_rate_no_records(self):
        """Test attendance rate and count are 0 when expected participants exist but no records."""
        no_records_session = self.Session.create(
            {
                "name": "No Attendance Records Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
                "expected_participant_ids": [
                    Command.link(self.participant1.id),
                    Command.link(self.participant2.id),
                ],
            }
        )
        self.assertEqual(no_records_session.attendance_rate, 0.0)
        self.assertEqual(no_records_session.attendance_count, 0)

    def test_attendance_count_all_excused(self):
        """Test attendance count is 0 when all records have is_attended=False."""
        excused_session = self.Session.create(
            {
                "name": "All Excused Session",
                "session_type_id": self.session_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
                "expected_participant_ids": [
                    Command.link(self.participant1.id),
                    Command.link(self.participant2.id),
                ],
            }
        )
        self.Attendance.create(
            {
                "session_id": excused_session.id,
                "participant_id": self.participant1.id,
                "is_attended": False,
                "is_excused": True,
            }
        )
        self.Attendance.create(
            {
                "session_id": excused_session.id,
                "participant_id": self.participant2.id,
                "is_attended": False,
                "is_excused": True,
            }
        )
        excused_session.invalidate_recordset(["attendance_count", "attendance_rate"])
        self.assertEqual(excused_session.attendance_count, 0)

    # --- Topic tests ---

    def test_topic_assignment_with_track_topics_enabled(self):
        """Test assigning topics to a session with a type that has track_topics=True."""
        topic_type = self.SessionType.create(
            {
                "name": "Topic Tracking Type",
                "code": "TOPTRACK",
                "track_topics": True,
            }
        )
        topic1 = self.SessionTopic.create(
            {
                "name": "Introduction",
                "session_type_id": topic_type.id,
            }
        )
        topic2 = self.SessionTopic.create(
            {
                "name": "Advanced Techniques",
                "session_type_id": topic_type.id,
            }
        )
        session_with_topics = self.Session.create(
            {
                "name": "Session With Topics",
                "session_type_id": topic_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
                "topic_ids": [
                    Command.link(topic1.id),
                    Command.link(topic2.id),
                ],
            }
        )
        self.assertEqual(len(session_with_topics.topic_ids), 2)
        self.assertIn(topic1, session_with_topics.topic_ids)
        self.assertIn(topic2, session_with_topics.topic_ids)

    def test_topic_assignment_type_without_tracking(self):
        """Test that topics can be assigned to a session even when track_topics is False."""
        no_track_type = self.SessionType.create(
            {
                "name": "No Topic Tracking Type",
                "code": "NOTRACK",
                "track_topics": False,
            }
        )
        standalone_topic = self.SessionTopic.create(
            {
                "name": "Standalone Topic",
            }
        )
        session_without_tracking = self.Session.create(
            {
                "name": "Session Without Topic Tracking",
                "session_type_id": no_track_type.id,
                "date": fields.Date.today(),
                "facilitator_id": self.facilitator.id,
                "topic_ids": [Command.link(standalone_topic.id)],
            }
        )
        self.assertEqual(len(session_without_tracking.topic_ids), 1)
        self.assertIn(standalone_topic, session_without_tracking.topic_ids)

    # --- Related field and field coverage tests ---

    def test_attendance_related_fields(self):
        """Test session_date and session_type_id are populated from session."""
        attendance = self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
            }
        )
        self.assertEqual(attendance.session_date, self.session.date)
        self.assertEqual(attendance.session_type_id, self.session_type)

    def test_attendance_with_time(self):
        """Test attendance record with attendance_time."""
        now = fields.Datetime.now()
        attendance = self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant1.id,
                "is_attended": True,
                "attendance_time": now,
            }
        )
        self.assertEqual(attendance.attendance_time, now)

    def test_attendance_excused_with_reason(self):
        """Test excused attendance with reason."""
        attendance = self.Attendance.create(
            {
                "session_id": self.session.id,
                "participant_id": self.participant1.id,
                "is_attended": False,
                "is_excused": True,
                "excuse_reason": "Medical appointment",
            }
        )
        self.assertTrue(attendance.is_excused)
        self.assertEqual(attendance.excuse_reason, "Medical appointment")

    def test_topic_full_creation(self):
        """Test topic creation with all fields."""
        topic = self.SessionTopic.create(
            {
                "name": "Full Topic",
                "code": "FULL",
                "description": "A complete topic",
                "sequence": 5,
            }
        )
        self.assertEqual(topic.code, "FULL")
        self.assertEqual(topic.description, "A complete topic")
        self.assertEqual(topic.sequence, 5)
        self.assertTrue(topic.active)

    def test_topic_archive(self):
        """Test topic can be archived."""
        topic = self.SessionTopic.create({"name": "Archivable Topic"})
        self.assertTrue(topic.active)
        topic.active = False
        self.assertFalse(topic.active)
