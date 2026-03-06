# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for spp_case_graduation GraduationAssessment extension.

Covers the GraduationAssessment model extension that adds a case_id
Many2one field linking assessments back to cases.
"""

from datetime import date

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGraduationAssessmentExtension(TransactionCase):
    """Test the spp.graduation.assessment case_id extension."""

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
                    "name": "Ext Test Worker",
                    "login": "ext_test_worker",
                    "email": "ext_worker@test.com",
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
                    "name": "Ext Test Client",
                    "email": "ext_client@test.com",
                }
            )
        )

        # Create a case type
        cls.case_type = (
            cls.env["spp.case.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Extension Test Case Type",
                    "code": "EXT001",
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
                    "name": "Extension Test Pathway",
                    "code": "ETP001",
                    "post_graduation_monitoring_months": 3,
                }
            )
        )

        # Create a case to link assessments to
        cls.case = (
            cls.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.client.id,
                    "case_worker_id": cls.case_worker.id,
                    "presenting_issue": "<p>Assessment extension test case.</p>",
                }
            )
        )

    # ------------------------------------------------------------------
    # case_id field presence and linkage
    # ------------------------------------------------------------------

    def test_assessment_has_case_id_field(self):
        """spp.graduation.assessment should expose a case_id field after module install."""
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                }
            )
        )
        # The field must exist; accessing it should not raise
        self.assertFalse(assessment.case_id, "Newly created assessment without case should have no case_id")

    def test_assessment_linked_to_case(self):
        """Creating an assessment with case_id should link it to the correct case."""
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                    "case_id": self.case.id,
                }
            )
        )
        self.assertEqual(assessment.case_id, self.case)

    def test_assessment_case_id_writable(self):
        """case_id should be writable so it can be updated after creation."""
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                }
            )
        )
        self.assertFalse(assessment.case_id)

        assessment.write({"case_id": self.case.id})
        self.assertEqual(assessment.case_id, self.case)

    def test_assessment_case_id_clearable(self):
        """case_id should be clearable (set to False) after being set."""
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                    "case_id": self.case.id,
                }
            )
        )
        self.assertEqual(assessment.case_id, self.case)

        assessment.write({"case_id": False})
        self.assertFalse(assessment.case_id)

    # ------------------------------------------------------------------
    # Inverse relation: case.graduation_assessment_ids
    # ------------------------------------------------------------------

    def test_case_sees_linked_assessments(self):
        """Assessments linked via case_id should appear in
        case.graduation_assessment_ids."""
        assessment1 = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                    "case_id": self.case.id,
                }
            )
        )
        assessment2 = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                    "case_id": self.case.id,
                }
            )
        )

        self.assertIn(assessment1, self.case.graduation_assessment_ids)
        self.assertIn(assessment2, self.case.graduation_assessment_ids)

    def test_unlinked_assessment_not_in_case(self):
        """An assessment without a case_id should not appear in any case's
        graduation_assessment_ids."""
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                }
            )
        )
        self.assertNotIn(assessment, self.case.graduation_assessment_ids)

    # ------------------------------------------------------------------
    # Multiple cases — assessments are scoped correctly
    # ------------------------------------------------------------------

    def test_assessments_scoped_to_correct_case(self):
        """Assessments linked to different cases should not appear in each
        other's graduation_assessment_ids."""
        other_case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Second case for scoping test.</p>",
                }
            )
        )

        assessment_for_case = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                    "case_id": self.case.id,
                }
            )
        )
        assessment_for_other = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                    "case_id": other_case.id,
                }
            )
        )

        self.assertIn(assessment_for_case, self.case.graduation_assessment_ids)
        self.assertNotIn(assessment_for_other, self.case.graduation_assessment_ids)
        self.assertIn(assessment_for_other, other_case.graduation_assessment_ids)
        self.assertNotIn(assessment_for_case, other_case.graduation_assessment_ids)

    # ------------------------------------------------------------------
    # Workflow: case_id survives state transitions on the assessment
    # ------------------------------------------------------------------

    def test_case_id_preserved_through_workflow(self):
        """The case_id link should be preserved as the assessment moves
        through its draft -> submitted -> approved workflow."""
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.client.id,
                    "pathway_id": self.pathway.id,
                    "assessment_date": date.today(),
                    "case_id": self.case.id,
                    "state": "draft",
                }
            )
        )

        assessment.action_submit()
        self.assertEqual(assessment.case_id, self.case, "case_id should survive submit")

        assessment.action_approve()
        self.assertEqual(assessment.case_id, self.case, "case_id should survive approve")
