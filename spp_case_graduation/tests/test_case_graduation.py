# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for spp_case_graduation Case extension.

Covers the Case model extension that adds graduation tracking fields and
computed graduation statistics derived from linked assessments.
"""

from datetime import date

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseGraduation(TransactionCase):
    """Test the spp.case graduation extension fields and methods."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data for all test methods."""
        super().setUpClass()

        # Create a case worker user
        cls.case_worker = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Graduation Test Worker",
                    "login": "grad_test_worker",
                    "email": "grad_worker@test.com",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                    ],
                }
            )
        )

        # Create a client partner
        cls.client = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Graduation Test Client",
                    "email": "grad_client@test.com",
                }
            )
        )

        # Create a case type
        cls.case_type = (
            cls.env["spp.case.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Graduation Test Case Type",
                    "code": "GRAD001",
                    "domain": "social_protection",
                }
            )
        )

        # Create a graduation pathway
        cls.pathway = (
            cls.env["spp.graduation.pathway"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Graduation Pathway",
                    "code": "TGP001",
                    "post_graduation_monitoring_months": 6,
                }
            )
        )

        # Create the case that will be used in most tests
        cls.case = (
            cls.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.client.id,
                    "case_worker_id": cls.case_worker.id,
                    "presenting_issue": "<p>Client needs graduation assessment.</p>",
                }
            )
        )

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_assessment(self, **kwargs):
        """Create a graduation assessment linked to cls.case with sensible defaults."""
        defaults = {
            "partner_id": self.client.id,
            "pathway_id": self.pathway.id,
            "case_id": self.case.id,
            "assessment_date": date.today(),
        }
        defaults.update(kwargs)
        return self.env["spp.graduation.assessment"].with_context(tracking_disable=True).create(defaults)

    # ------------------------------------------------------------------
    # No assessments — default computed values
    # ------------------------------------------------------------------

    def test_graduation_stats_no_assessments(self):
        """A case with no assessments should have sensible zero/False defaults."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>No assessments yet.</p>",
                }
            )
        )
        case._compute_graduation_stats()

        self.assertEqual(case.graduation_assessment_count, 0)
        self.assertFalse(case.latest_graduation_assessment_id)
        self.assertEqual(case.graduation_readiness, 0.0)
        self.assertEqual(case.graduation_status, "not_assessed")

    # ------------------------------------------------------------------
    # Status: in_progress (draft assessment)
    # ------------------------------------------------------------------

    def test_graduation_status_in_progress(self):
        """Draft assessment should produce in_progress graduation status."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>In progress case.</p>",
                }
            )
        )
        self.env["spp.graduation.assessment"].with_context(tracking_disable=True).create(
            {
                "partner_id": self.client.id,
                "pathway_id": self.pathway.id,
                "case_id": case.id,
                "assessment_date": date.today(),
                "state": "draft",
            }
        )
        case._compute_graduation_stats()

        self.assertEqual(case.graduation_status, "in_progress")
        self.assertEqual(case.graduation_assessment_count, 1)

    # ------------------------------------------------------------------
    # Status: pending_approval (submitted assessment)
    # ------------------------------------------------------------------

    def test_graduation_status_pending_approval(self):
        """Submitted assessment should produce pending_approval status."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Pending approval case.</p>",
                }
            )
        )
        self.env["spp.graduation.assessment"].with_context(tracking_disable=True).create(
            {
                "partner_id": self.client.id,
                "pathway_id": self.pathway.id,
                "case_id": case.id,
                "assessment_date": date.today(),
                "state": "submitted",
            }
        )
        case._compute_graduation_stats()

        self.assertEqual(case.graduation_status, "pending_approval")

    # ------------------------------------------------------------------
    # Status: approved (approved + graduate recommendation, no graduation date)
    # ------------------------------------------------------------------

    def test_graduation_status_approved(self):
        """Approved assessment with graduate recommendation and no graduation date
        should produce approved status."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Approved for graduation.</p>",
                }
            )
        )
        self.env["spp.graduation.assessment"].with_context(tracking_disable=True).create(
            {
                "partner_id": self.client.id,
                "pathway_id": self.pathway.id,
                "case_id": case.id,
                "assessment_date": date.today(),
                "state": "approved",
                "recommendation": "graduate",
                # graduation_date intentionally left False
            }
        )
        case._compute_graduation_stats()

        self.assertEqual(case.graduation_status, "approved")

    # ------------------------------------------------------------------
    # Status: graduated (approved + graduate + graduation_date set)
    # ------------------------------------------------------------------

    def test_graduation_status_graduated(self):
        """Approved assessment with graduate recommendation and a graduation date
        should produce graduated status."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Already graduated.</p>",
                }
            )
        )
        self.env["spp.graduation.assessment"].with_context(tracking_disable=True).create(
            {
                "partner_id": self.client.id,
                "pathway_id": self.pathway.id,
                "case_id": case.id,
                "assessment_date": date.today(),
                "state": "approved",
                "recommendation": "graduate",
                "graduation_date": date.today(),
            }
        )
        case._compute_graduation_stats()

        self.assertEqual(case.graduation_status, "graduated")

    # ------------------------------------------------------------------
    # Status: deferred (defer recommendation)
    # ------------------------------------------------------------------

    def test_graduation_status_deferred(self):
        """Assessment with defer recommendation should produce deferred status."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Deferred case.</p>",
                }
            )
        )
        self.env["spp.graduation.assessment"].with_context(tracking_disable=True).create(
            {
                "partner_id": self.client.id,
                "pathway_id": self.pathway.id,
                "case_id": case.id,
                "assessment_date": date.today(),
                "state": "rejected",
                "recommendation": "defer",
            }
        )
        case._compute_graduation_stats()

        self.assertEqual(case.graduation_status, "deferred")

    # ------------------------------------------------------------------
    # Status: not_assessed (approved but non-graduate/defer recommendation)
    # ------------------------------------------------------------------

    def test_graduation_status_not_assessed_fallback(self):
        """An approved assessment with an extend recommendation falls back
        to not_assessed because none of the explicit branches match."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Fallback status case.</p>",
                }
            )
        )
        self.env["spp.graduation.assessment"].with_context(tracking_disable=True).create(
            {
                "partner_id": self.client.id,
                "pathway_id": self.pathway.id,
                "case_id": case.id,
                "assessment_date": date.today(),
                "state": "approved",
                "recommendation": "extend",
            }
        )
        case._compute_graduation_stats()

        self.assertEqual(case.graduation_status, "not_assessed")

    # ------------------------------------------------------------------
    # Latest assessment selection (most recent by date)
    # ------------------------------------------------------------------

    def test_latest_assessment_is_most_recent(self):
        """latest_graduation_assessment_id should be the assessment with the
        latest assessment_date."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Multiple assessment case.</p>",
                }
            )
        )

        self.env["spp.graduation.assessment"].with_context(tracking_disable=True).create(
            {
                "partner_id": self.client.id,
                "pathway_id": self.pathway.id,
                "case_id": case.id,
                "assessment_date": date(2024, 1, 1),
                "state": "draft",
            }
        )
        newer = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "case_id": case.id,
                    "assessment_date": date(2024, 6, 1),
                    "state": "submitted",
                }
            )
        )

        case._compute_graduation_stats()

        self.assertEqual(case.graduation_assessment_count, 2)
        self.assertEqual(case.latest_graduation_assessment_id, newer)
        # The readiness score comes from the latest (newer) assessment
        self.assertEqual(case.graduation_readiness, newer.readiness_score)

    # ------------------------------------------------------------------
    # Readiness score reflects latest assessment
    # ------------------------------------------------------------------

    def test_graduation_readiness_score_from_latest(self):
        """graduation_readiness should reflect the readiness_score of the
        latest linked assessment."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Readiness score case.</p>",
                }
            )
        )
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "case_id": case.id,
                    "assessment_date": date.today(),
                    "state": "submitted",
                }
            )
        )

        case._compute_graduation_stats()

        self.assertEqual(case.graduation_readiness, assessment.readiness_score)

    # ------------------------------------------------------------------
    # action_view_graduation_assessments
    # ------------------------------------------------------------------

    def test_action_view_graduation_assessments(self):
        """action_view_graduation_assessments should return a window action
        filtered to this case."""
        action = self.case.action_view_graduation_assessments()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.graduation.assessment")
        self.assertIn("list", action["view_mode"])
        self.assertIn("form", action["view_mode"])
        self.assertEqual(action["domain"], [("case_id", "=", self.case.id)])
        self.assertEqual(action["context"]["default_case_id"], self.case.id)
        self.assertEqual(action["context"]["default_partner_id"], self.client.id)

    def test_action_view_graduation_assessments_name(self):
        """The window action title should be 'Graduation Assessments'."""
        action = self.case.action_view_graduation_assessments()
        self.assertEqual(action["name"], "Graduation Assessments")

    # ------------------------------------------------------------------
    # action_create_graduation_assessment
    # ------------------------------------------------------------------

    def test_action_create_graduation_assessment(self):
        """action_create_graduation_assessment should return a form window
        action targeting a new assessment with context pre-filled."""
        action = self.case.action_create_graduation_assessment()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.graduation.assessment")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_case_id"], self.case.id)
        self.assertEqual(action["context"]["default_partner_id"], self.client.id)

    def test_action_create_graduation_assessment_name(self):
        """The window action title should be 'New Graduation Assessment'."""
        action = self.case.action_create_graduation_assessment()
        self.assertEqual(action["name"], "New Graduation Assessment")

    # ------------------------------------------------------------------
    # Computed stats across multiple cases (batch compute)
    # ------------------------------------------------------------------

    def test_compute_graduation_stats_multiple_cases(self):
        """_compute_graduation_stats should work correctly when called on a
        multi-record recordset."""
        case1 = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Multi-compute case 1.</p>",
                }
            )
        )
        case2 = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Multi-compute case 2.</p>",
                }
            )
        )

        self.env["spp.graduation.assessment"].with_context(tracking_disable=True).create(
            {
                "partner_id": self.client.id,
                "pathway_id": self.pathway.id,
                "case_id": case1.id,
                "assessment_date": date.today(),
                "state": "approved",
                "recommendation": "graduate",
                "graduation_date": date.today(),
            }
        )

        # Trigger compute on a batch recordset
        both = case1 | case2
        both._compute_graduation_stats()

        self.assertEqual(case1.graduation_status, "graduated")
        self.assertEqual(case2.graduation_status, "not_assessed")
        self.assertEqual(case1.graduation_assessment_count, 1)
        self.assertEqual(case2.graduation_assessment_count, 0)
