# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for per-CR-Type approval workflow definitions.

This test verifies that each Change Request Type can have its own specific
approval workflow, and that the approval mixin respects this configuration.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApprovalPerCRType(TransactionCase):
    """Test that CR Types can have different approval workflows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get CR validator group and approval viewer group
        cls.cr_validator_group = cls.env.ref(
            "spp_change_request_v2.group_cr_validator",
            raise_if_not_found=False,
        )
        cls.approval_viewer_group = cls.env.ref(
            "spp_approval.group_approval_viewer",
            raise_if_not_found=False,
        )

        # Build group_ids for test users
        user_groups = []
        if cls.cr_validator_group:
            user_groups.append((4, cls.cr_validator_group.id))
        if cls.approval_viewer_group:
            user_groups.append((4, cls.approval_viewer_group.id))

        # Create test users for different approval workflows
        cls.user_approver_a = cls.env["res.users"].create(
            {
                "name": "Approver A",
                "login": "approver_a_test",
                "email": "approver_a@test.com",
                "group_ids": user_groups,
            }
        )
        cls.user_approver_b = cls.env["res.users"].create(
            {
                "name": "Approver B",
                "login": "approver_b_test",
                "email": "approver_b@test.com",
                "group_ids": user_groups,
            }
        )

        # Get the ir.model for spp.change.request
        cls.cr_model_record = cls.env["ir.model"].search([("model", "=", "spp.change.request")], limit=1)

        # Create two different approval definitions using user-based approval (more direct)
        cls.approval_def_a = cls.env["spp.approval.definition"].create(
            {
                "name": "Approval Workflow A (for Edit Individual)",
                "model_id": cls.cr_model_record.id,
                "approval_type": "user",
                "approval_user_ids": [(6, 0, [cls.user_approver_a.id])],
            }
        )
        cls.approval_def_b = cls.env["spp.approval.definition"].create(
            {
                "name": "Approval Workflow B (for Edit Group)",
                "model_id": cls.cr_model_record.id,
                "approval_type": "user",
                "approval_user_ids": [(6, 0, [cls.user_approver_b.id])],
            }
        )

        # Get CR types by code (may be in different modules)
        cls.cr_type_edit_individual = cls.env["spp.change.request.type"].search(
            [("code", "=", "edit_individual")], limit=1
        )
        if not cls.cr_type_edit_individual:
            cls.cr_type_edit_individual = cls.env["spp.change.request.type"].create(
                {
                    "name": "Test Edit Individual",
                    "code": "test_edit_individual",
                    "target_type": "individual",
                    "detail_model": "spp.cr.detail.edit_individual",
                    "apply_strategy": "field_mapping",
                }
            )
        cls.cr_type_edit_group = cls.env["spp.change.request.type"].search([("code", "=", "edit_group")], limit=1)
        if not cls.cr_type_edit_group:
            cls.cr_type_edit_group = cls.env["spp.change.request.type"].create(
                {
                    "name": "Test Edit Group",
                    "code": "test_edit_group",
                    "target_type": "group",
                    "detail_model": "spp.cr.detail.edit_group",
                    "apply_strategy": "field_mapping",
                }
            )

        if cls.cr_type_edit_individual:
            cls.cr_type_edit_individual.approval_definition_id = cls.approval_def_a
        if cls.cr_type_edit_group:
            cls.cr_type_edit_group.approval_definition_id = cls.approval_def_b

        # Create test registrants
        cls.individual = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "given_name": "Test",
                "family_name": "Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.group = cls.env["res.partner"].create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )

    def test_cr_type_has_approval_definition_field(self):
        """Verify CR Type has approval_definition_id field configured."""
        if not self.cr_type_edit_individual:
            self.skipTest("Edit individual CR type not found")

        self.assertEqual(
            self.cr_type_edit_individual.approval_definition_id,
            self.approval_def_a,
            "CR Type should have approval definition A assigned",
        )
        self.assertEqual(
            self.cr_type_edit_group.approval_definition_id,
            self.approval_def_b,
            "CR Type should have approval definition B assigned",
        )

    def test_cr_get_approval_definition_returns_type_definition(self):
        """Test that CR._get_approval_definition() returns the type's definition."""
        if not self.cr_type_edit_individual:
            self.skipTest("Edit individual CR type not found")

        # Create CR for individual
        cr_individual = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_edit_individual.id,
                "registrant_id": self.individual.id,
            }
        )

        # Create CR for group
        cr_group = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_edit_group.id,
                "registrant_id": self.group.id,
            }
        )

        # Verify _get_approval_definition returns the CR Type's definition
        self.assertEqual(
            cr_individual._get_approval_definition(),
            self.approval_def_a,
            "Individual CR should use approval definition A from its type",
        )
        self.assertEqual(
            cr_group._get_approval_definition(),
            self.approval_def_b,
            "Group CR should use approval definition B from its type",
        )

    def test_different_cr_types_use_different_approvers(self):
        """Verify that different CR types use their own approval workflows.

        Each CR Type can have its own approval_definition_id, and when a CR is
        submitted for approval, the review should use that type's definition.

        Expected behavior:
        - Edit Individual CR uses Approval Definition A (approver_a)
        - Edit Group CR uses Approval Definition B (approver_b)
        """
        if not self.cr_type_edit_individual or not self.cr_type_edit_group:
            self.skipTest("Required CR types not found")

        # Create CRs
        cr_individual = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_edit_individual.id,
                "registrant_id": self.individual.id,
            }
        )
        cr_group = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_edit_group.id,
                "registrant_id": self.group.id,
            }
        )

        # Submit both for approval
        cr_individual.action_submit_for_approval()
        cr_group.action_submit_for_approval()

        # Both should now be pending
        self.assertEqual(cr_individual.approval_state, "pending")
        self.assertEqual(cr_group.approval_state, "pending")

        # Get the approval reviews created
        review_individual = cr_individual.approval_review_ids.filtered(lambda r: r.status == "pending")
        review_group = cr_group.approval_review_ids.filtered(lambda r: r.status == "pending")

        self.assertTrue(review_individual, "Individual CR should have pending review")
        self.assertTrue(review_group, "Group CR should have pending review")

        # Each review should use the approval definition from its CR Type
        self.assertEqual(
            review_individual.definition_id,
            self.approval_def_a,
            "Individual CR review should use Approval Definition A from CR Type",
        )
        self.assertEqual(
            review_group.definition_id,
            self.approval_def_b,
            "Group CR review should use Approval Definition B from CR Type",
        )

    def test_approver_permissions_respect_cr_type(self):
        """
        Test that can_approve is computed based on CR Type's approval definition.

        Expected:
        - user_approver_a CAN approve Edit Individual CRs (Def A)
        - user_approver_a CANNOT approve Edit Group CRs (Def B)
        - user_approver_b CANNOT approve Edit Individual CRs (Def A)
        - user_approver_b CAN approve Edit Group CRs (Def B)
        """
        if not self.cr_type_edit_individual or not self.cr_type_edit_group:
            self.skipTest("Required CR types not found")

        # Verify setup is correct
        self.assertIn(
            self.user_approver_a,
            self.approval_def_a.approval_user_ids,
            "Setup check: user_approver_a should be in approval_def_a",
        )
        self.assertNotIn(
            self.user_approver_b,
            self.approval_def_a.approval_user_ids,
            "Setup check: user_approver_b should NOT be in approval_def_a",
        )

        # Create and submit CRs
        cr_individual = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type_edit_individual.id,
                "registrant_id": self.individual.id,
            }
        )

        cr_individual.action_submit_for_approval()

        # Verify the review was created with correct definition
        pending_review = cr_individual.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]
        self.assertTrue(pending_review, "Should have a pending review")
        self.assertEqual(
            pending_review.definition_id,
            self.approval_def_a,
            "Review should use approval_def_a from CR Type",
        )

        # Check approvers from the definition
        approvers = pending_review.definition_id.get_approvers(cr_individual)
        self.assertIn(
            self.user_approver_a,
            approvers,
            "user_approver_a should be in approvers list",
        )
        self.assertNotIn(
            self.user_approver_b,
            approvers,
            "user_approver_b should NOT be in approvers list",
        )

        # Now check can_approve for each user
        cr_individual.invalidate_recordset()
        cr_individual_as_a = cr_individual.with_user(self.user_approver_a)
        self.assertTrue(
            cr_individual_as_a.can_approve,
            "Approver A should be able to approve Individual CR",
        )

        cr_individual.invalidate_recordset()
        cr_individual_as_b = cr_individual.with_user(self.user_approver_b)
        self.assertFalse(
            cr_individual_as_b.can_approve,
            "Approver B should NOT be able to approve Individual CR",
        )
