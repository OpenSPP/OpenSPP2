# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields
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
            }
        )

        cls.pathway = cls.Pathway.create(
            {
                "name": "Test Pathway",
                "code": "TEST",
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

    def test_assessment_workflow(self):
        """Test assessment state workflow."""
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

    def test_assessment_reset(self):
        """Test assessment reset to draft."""
        assessment = self.Assessment.create(
            {
                "partner_id": self.beneficiary.id,
                "pathway_id": self.pathway.id,
            }
        )

        assessment.action_submit()
        assessment.action_reset_draft()
        self.assertEqual(assessment.state, "draft")

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
                "score": 0.8,  # 80%
                "is_met": True,
            }
        )
        self.Response.create(
            {
                "assessment_id": assessment.id,
                "criteria_id": self.criteria2.id,
                "score": 0.6,  # 60%
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

        # Only required criterion met
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
                "is_met": False,  # Required but not met
            }
        )

        assessment.invalidate_recordset(["is_required_criteria_met"])
        self.assertFalse(assessment.is_required_criteria_met)

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
