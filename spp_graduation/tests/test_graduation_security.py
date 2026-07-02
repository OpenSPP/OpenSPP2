"""Security tests for graduation module."""

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGraduationSecurity(TransactionCase):
    """Test access control for graduation records."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create(
            {
                "name": "Graduation User",
                "login": "test_graduation_user",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_graduation.group_spp_graduation_user").id),
                ],
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Graduation Manager",
                "login": "test_graduation_manager",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_graduation.group_spp_graduation_manager").id),
                ],
            }
        )
        # Create test beneficiary for assessments
        cls.beneficiary = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary",
                "is_registrant": True,
            }
        )

    def test_group_hierarchy_manager_has_user(self):
        """Test manager inherits user permissions."""
        self.assertTrue(
            self.manager.has_group("spp_graduation.group_spp_graduation_user"), "Manager should have user permissions"
        )

    def test_admin_has_manager(self):
        """Test OpenSPP admin has graduation manager access."""
        admin = self.env["res.users"].create(
            {
                "name": "Admin Test",
                "login": "test_admin_graduation",
                "group_ids": [
                    Command.link(self.env.ref("spp_security.group_spp_admin").id),
                ],
            }
        )
        self.assertTrue(
            admin.has_group("spp_graduation.group_spp_graduation_manager"),
            "Admin should have graduation manager access",
        )

    def test_user_sees_own_assessments(self):
        """Test user sees own assessments."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        assessment = self.env["spp.graduation.assessment"].create(
            {
                "pathway_id": pathway.id,
                "partner_id": self.beneficiary.id,
                "assessor_id": self.user.id,
            }
        )
        assessments_as_user = self.env["spp.graduation.assessment"].with_user(self.user).search([])
        self.assertIn(assessment, assessments_as_user, "User should see own assessments")

    def test_manager_sees_all_assessments(self):
        """Test manager sees all assessments."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        assessment1 = self.env["spp.graduation.assessment"].create(
            {
                "pathway_id": pathway.id,
                "partner_id": self.beneficiary.id,
                "assessor_id": self.user.id,
            }
        )
        assessment2 = self.env["spp.graduation.assessment"].create(
            {
                "pathway_id": pathway.id,
                "partner_id": self.beneficiary.id,
                "assessor_id": self.manager.id,
            }
        )
        assessments_as_manager = self.env["spp.graduation.assessment"].with_user(self.manager).search([])
        self.assertIn(assessment1, assessments_as_manager, "Manager should see all assessments")
        self.assertIn(assessment2, assessments_as_manager, "Manager should see all assessments")

    def test_user_can_read_pathways(self):
        """Test user can read pathways."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        pathway_as_user = pathway.with_user(self.user)
        self.assertEqual(pathway_as_user.name, "Test Pathway")

    def test_user_cannot_write_pathways(self):
        """Test user cannot write pathways."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        with self.assertRaises(AccessError):
            pathway.with_user(self.user).write({"name": "Modified"})

    def test_manager_can_write_pathways(self):
        """Test manager can write pathways."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        pathway.with_user(self.manager).write({"name": "Modified by Manager"})
        self.assertEqual(pathway.name, "Modified by Manager")

    def test_user_workflow_as_user(self):
        """Test user can submit own assessments."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_user(self.user)
            .create(
                {
                    "pathway_id": pathway.id,
                    "partner_id": self.beneficiary.id,
                }
            )
        )
        assessment.action_submit()
        self.assertEqual(assessment.state, "submitted")

    def test_manager_can_approve(self):
        """Test manager can approve submitted assessments."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        assessment = self.env["spp.graduation.assessment"].create(
            {
                "pathway_id": pathway.id,
                "partner_id": self.beneficiary.id,
                "assessor_id": self.user.id,
            }
        )
        assessment.action_submit()
        assessment.with_user(self.manager).action_approve()
        self.assertEqual(assessment.state, "approved")
        self.assertEqual(assessment.approved_by_id, self.manager)

    def test_manager_can_reject(self):
        """Test manager can reject submitted assessments."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        assessment = self.env["spp.graduation.assessment"].create(
            {
                "pathway_id": pathway.id,
                "partner_id": self.beneficiary.id,
                "assessor_id": self.user.id,
            }
        )
        assessment.action_submit()
        assessment.with_user(self.manager).action_reject()
        self.assertEqual(assessment.state, "rejected")

    # ──────────────────────────────────────────────────────────────────────────
    # Approval boundary — a graduation USER must not approve (or otherwise drive
    # the approval workflow of) their own assessment, via the action methods OR
    # via direct RPC write/create of the workflow fields.
    # ──────────────────────────────────────────────────────────────────────────

    def _submitted_assessment_owned_by_user(self):
        pathway = self.env["spp.graduation.pathway"].create({"name": "Test Pathway"})
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_user(self.user)
            .create(
                {
                    "pathway_id": pathway.id,
                    "partner_id": self.beneficiary.id,
                    "recommendation": "graduate",
                }
            )
        )
        assessment.action_submit()
        self.assertEqual(assessment.state, "submitted")
        return assessment

    def test_user_cannot_approve_own_assessment(self):
        """Reported self-approval: a user must not approve their own assessment."""
        assessment = self._submitted_assessment_owned_by_user()
        with self.assertRaises(AccessError):
            assessment.action_approve()
        self.assertEqual(assessment.state, "submitted")
        self.assertFalse(assessment.graduation_date)

    def test_user_cannot_reject_or_reset_own_assessment(self):
        assessment = self._submitted_assessment_owned_by_user()
        with self.assertRaises(AccessError):
            assessment.action_reject()
        with self.assertRaises(AccessError):
            assessment.action_reset_draft()
        self.assertEqual(assessment.state, "submitted")

    def test_user_cannot_write_approved_state_directly(self):
        """Raw-RPC bypass of the action methods must also be blocked."""
        assessment = self._submitted_assessment_owned_by_user()
        with self.assertRaises(AccessError):
            assessment.write({"state": "approved"})
        self.assertEqual(assessment.state, "submitted")

    def test_user_cannot_write_approval_fields_directly(self):
        assessment = self._submitted_assessment_owned_by_user()
        with self.assertRaises(AccessError):
            assessment.write({"graduation_date": fields.Date.today()})
        with self.assertRaises(AccessError):
            assessment.write({"approved_by_id": self.user.id})

    def test_user_cannot_create_non_draft_assessment(self):
        """Creating an already-approved assessment via RPC must be blocked."""
        pathway = self.env["spp.graduation.pathway"].create({"name": "Test Pathway"})
        with self.assertRaises(AccessError):
            self.env["spp.graduation.assessment"].with_user(self.user).create(
                {
                    "pathway_id": pathway.id,
                    "partner_id": self.beneficiary.id,
                    "state": "approved",
                    "graduation_date": fields.Date.today(),
                }
            )

    def test_manager_approve_sets_graduation_date(self):
        """Regression: a manager can still approve, and graduation_date is set for
        a 'graduate' recommendation."""
        assessment = self._submitted_assessment_owned_by_user()
        assessment.with_user(self.manager).action_approve()
        self.assertEqual(assessment.state, "approved")
        self.assertEqual(assessment.approved_by_id, self.manager)
        self.assertTrue(assessment.graduation_date)

    def test_user_can_edit_own_draft_content(self):
        """The guard must not over-block: a user can still edit non-workflow
        content on their own draft assessment."""
        pathway = self.env["spp.graduation.pathway"].create({"name": "Test Pathway"})
        assessment = (
            self.env["spp.graduation.assessment"]
            .with_user(self.user)
            .create({"pathway_id": pathway.id, "partner_id": self.beneficiary.id})
        )
        assessment.write({"recommendation": "graduate", "recommendation_notes": "ready"})
        self.assertEqual(assessment.recommendation, "graduate")

    def test_user_cannot_modify_submitted_assessment_content(self):
        """A user must not change assessment content once it is submitted — else
        they could flip the recommendation the manager is about to approve."""
        assessment = self._submitted_assessment_owned_by_user()
        with self.assertRaises(AccessError):
            assessment.write({"recommendation": "extend"})
        with self.assertRaises(AccessError):
            assessment.write({"recommendation_notes": "changed after submit"})
        self.assertEqual(assessment.recommendation, "graduate")

    def test_user_cannot_unsubmit_own_assessment(self):
        """A user may only move draft -> submitted; un-submitting is manager-only."""
        assessment = self._submitted_assessment_owned_by_user()
        with self.assertRaises(AccessError):
            assessment.write({"state": "draft"})
        self.assertEqual(assessment.state, "submitted")

    def test_user_cannot_create_assessment_for_another_assessor(self):
        """A user cannot create an assessment attributed to a different assessor
        (record-rule protection; documents the boundary)."""
        pathway = self.env["spp.graduation.pathway"].create({"name": "Test Pathway"})
        with self.assertRaises(AccessError):
            self.env["spp.graduation.assessment"].with_user(self.user).create(
                {
                    "pathway_id": pathway.id,
                    "partner_id": self.beneficiary.id,
                    "assessor_id": self.manager.id,
                }
            )
