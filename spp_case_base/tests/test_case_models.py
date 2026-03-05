"""Tests for case assessment, referral, note, and visit models."""

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseModels(TransactionCase):
    """Tests for spp.case.assessment, spp.case.referral, spp.case.note, spp.case.visit."""

    @classmethod
    def setUpClass(cls):
        """Set up test data shared across all test methods."""
        super().setUpClass()

        # Create test users
        cls.case_worker = cls.env["res.users"].create(
            {
                "name": "Test Case Worker",
                "login": "test_cm_worker",
                "email": "cm_worker@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                ],
            }
        )

        cls.supervisor = cls.env["res.users"].create(
            {
                "name": "Test CM Supervisor",
                "login": "test_cm_supervisor",
                "email": "cm_supervisor@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_supervisor").id),
                ],
            }
        )

        # Create test partner (client)
        cls.client = cls.env["res.partner"].create(
            {
                "name": "Test CM Client",
                "email": "cm_client@test.com",
            }
        )

        # Create case type
        cls.case_type = cls.env["spp.case.type"].create(
            {
                "name": "CM Test Type",
                "code": "CMT001",
                "domain": "social_protection",
                "default_intensity": "2",
            }
        )

        # Create case stage
        cls.stage = cls.env["spp.case.stage"].create(
            {
                "name": "CM Test Intake",
                "sequence": 1,
                "phase": "intake",
                "is_closed": False,
            }
        )

        # Create a test case
        cls.case = cls.env["spp.case"].create(
            {
                "case_type_id": cls.case_type.id,
                "partner_id": cls.client.id,
                "case_worker_id": cls.case_worker.id,
                "stage_id": cls.stage.id,
                "presenting_issue": "<p>Test presenting issue</p>",
            }
        )

    # -------------------------------------------------------------------------
    # spp.case.assessment tests
    # -------------------------------------------------------------------------

    def _make_assessment(self, **kwargs):
        """Helper to create a case assessment with sensible defaults."""
        vals = {
            "case_id": self.case.id,
            "assessment_type": "periodic",
            "assessment_date": fields.Date.today(),
            "assessor_id": self.case_worker.id,
        }
        vals.update(kwargs)
        return self.env["spp.case.assessment"].create(vals)

    def test_assessment_compute_name_complete(self):
        """_compute_name produces a name when all fields are present."""
        assessment = self._make_assessment(assessment_type="intake")
        # Name should include the case name, type label, and date
        self.assertIn(self.case.name, assessment.name)
        self.assertIn("Intake Assessment", assessment.name)
        self.assertIn(str(fields.Date.today()), assessment.name)

    def test_assessment_compute_name_incomplete(self):
        """_compute_name returns 'New Assessment' when required fields are missing."""
        # Use new() to get an unsaved record missing case_id
        assessment = self.env["spp.case.assessment"].new(
            {
                "assessment_type": "periodic",
                "assessment_date": fields.Date.today(),
            }
        )
        assessment._compute_name()
        self.assertEqual(assessment.name, "New Assessment")

    def test_assessment_compute_risk_level_low(self):
        """_compute_risk_level maps score 0-25 to 'low'."""
        assessment = self._make_assessment(risk_score=0)
        self.assertEqual(assessment.risk_level, "low")

        assessment.risk_score = 25
        assessment._compute_risk_level()
        self.assertEqual(assessment.risk_level, "low")

    def test_assessment_compute_risk_level_medium(self):
        """_compute_risk_level maps score 26-50 to 'medium'."""
        assessment = self._make_assessment(risk_score=26)
        self.assertEqual(assessment.risk_level, "medium")

        assessment.risk_score = 50
        assessment._compute_risk_level()
        self.assertEqual(assessment.risk_level, "medium")

    def test_assessment_compute_risk_level_high(self):
        """_compute_risk_level maps score 51-75 to 'high'."""
        assessment = self._make_assessment(risk_score=51)
        self.assertEqual(assessment.risk_level, "high")

        assessment.risk_score = 75
        assessment._compute_risk_level()
        self.assertEqual(assessment.risk_level, "high")

    def test_assessment_compute_risk_level_critical(self):
        """_compute_risk_level maps score 76+ to 'critical'."""
        assessment = self._make_assessment(risk_score=76)
        self.assertEqual(assessment.risk_level, "critical")

        assessment.risk_score = 100
        assessment._compute_risk_level()
        self.assertEqual(assessment.risk_level, "critical")

    def test_assessment_compute_risk_level_negative_treated_as_low(self):
        """_compute_risk_level treats a negative score as 'low' (defensive branch)."""
        # Test the compute logic directly via new() to bypass the constraint.
        record = self.env["spp.case.assessment"].new(
            {
                "case_id": self.case.id,
                "assessment_type": "periodic",
                "assessment_date": fields.Date.today(),
                "risk_score": -5,
            }
        )
        record._compute_risk_level()
        self.assertEqual(record.risk_level, "low")

    def test_assessment_check_risk_score_valid(self):
        """_check_risk_score does not raise for scores within 0-100."""
        # Should not raise
        assessment = self._make_assessment(risk_score=50)
        self.assertEqual(assessment.risk_score, 50)

    def test_assessment_check_risk_score_too_high(self):
        """_check_risk_score raises UserError when score > 100."""
        with self.assertRaises(UserError):
            self._make_assessment(risk_score=101)

    def test_assessment_action_complete_from_draft(self):
        """action_complete moves a draft assessment to completed."""
        assessment = self._make_assessment()
        self.assertEqual(assessment.state, "draft")

        assessment.action_complete()
        self.assertEqual(assessment.state, "completed")

    def test_assessment_action_complete_non_draft_raises(self):
        """action_complete raises UserError if assessment is not in draft state."""
        assessment = self._make_assessment()
        assessment.action_complete()  # draft → completed
        # Calling again (now completed) should fail
        with self.assertRaises(UserError):
            assessment.action_complete()

    def test_assessment_action_review_requires_supervisor(self):
        """action_review raises UserError when called by a non-supervisor."""
        assessment = self._make_assessment()
        assessment.action_complete()  # → completed

        # Switch to case_worker context (not a supervisor)
        env_worker = self.env(user=self.case_worker)
        assessment_as_worker = assessment.with_env(env_worker)
        with self.assertRaises(UserError):
            assessment_as_worker.action_review()

    def test_assessment_action_review_by_supervisor(self):
        """action_review moves completed assessment to reviewed when called by supervisor."""
        assessment = self._make_assessment()
        assessment.action_complete()  # → completed

        env_supervisor = self.env(user=self.supervisor)
        assessment_as_supervisor = assessment.with_env(env_supervisor)
        assessment_as_supervisor.action_review()

        self.assertEqual(assessment.state, "reviewed")
        self.assertEqual(assessment.reviewed_by_id, self.supervisor)
        self.assertTrue(assessment.reviewed_date)

    def test_assessment_action_review_non_completed_raises(self):
        """action_review raises UserError if assessment is not completed."""
        assessment = self._make_assessment()
        # Still in draft state
        env_supervisor = self.env(user=self.supervisor)
        assessment_as_supervisor = assessment.with_env(env_supervisor)
        with self.assertRaises(UserError):
            assessment_as_supervisor.action_review()

    def test_assessment_action_reset_to_draft(self):
        """action_reset_to_draft returns a completed assessment to draft."""
        assessment = self._make_assessment()
        assessment.action_complete()
        self.assertEqual(assessment.state, "completed")

        assessment.action_reset_to_draft()
        self.assertEqual(assessment.state, "draft")
        self.assertFalse(assessment.reviewed_by_id)
        self.assertFalse(assessment.reviewed_date)

    def test_assessment_action_reset_to_draft_reviewed_raises(self):
        """action_reset_to_draft raises UserError when assessment is already reviewed."""
        assessment = self._make_assessment()
        assessment.action_complete()

        env_supervisor = self.env(user=self.supervisor)
        assessment.with_env(env_supervisor).action_review()
        self.assertEqual(assessment.state, "reviewed")

        with self.assertRaises(UserError):
            assessment.action_reset_to_draft()

    def test_assessment_action_view_case(self):
        """action_view_case returns an act_window dict pointing to the case."""
        assessment = self._make_assessment()
        result = assessment.action_view_case()

        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.case")
        self.assertEqual(result["res_id"], self.case.id)
        self.assertEqual(result["view_mode"], "form")

    # -------------------------------------------------------------------------
    # spp.case.referral tests
    # -------------------------------------------------------------------------

    def _make_referral(self, **kwargs):
        """Helper to create a case referral with sensible defaults."""
        vals = {
            "case_id": self.case.id,
            "service_name": "Test Service",
            "reason": "Client needs this service",
            "referral_date": fields.Date.today(),
            "referred_by_id": self.case_worker.id,
        }
        vals.update(kwargs)
        return self.env["spp.case.referral"].create(vals)

    def test_referral_compute_is_overdue_past_date_pending(self):
        """_compute_is_overdue is True when follow_up_date is in the past and status is pending."""
        past_date = fields.Date.today() - timedelta(days=1)
        referral = self._make_referral(follow_up_date=past_date, status="pending")
        referral._compute_is_overdue()
        self.assertTrue(referral.is_overdue)

    def test_referral_compute_is_overdue_future_date(self):
        """_compute_is_overdue is False when follow_up_date is in the future."""
        future_date = fields.Date.today() + timedelta(days=1)
        referral = self._make_referral(follow_up_date=future_date, status="pending")
        referral._compute_is_overdue()
        self.assertFalse(referral.is_overdue)

    def test_referral_compute_is_overdue_completed_not_overdue(self):
        """_compute_is_overdue is False when status is completed, even with past date."""
        past_date = fields.Date.today() - timedelta(days=5)
        referral = self._make_referral(follow_up_date=past_date, status="completed")
        referral._compute_is_overdue()
        self.assertFalse(referral.is_overdue)

    def test_referral_compute_is_overdue_rejected_not_overdue(self):
        """_compute_is_overdue is False when status is rejected."""
        past_date = fields.Date.today() - timedelta(days=5)
        referral = self._make_referral(follow_up_date=past_date, status="rejected")
        referral._compute_is_overdue()
        self.assertFalse(referral.is_overdue)

    def test_referral_compute_display_name_with_client(self):
        """_compute_display_name includes service and client name."""
        referral = self._make_referral(service_name="Housing Support")
        referral._compute_display_name()
        self.assertIn("Housing Support", referral.display_name)
        self.assertIn(self.client.name, referral.display_name)

    def test_referral_compute_display_name_service_only(self):
        """_compute_display_name uses service name when no client is on the referral."""
        # Create a case with no partner to test the service-only branch
        referral = self.env["spp.case.referral"].new(
            {
                "service_name": "Orphan Service",
                "reason": "Test",
                "referral_date": fields.Date.today(),
                "referred_by_id": self.case_worker.id,
                # No case_id means no client_id
            }
        )
        referral._compute_display_name()
        self.assertEqual(referral.display_name, "Orphan Service")

    def test_referral_compute_display_name_no_service(self):
        """_compute_display_name falls back to 'Referral #ID' when service_name is empty."""
        # Create a real record, then clear service_name to trigger the fallback branch
        referral = self._make_referral(service_name="Temporary")
        referral.service_name = False
        referral._compute_display_name()
        self.assertIn("Referral #", referral.display_name)
        self.assertIn(str(referral.id), referral.display_name)

    def test_referral_action_accept(self):
        """action_accept changes referral status to 'accepted'."""
        referral = self._make_referral()
        self.assertEqual(referral.status, "pending")
        referral.action_accept()
        self.assertEqual(referral.status, "accepted")

    def test_referral_action_reject(self):
        """action_reject changes referral status to 'rejected'."""
        referral = self._make_referral()
        referral.action_reject()
        self.assertEqual(referral.status, "rejected")

    def test_referral_action_complete(self):
        """action_complete changes referral status to 'completed'."""
        referral = self._make_referral()
        referral.action_complete()
        self.assertEqual(referral.status, "completed")

    def test_referral_create_posts_case_message(self):
        """create() override posts a message to the case chatter."""
        message_count_before = len(self.case.message_ids)
        self._make_referral(service_name="Food Aid")
        message_count_after = len(self.case.message_ids)
        self.assertGreater(message_count_after, message_count_before)

    # -------------------------------------------------------------------------
    # spp.case.note tests
    # -------------------------------------------------------------------------

    def _make_note(self, **kwargs):
        """Helper to create a case note with sensible defaults."""
        vals = {
            "case_id": self.case.id,
            "note_type": "general",
            "content": "<p>Test note content</p>",
            "author_id": self.case_worker.id,
            "note_date": fields.Datetime.now(),
        }
        vals.update(kwargs)
        return self.env["spp.case.note"].create(vals)

    def test_note_compute_note_date_display_with_date(self):
        """_compute_note_date_display returns a formatted string when note_date is set."""
        note = self._make_note()
        note._compute_note_date_display()
        self.assertTrue(note.note_date_display)
        # The value should be the Odoo string representation of the datetime
        expected = fields.Datetime.to_string(note.note_date)
        self.assertEqual(note.note_date_display, expected)

    def test_note_compute_note_date_display_without_date(self):
        """_compute_note_date_display returns empty string when note_date is not set."""
        record = self.env["spp.case.note"].new(
            {
                "case_id": self.case.id,
                "note_type": "general",
                "content": "<p>content</p>",
                "author_id": self.case_worker.id,
            }
        )
        # Clear the default that note_date receives from fields.Datetime.now
        record.note_date = False
        record._compute_note_date_display()
        self.assertEqual(record.note_date_display, "")

    def test_note_compute_display_name_with_date_and_client(self):
        """_compute_display_name includes type, date, and client name."""
        note = self._make_note(note_type="progress")
        note._compute_display_name()
        self.assertIn("Progress Update", note.display_name)
        self.assertIn(self.client.name, note.display_name)

    def test_note_compute_display_name_with_date_no_client(self):
        """_compute_display_name includes type and date when no client is linked."""
        record = self.env["spp.case.note"].new(
            {
                "note_type": "assessment",
                "content": "<p>content</p>",
                "author_id": self.case_worker.id,
                "note_date": fields.Datetime.now(),
                # No case_id, so no client_id
            }
        )
        record._compute_display_name()
        self.assertIn("Assessment", record.display_name)
        # Should not contain a client name separator beyond the date
        self.assertNotIn(self.client.name, record.display_name)

    def test_note_compute_display_name_no_date(self):
        """_compute_display_name returns just the type label when date is missing."""
        record = self.env["spp.case.note"].new(
            {
                "note_type": "supervision",
                "content": "<p>content</p>",
                "author_id": self.case_worker.id,
            }
        )
        # Clear the default that note_date receives from fields.Datetime.now
        record.note_date = False
        record._compute_display_name()
        self.assertEqual(record.display_name, "Supervision Note")

    def test_note_create_posts_case_message(self):
        """create() override posts a message to the case chatter."""
        message_count_before = len(self.case.message_ids)
        self._make_note(note_type="general")
        message_count_after = len(self.case.message_ids)
        self.assertGreater(message_count_after, message_count_before)

    # -------------------------------------------------------------------------
    # spp.case.visit tests
    # -------------------------------------------------------------------------

    def _make_visit(self, **kwargs):
        """Helper to create a case visit with sensible defaults."""
        vals = {
            "case_id": self.case.id,
            "visit_type": "office",
            "visit_date": fields.Datetime.now(),
            "conducted_by_id": self.case_worker.id,
        }
        vals.update(kwargs)
        return self.env["spp.case.visit"].create(vals)

    def test_visit_compute_visit_date_display_with_date(self):
        """_compute_visit_date_display returns a formatted string when visit_date is set."""
        visit = self._make_visit()
        visit._compute_visit_date_display()
        self.assertTrue(visit.visit_date_display)
        expected = fields.Datetime.to_string(visit.visit_date)
        self.assertEqual(visit.visit_date_display, expected)

    def test_visit_compute_visit_date_display_without_date(self):
        """_compute_visit_date_display returns empty string when visit_date is not set."""
        record = self.env["spp.case.visit"].new(
            {
                "case_id": self.case.id,
                "visit_type": "office",
                "conducted_by_id": self.case_worker.id,
            }
        )
        # Clear the default that visit_date receives from fields.Datetime.now
        record.visit_date = False
        record._compute_visit_date_display()
        self.assertEqual(record.visit_date_display, "")

    def test_visit_compute_display_name_with_date_and_client(self):
        """_compute_display_name includes type, date, and client name."""
        visit = self._make_visit(visit_type="home")
        visit._compute_display_name()
        self.assertIn("Home Visit", visit.display_name)
        self.assertIn(self.client.name, visit.display_name)

    def test_visit_compute_display_name_with_date_no_client(self):
        """_compute_display_name includes type and date when no client is linked."""
        record = self.env["spp.case.visit"].new(
            {
                "visit_type": "phone",
                "visit_date": fields.Datetime.now(),
                "conducted_by_id": self.case_worker.id,
                # No case_id, so no client_id
            }
        )
        record._compute_display_name()
        self.assertIn("Phone Call", record.display_name)
        self.assertNotIn(self.client.name, record.display_name)

    def test_visit_compute_display_name_no_date(self):
        """_compute_display_name returns just the type label when visit_date is missing."""
        record = self.env["spp.case.visit"].new(
            {
                "visit_type": "virtual",
                "conducted_by_id": self.case_worker.id,
            }
        )
        # Clear the default that visit_date receives from fields.Datetime.now
        record.visit_date = False
        record._compute_display_name()
        self.assertEqual(record.display_name, "Virtual Meeting")

    def test_visit_create_adds_client_as_attendee(self):
        """create() override adds the case client as a default attendee."""
        visit = self._make_visit()
        self.assertIn(self.client, visit.attendee_ids)

    def test_visit_create_does_not_duplicate_client_attendee(self):
        """create() does not add the client twice when already specified as attendee."""
        visit = self._make_visit(
            attendee_ids=[Command.set([self.client.id])],
        )
        # Client should appear exactly once
        client_in_attendees = visit.attendee_ids.filtered(lambda p: p.id == self.client.id)
        self.assertEqual(len(client_in_attendees), 1)
