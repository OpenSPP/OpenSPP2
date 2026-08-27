# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#1173: three roles, and an Approver that can actually approve.

The module used to ship four roles. Assessor and Validator carried identical
ACLs on every model, so Validator drew a distinction the system did not make.
Worse, approving was not governed by any of them: the Approve button has no
``groups`` attribute, ``can_approve`` comes from the approval definition, and
nothing shipped a definition -- so on a fresh database no assessment could be
submitted, and the role named "Validator" granted no approval power at all.
"""

from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

# Everything _check_can_submit gates on for an adult (WG-SS, no proxy): all six
# questionnaire domains answered, the impairment question answered, and a review
# category chosen. Anything less and the submit is refused before approval
# permissions are ever computed.
SUBMITTABLE = {
    "wg_seeing": "cannot",
    "wg_hearing": "none",
    "wg_walking": "none",
    "wg_remembering": "none",
    "wg_selfcare": "none",
    "wg_communicating": "none",
    "has_impairments_to_record": "no",
    "review_category": "mine",
}


@tagged("post_install", "-at_install")
class TestDisabilityRoles(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Role Test Registrant",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date(1990, 1, 1),
            }
        )

    def _user(self, login, group_xmlid):
        """An internal user holding one disability role.

        base.group_user is deliberate: passing group_ids to create() replaces
        the default rather than adding to it, and a user with only a disability
        group is not an internal user at all. Approving reaches
        activity_feedback, which searches mail.activity, so a fixture missing
        the base group fails on an access error that no real holder of the role
        would ever see.
        """
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@test.com",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.env.ref(group_xmlid).id),
                ],
            }
        )

    # === the role set itself ===

    def test_only_three_roles_exist(self):
        """Viewer, Assessor, Approver -- and nothing else in the category."""
        for xmlid in (
            "spp_disability_registry.group_disability_viewer",
            "spp_disability_registry.group_disability_assessor",
            "spp_disability_registry.group_disability_approver",
        ):
            self.assertTrue(self.env.ref(xmlid), f"{xmlid} should exist")

        for xmlid in (
            "spp_disability_registry.group_disability_validator",
            "spp_disability_registry.group_disability_manager",
        ):
            self.assertFalse(
                self.env.ref(xmlid, raise_if_not_found=False),
                f"{xmlid} was consolidated away and should no longer resolve",
            )

    def test_the_roles_stack(self):
        """Approver includes Assessor includes Viewer, as the ticket's table says."""
        viewer = self.env.ref("spp_disability_registry.group_disability_viewer")
        assessor = self.env.ref("spp_disability_registry.group_disability_assessor")
        approver = self.env.ref("spp_disability_registry.group_disability_approver")

        self.assertIn(viewer, assessor.all_implied_ids)
        self.assertIn(assessor, approver.all_implied_ids)
        self.assertIn(viewer, approver.all_implied_ids)

    def test_assessor_and_approver_are_not_the_same_role(self):
        """The old Validator was removed precisely because it was a duplicate.

        Whatever else changes, Approver has to differ from Assessor by more
        than its name, or the consolidation has simply recreated the problem.
        """
        assessor = self.env.ref("spp_disability_registry.group_disability_assessor")
        approver = self.env.ref("spp_disability_registry.group_disability_approver")

        def acls(group):
            rules = self.env["ir.model.access"].search([("group_id", "=", group.id)])
            return {(r.model_id.model, r.perm_read, r.perm_write, r.perm_create, r.perm_unlink) for r in rules}

        self.assertNotEqual(acls(assessor), acls(approver))

    # === approval works with no configuration ===

    def test_approval_is_available_without_configuring_anything(self):
        """A fresh database can submit: the module ships the workflow.

        Before this, `disability_approval_definition_id` was unset, the
        Submit button was hidden behind `has_approval_definition`, and nothing
        could ever reach an approvable state.
        """
        self.assertFalse(
            self.env["ir.config_parameter"].sudo().get_param("spp_disability_registry.approval_definition_id"),
            "the fixture assumes no workflow has been configured",
        )
        assessment = self.env["spp.disability.assessment"].create(
            {"registrant_id": self.registrant.id, "assessment_date": date.today()}
        )

        self.assertTrue(assessment.has_approval_definition)
        self.assertEqual(
            assessment._resolve_approval_definition(),
            self.env.ref("spp_disability_registry.approval_definition_disability_assessment"),
        )

    def test_a_configured_workflow_still_wins(self):
        """The shipped definition is a default, not an override."""
        custom = self.env["spp.approval.definition"].create(
            {
                "name": "Custom Disability Workflow",
                "model_id": self.env["ir.model"]._get_id("spp.disability.assessment"),
                "approval_type": "group",
                "approval_group_id": self.env.ref("base.group_system").id,
            }
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "spp_disability_registry.approval_definition_id", str(custom.id)
        )
        assessment = self.env["spp.disability.assessment"].create(
            {"registrant_id": self.registrant.id, "assessment_date": date.today()}
        )

        self.assertEqual(assessment._resolve_approval_definition(), custom)

    # === who may do what ===

    def test_the_approver_role_is_offered_the_buttons(self):
        """can_approve drives whether Approve and Reject render.

        This is only half the story, and on its own it is misleading: the
        buttons appeared in QA round 1 and then failed on click, because
        approving writes to the approval framework's own records. See
        test_the_approver_role_can_actually_approve.
        """
        approver = self._user("test_1173_approver", "spp_disability_registry.group_disability_approver")
        assessment = self.env["spp.disability.assessment"].create(
            {"registrant_id": self.registrant.id, "assessment_date": date.today(), **SUBMITTABLE}
        )
        assessment.action_submit_for_approval()

        self.assertEqual(assessment.approval_state, "pending")
        self.assertTrue(assessment.with_user(approver).can_approve)
        self.assertTrue(assessment.with_user(approver).can_reject)

    def test_the_assessor_role_cannot_approve(self):
        """Otherwise the Approver role would again be decoration."""
        assessor = self._user("test_1173_assessor", "spp_disability_registry.group_disability_assessor")
        assessment = self.env["spp.disability.assessment"].create(
            {"registrant_id": self.registrant.id, "assessment_date": date.today(), **SUBMITTABLE}
        )
        assessment.action_submit_for_approval()

        self.assertFalse(assessment.with_user(assessor).can_approve)
        self.assertFalse(assessment.with_user(assessor).can_reject)

    def test_the_approver_role_can_actually_approve(self):
        """Press the button, do not just check that it renders.

        QA round 1: the Approve button showed for a Disability Approver and
        raised "You are not allowed to modify 'Approval Review Record'" on
        click. `_do_approve` calls `pending_reviews.action_approve(...)`
        without sudo, and write on spp.approval.review belongs to
        spp_approval's own groups. Asserting on can_approve could never have
        caught it -- that flag is computed from the definition's approver
        group and was correctly True the whole time.
        """
        approver = self._user("test_1173_doer", "spp_disability_registry.group_disability_approver")
        assessment = self.env["spp.disability.assessment"].create(
            {"registrant_id": self.registrant.id, "assessment_date": date.today(), **SUBMITTABLE}
        )
        assessment.action_submit_for_approval()
        self.assertEqual(assessment.approval_state, "pending")

        assessment.with_user(approver).action_approve()

        self.assertEqual(assessment.approval_state, "approved")
        self.assertFalse(
            assessment.approval_review_ids.filtered(lambda r: r.status == "pending"),
            "the approval review should have been closed too",
        )

    def test_the_approver_can_write_the_review_the_approval_updates(self):
        """The specific right the round-1 failure was missing.

        Pinned directly so a future change to the implied groups fails here
        with a clear reason rather than somewhere deep in the approval flow.
        """
        approver = self._user("test_1173_writer", "spp_disability_registry.group_disability_approver")
        review = self.env["spp.approval.review"]

        self.assertTrue(
            review.with_user(approver).has_access("write"),
            "a Disability Approver cannot write approval reviews, so Approve will fail on click",
        )
        self.assertFalse(
            review.with_user(approver).has_access("unlink"),
            "an approver should not be able to delete an approval trail",
        )

    def test_the_assessor_still_cannot_approve(self):
        """Widening the approver's rights must not widen the assessor's."""
        assessor = self._user("test_1173_assessor_deny", "spp_disability_registry.group_disability_assessor")
        assessment = self.env["spp.disability.assessment"].create(
            {"registrant_id": self.registrant.id, "assessment_date": date.today(), **SUBMITTABLE}
        )
        assessment.action_submit_for_approval()

        # A UserError naming the required group, not an access error: the
        # framework refuses on can_approve before any ACL is consulted.
        with self.assertRaises(UserError):
            assessment.with_user(assessor).action_approve()
