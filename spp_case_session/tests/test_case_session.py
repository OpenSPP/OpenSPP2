# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for spp.case session integration (case.py extension)."""

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseSessionIntegration(TransactionCase):
    """Test the spp.case session-related fields and methods."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data."""
        super().setUpClass()

        # Case worker user
        cls.case_worker = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session Test Worker",
                    "login": "session_test_worker",
                    "email": "session_worker@test.com",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                    ],
                }
            )
        )

        # Client partner (the case subject)
        cls.client = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session Test Client",
                    "email": "session_client@test.com",
                }
            )
        )

        # Another partner (used to check attendance filtering)
        cls.other_partner = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Other Partner",
                    "email": "other@test.com",
                }
            )
        )

        # Case type
        cls.case_type = (
            cls.env["spp.case.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Training Case",
                    "code": "TRN001",
                    "domain": "social_protection",
                }
            )
        )

        # Session type (required by spp.session)
        cls.session_type = (
            cls.env["spp.session.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Group Training",
                    "code": "GT001",
                }
            )
        )

        # Case (no sessions linked initially)
        cls.case = (
            cls.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.client.id,
                    "case_worker_id": cls.case_worker.id,
                    "presenting_issue": "<p>Needs training sessions</p>",
                }
            )
        )

        # Sessions
        cls.session1 = (
            cls.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session 1",
                    "session_type_id": cls.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": cls.case_worker.id,
                }
            )
        )

        cls.session2 = (
            cls.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session 2",
                    "session_type_id": cls.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": cls.case_worker.id,
                }
            )
        )

        cls.session3 = (
            cls.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session 3",
                    "session_type_id": cls.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": cls.case_worker.id,
                }
            )
        )

    # -------------------------------------------------------------------------
    # _compute_session_attendance
    # -------------------------------------------------------------------------

    def test_session_attendance_empty_when_no_sessions(self):
        """When no sessions are linked, session_attendance_ids is empty."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>No sessions yet</p>",
                }
            )
        )
        self.assertFalse(
            case.session_attendance_ids,
            "session_attendance_ids should be empty when no sessions are linked",
        )

    def test_session_attendance_empty_when_no_partner(self):
        """When partner_id is not set, session_attendance_ids falls back to empty."""
        # Use .new() so partner_id can be unset
        case_obj = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>No partner</p>",
                "session_ids": [Command.link(self.session1.id)],
            }
        )
        case_obj._compute_session_attendance()
        self.assertFalse(
            case_obj.session_attendance_ids,
            "session_attendance_ids must be empty when partner_id is not set",
        )

    def test_session_attendance_returns_matching_records(self):
        """Attendance records for the case client in linked sessions are returned."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Attended sessions</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                    ],
                }
            )
        )

        # Create attendance record for the case client in session1
        att1 = (
            self.env["spp.session.attendance"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "session_id": self.session1.id,
                    "participant_id": self.client.id,
                    "is_attended": True,
                }
            )
        )

        # Create attendance for another partner (should NOT appear)
        self.env["spp.session.attendance"].with_context(tracking_disable=True).create(
            {
                "session_id": self.session1.id,
                "participant_id": self.other_partner.id,
                "is_attended": True,
            }
        )

        case._compute_session_attendance()

        self.assertIn(
            att1,
            case.session_attendance_ids,
            "Attendance for the case client should be included",
        )
        self.assertEqual(
            len(case.session_attendance_ids),
            1,
            "Only attendance for the case client should be returned",
        )

    def test_session_attendance_filters_by_linked_sessions_only(self):
        """Attendance in sessions not linked to this case is excluded."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Filtered sessions</p>",
                    "session_ids": [Command.link(self.session1.id)],
                }
            )
        )

        # Attendance in the linked session
        att_linked = (
            self.env["spp.session.attendance"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "session_id": self.session1.id,
                    "participant_id": self.client.id,
                    "is_attended": True,
                }
            )
        )

        # Attendance in an unlinked session (session2 not in case)
        self.env["spp.session.attendance"].with_context(tracking_disable=True).create(
            {
                "session_id": self.session2.id,
                "participant_id": self.client.id,
                "is_attended": True,
            }
        )

        case._compute_session_attendance()

        self.assertIn(att_linked, case.session_attendance_ids)
        self.assertEqual(
            len(case.session_attendance_ids),
            1,
            "Only attendance records from linked sessions should be returned",
        )

    # -------------------------------------------------------------------------
    # _compute_session_stats — no sessions branch
    # -------------------------------------------------------------------------

    def test_session_stats_no_sessions(self):
        """When no sessions are linked, stats default to zero / not_applicable."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>No sessions</p>",
                }
            )
        )
        case._compute_session_stats()

        self.assertEqual(case.session_count, 0, "session_count should be 0 with no sessions")
        self.assertAlmostEqual(
            case.session_attendance_rate,
            0.0,
            places=2,
            msg="session_attendance_rate should be 0.0 with no sessions",
        )
        self.assertEqual(
            case.session_compliance,
            "not_applicable",
            "session_compliance should be 'not_applicable' with no sessions",
        )

    # -------------------------------------------------------------------------
    # _compute_session_stats — compliant branch (rate >= 80)
    # -------------------------------------------------------------------------

    def test_session_stats_compliant(self):
        """Attendance >= 80% yields 'compliant' status."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Compliant client</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                        Command.link(self.session3.id),
                    ],
                }
            )
        )

        # Attend all 3 out of 3 → 100% → compliant
        for session in [self.session1, self.session2, self.session3]:
            self.env["spp.session.attendance"].with_context(tracking_disable=True).create(
                {
                    "session_id": session.id,
                    "participant_id": self.client.id,
                    "is_attended": True,
                }
            )

        case._compute_session_stats()

        self.assertEqual(case.session_count, 3)
        self.assertAlmostEqual(case.session_attendance_rate, 100.0, places=2)
        self.assertEqual(case.session_compliance, "compliant")

    def test_session_stats_compliant_at_boundary(self):
        """Exactly 80% attendance gives 'compliant'."""
        # 4 sessions, attend 4 → need 80% exactly from 5 sessions
        session4 = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session 4",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.case_worker.id,
                }
            )
        )
        session5 = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session 5",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.case_worker.id,
                }
            )
        )

        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Boundary client</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                        Command.link(self.session3.id),
                        Command.link(session4.id),
                        Command.link(session5.id),
                    ],
                }
            )
        )

        # Attend 4 out of 5 → 80% exactly
        for session in [self.session1, self.session2, self.session3, session4]:
            self.env["spp.session.attendance"].with_context(tracking_disable=True).create(
                {
                    "session_id": session.id,
                    "participant_id": self.client.id,
                    "is_attended": True,
                }
            )

        case._compute_session_stats()

        self.assertAlmostEqual(case.session_attendance_rate, 80.0, places=2)
        self.assertEqual(case.session_compliance, "compliant")

    # -------------------------------------------------------------------------
    # _compute_session_stats — partial branch (50 <= rate < 80)
    # -------------------------------------------------------------------------

    def test_session_stats_partial(self):
        """50-79% attendance yields 'partial' compliance."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Partial client</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                    ],
                }
            )
        )

        # Attend 1 out of 2 → 50% → partial
        self.env["spp.session.attendance"].with_context(tracking_disable=True).create(
            {
                "session_id": self.session1.id,
                "participant_id": self.client.id,
                "is_attended": True,
            }
        )

        case._compute_session_stats()

        self.assertAlmostEqual(case.session_attendance_rate, 50.0, places=2)
        self.assertEqual(case.session_compliance, "partial")

    def test_session_stats_partial_at_boundary(self):
        """Exactly 50% attendance gives 'partial'."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Partial boundary client</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                        Command.link(self.session3.id),
                        Command.link(
                            self.env["spp.session"]
                            .with_context(tracking_disable=True)
                            .create(
                                {
                                    "name": "Session Extra",
                                    "session_type_id": self.session_type.id,
                                    "date": fields.Date.today(),
                                    "facilitator_id": self.case_worker.id,
                                }
                            )
                            .id
                        ),
                    ],
                }
            )
        )

        # Attend exactly 2 out of 4 = 50%
        for session in [self.session1, self.session2]:
            self.env["spp.session.attendance"].with_context(tracking_disable=True).create(
                {
                    "session_id": session.id,
                    "participant_id": self.client.id,
                    "is_attended": True,
                }
            )

        case._compute_session_stats()

        self.assertAlmostEqual(case.session_attendance_rate, 50.0, places=2)
        self.assertEqual(case.session_compliance, "partial")

    # -------------------------------------------------------------------------
    # _compute_session_stats — non_compliant branch (rate < 50)
    # -------------------------------------------------------------------------

    def test_session_stats_non_compliant(self):
        """Below 50% attendance yields 'non_compliant' status."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Non-compliant client</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                        Command.link(self.session3.id),
                    ],
                }
            )
        )

        # Attend 0 out of 3 → 0% → non_compliant
        case._compute_session_stats()

        self.assertAlmostEqual(case.session_attendance_rate, 0.0, places=2)
        self.assertEqual(case.session_compliance, "non_compliant")

    def test_session_stats_non_compliant_one_of_three(self):
        """33% attendance yields 'non_compliant'."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>One-third attendance</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                        Command.link(self.session3.id),
                    ],
                }
            )
        )

        # Attend 1 out of 3 → ~33% → non_compliant
        self.env["spp.session.attendance"].with_context(tracking_disable=True).create(
            {
                "session_id": self.session1.id,
                "participant_id": self.client.id,
                "is_attended": True,
            }
        )

        case._compute_session_stats()

        self.assertAlmostEqual(
            case.session_attendance_rate,
            33.33,
            places=1,
        )
        self.assertEqual(case.session_compliance, "non_compliant")

    def test_session_stats_unattended_records_not_counted(self):
        """Attendance records with is_attended=False do not count towards rate."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Absent client</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                    ],
                }
            )
        )

        # Create attendance records marked as NOT attended
        self.env["spp.session.attendance"].with_context(tracking_disable=True).create(
            {
                "session_id": self.session1.id,
                "participant_id": self.client.id,
                "is_attended": False,
            }
        )
        self.env["spp.session.attendance"].with_context(tracking_disable=True).create(
            {
                "session_id": self.session2.id,
                "participant_id": self.client.id,
                "is_attended": False,
            }
        )

        case._compute_session_stats()

        self.assertAlmostEqual(case.session_attendance_rate, 0.0, places=2)
        self.assertEqual(case.session_compliance, "non_compliant")

    def test_session_count_matches_linked_sessions(self):
        """session_count reflects the number of sessions linked to the case."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Count test</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                    ],
                }
            )
        )

        case._compute_session_stats()

        self.assertEqual(case.session_count, 2)

    # -------------------------------------------------------------------------
    # action_view_sessions
    # -------------------------------------------------------------------------

    def test_action_view_sessions_returns_correct_structure(self):
        """action_view_sessions returns a valid act_window action dict."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Action test</p>",
                    "session_ids": [Command.link(self.session1.id)],
                }
            )
        )

        action = case.action_view_sessions()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.session")
        self.assertIn("list", action["view_mode"])
        self.assertIn("form", action["view_mode"])

    def test_action_view_sessions_domain_contains_session_ids(self):
        """The action domain restricts to sessions linked to this case."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Domain test</p>",
                    "session_ids": [
                        Command.link(self.session1.id),
                        Command.link(self.session2.id),
                    ],
                }
            )
        )

        action = case.action_view_sessions()

        domain = action.get("domain", [])
        # The domain should filter on ("id", "in", [session1.id, session2.id])
        self.assertTrue(
            any(
                len(clause) == 3
                and clause[0] == "id"
                and clause[1] == "in"
                and set(clause[2]) == {self.session1.id, self.session2.id}
                for clause in domain
            ),
            "Domain should filter sessions by linked IDs",
        )

    def test_action_view_sessions_context_defaults(self):
        """The action context sets default_case_ids and default_expected_participant_ids."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Context test</p>",
                    "session_ids": [Command.link(self.session1.id)],
                }
            )
        )

        action = case.action_view_sessions()
        ctx = action.get("context", {})

        self.assertIn("default_case_ids", ctx)
        self.assertIn("default_expected_participant_ids", ctx)

    def test_action_view_sessions_name(self):
        """The action name is set to 'Case Sessions'."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Name test</p>",
                }
            )
        )

        action = case.action_view_sessions()

        self.assertEqual(action["name"], "Case Sessions")
