# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestGraduationAssessment(TransactionCase):
    """Test graduation assessment management."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Assessment = cls.env["spp.graduation.assessment"]
        cls.Response = cls.env["spp.graduation.criteria.response"]
        cls.Pathway = cls.env["spp.graduation.pathway"]
        cls.Criteria = cls.env["spp.graduation.criteria"]
        cls.Partner = cls.env["res.partner"]

        cls.beneficiary = cls.Partner.create(
            {
                "name": "Test Beneficiary",
                "is_registrant": True,
            }
        )

        cls.pathway = cls.Pathway.create(
            {
                "name": "Test Pathway",
                "code": "TEST",
                "post_graduation_monitoring_months": 12,
            }
        )

        cls.criteria1 = cls.Criteria.create(
            {
                "pathway_id": cls.pathway.id,
                "name": "Economic",
                "weight": 60,
                "is_required": True,
            }
        )
        cls.criteria2 = cls.Criteria.create(
            {
                "pathway_id": cls.pathway.id,
                "name": "Social",
                "weight": 40,
                "is_required": False,
            }
        )

    def test_assessment_creation(self):
        """Test assessment can be created."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        self.assertEqual(assessment.state, "draft")
        self.assertEqual(assessment.readiness_score, 0)

    def test_assessment_name_computation(self):
        """Test assessment name is computed."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        self.assertIn(self.beneficiary.name, assessment.name)
        self.assertIn(self.pathway.name, assessment.name)

    # --- State transition tests ---

    def test_assessment_workflow(self):
        """Test assessment state workflow: draft -> submitted -> approved."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )

        self.assertEqual(assessment.state, "draft")

        assessment.action_submit()
        self.assertEqual(assessment.state, "submitted")

        assessment.action_approve()
        self.assertEqual(assessment.state, "approved")
        self.assertTrue(assessment.approved_by_id)
        self.assertTrue(assessment.approved_date)

    def test_assessment_rejection(self):
        """Test assessment rejection."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )

        assessment.action_submit()
        assessment.action_reject()
        self.assertEqual(assessment.state, "rejected")

    def test_assessment_reset_from_submitted(self):
        """Test assessment reset to draft from submitted."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )

        assessment.action_submit()
        assessment.action_reset_draft()
        self.assertEqual(assessment.state, "draft")

    def test_assessment_reset_from_rejected(self):
        """Test assessment reset to draft from rejected."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )

        assessment.action_submit()
        assessment.action_reject()
        assessment.action_reset_draft()
        self.assertEqual(assessment.state, "draft")

    # --- State transition guard tests ---

    def test_submit_only_from_draft(self):
        """Test submit raises UserError if not in draft state."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        assessment.action_submit()
        # Already submitted, cannot submit again
        with self.assertRaises(UserError):
            assessment.action_submit()

    def test_approve_only_from_submitted(self):
        """Test approve raises UserError if not in submitted state."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        # Cannot approve from draft
        with self.assertRaises(UserError):
            assessment.action_approve()

    def test_reject_only_from_submitted(self):
        """Test reject raises UserError if not in submitted state."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        # Cannot reject from draft
        with self.assertRaises(UserError):
            assessment.action_reject()

    def test_reset_not_from_draft(self):
        """Test reset raises UserError if in draft state."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        with self.assertRaises(UserError):
            assessment.action_reset_draft()

    def test_reset_not_from_approved(self):
        """Test reset raises UserError if in approved state."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        assessment.action_submit()
        assessment.action_approve()
        with self.assertRaises(UserError):
            assessment.action_reset_draft()

    # --- Multi-record action tests ---

    def test_multi_record_submit(self):
        """Test submit works on multiple records."""
        a1 = self.Assessment.create({"partner_id": self.beneficiary.id, "pathway_id": self.pathway.id})
        a2 = self.Assessment.create({"partner_id": self.beneficiary.id, "pathway_id": self.pathway.id})
        (a1 | a2).action_submit()
        self.assertEqual(a1.state, "submitted")
        self.assertEqual(a2.state, "submitted")

    def test_multi_record_approve(self):
        """Test approve works on multiple records."""
        a1 = self.Assessment.create({"partner_id": self.beneficiary.id, "pathway_id": self.pathway.id})
        a2 = self.Assessment.create({"partner_id": self.beneficiary.id, "pathway_id": self.pathway.id})
        (a1 | a2).action_submit()
        (a1 | a2).action_approve()
        self.assertEqual(a1.state, "approved")
        self.assertEqual(a2.state, "approved")

    # --- Score computation tests ---

    def test_readiness_score_computation(self):
        """Test readiness score computation."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )

        self.Response.create(
            {
                "assessment_id": assessment.id,
                "criteria_id": self.criteria1.id,
                "score": 0.8,
                "is_met": True,
            }
        )
        self.Response.create(
            {
                "assessment_id": assessment.id,
                "criteria_id": self.criteria2.id,
                "score": 0.6,
                "is_met": False,
            }
        )

        assessment.invalidate_recordset(["readiness_score", "is_required_criteria_met"])

        # Expected: (0.8 * 60 + 0.6 * 40) / (60 + 40) = 0.72
        expected_score = (0.8 * 60 + 0.6 * 40) / (60 + 40)
        self.assertAlmostEqual(assessment.readiness_score, expected_score, places=1)

    def test_required_criteria_check(self):
        """Test required criteria validation."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )

        self.Response.create(
            {
                "assessment_id": assessment.id,
                "criteria_id": self.criteria1.id,
                "score": 1.0,
                "is_met": True,
            }
        )

        assessment.invalidate_recordset(["is_required_criteria_met"])
        self.assertTrue(assessment.is_required_criteria_met)

    def test_required_criteria_not_met(self):
        """Test required criteria not met."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )

        self.Response.create(
            {
                "assessment_id": assessment.id,
                "criteria_id": self.criteria1.id,
                "score": 0.4,
                "is_met": False,
            }
        )

        assessment.invalidate_recordset(["is_required_criteria_met"])
        self.assertFalse(assessment.is_required_criteria_met)

    def test_no_responses_scores_zero(self):
        """Test assessment with no responses has zero score and required not met."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        self.assertEqual(assessment.readiness_score, 0)
        self.assertFalse(assessment.is_required_criteria_met)

    # --- Score constraint tests ---

    def test_score_constraint_above_one(self):
        """Test score above 1 raises ValidationError."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.Response.create(
                {
                    "assessment_id": assessment.id,
                    "criteria_id": self.criteria1.id,
                    "score": 1.5,
                }
            )

    def test_score_constraint_negative(self):
        """Test negative score raises ValidationError."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.Response.create(
                {
                    "assessment_id": assessment.id,
                    "criteria_id": self.criteria1.id,
                    "score": -0.1,
                }
            )

    def test_score_boundary_values(self):
        """Test score at boundaries (0 and 1) is accepted."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        r1 = self.Response.create(
            {
                "assessment_id": assessment.id,
                "criteria_id": self.criteria1.id,
                "score": 0.0,
            }
        )
        self.assertEqual(r1.score, 0.0)

        r2 = self.Response.create(
            {
                "assessment_id": assessment.id,
                "criteria_id": self.criteria2.id,
                "score": 1.0,
            }
        )
        self.assertEqual(r2.score, 1.0)

    # --- Graduation and monitoring tests ---

    def test_graduation_date_on_approval(self):
        """Test graduation date is set on approval with graduate recommendation."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
                "recommendation": "graduate",
            }
        )

        assessment.action_submit()
        assessment.action_approve()

        self.assertEqual(assessment.graduation_date, fields.Date.today())

    def test_no_graduation_date_without_graduate_recommendation(self):
        """Test graduation date is NOT set when recommendation is not graduate."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
                "recommendation": "extend",
            }
        )

        assessment.action_submit()
        assessment.action_approve()

        self.assertFalse(assessment.graduation_date)

    def test_monitoring_end_date_computation(self):
        """Test monitoring end date is computed from graduation date + pathway months."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
                "recommendation": "graduate",
            }
        )

        assessment.action_submit()
        assessment.action_approve()

        expected_end = date.today() + relativedelta(months=12)
        self.assertEqual(assessment.monitoring_end_date, expected_end)

    def test_monitoring_end_date_no_graduation(self):
        """Test monitoring end date is False when no graduation date."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        self.assertFalse(assessment.monitoring_end_date)

    # --- Name computation edge case ---

    def test_assessment_name_without_pathway(self):
        """Test assessment name defaults when pathway is missing."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        # Remove pathway to trigger else branch
        assessment.pathway_id = False
        self.assertEqual(assessment.name, "New Assessment")

    # --- Response field tests ---

    def test_response_value_and_notes(self):
        """Test response value and notes fields are stored correctly."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )
        response = self.Response.create(
            {
                "assessment_id": assessment.id,
                "criteria_id": self.criteria1.id,
                "score": 0.7,
                "is_met": True,
                "value": "Above threshold",
                "notes": "Verified via documentation",
            }
        )
        self.assertEqual(response.value, "Above threshold")
        self.assertEqual(response.notes, "Verified via documentation")

    def test_recommendation_notes(self):
        """Test recommendation notes field is stored correctly."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
                "recommendation": "graduate",
                "recommendation_notes": "Beneficiary meets all criteria for graduation.",
            }
        )
        self.assertEqual(
            assessment.recommendation_notes,
            "Beneficiary meets all criteria for graduation.",
        )
