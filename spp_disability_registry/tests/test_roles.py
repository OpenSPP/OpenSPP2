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
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@test.com",
                "group_ids": [Command.link(self.env.ref(group_xmlid).id)],
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

    def test_the_approver_role_can_approve(self):
        """The point of the ticket: holding the role is enough."""
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
