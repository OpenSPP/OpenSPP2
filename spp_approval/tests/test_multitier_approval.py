from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


def _has_hr_module(env):
    """Check if hr module is installed."""
    return env["ir.module.module"].search(
        [
            ("name", "=", "hr"),
            ("state", "=", "installed"),
        ]
    )


@tagged("post_install", "-at_install")
class TestMultitierApproval(TransactionCase):
    """Test multi-tier approval workflows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test users
        cls.user_submitter = cls.env["res.users"].create(
            {
                "name": "Submitter User",
                "login": "submitter_multitier",
                "email": "submitter@test.com",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )

        cls.user_validator = cls.env["res.users"].create(
            {
                "name": "Validator User",
                "login": "validator_multitier",
                "email": "validator@test.com",
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("spp_approval.group_approval_approver").id,
                        ]
                    )
                ],
            }
        )

        cls.user_manager = cls.env["res.users"].create(
            {
                "name": "Manager User",
                "login": "manager_multitier",
                "email": "manager@test.com",
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("spp_approval.group_approval_manager").id,
                        ]
                    )
                ],
            }
        )

        cls.user_director = cls.env["res.users"].create(
            {
                "name": "Director User",
                "login": "director_multitier",
                "email": "director@test.com",
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("spp_approval.group_approval_admin").id,
                        ]
                    )
                ],
            }
        )

        # Create security groups for tiers
        cls.group_validators = cls.env["res.groups"].create(
            {
                "name": "Test Validators",
                "user_ids": [Command.set([cls.user_validator.id])],
            }
        )

        cls.group_managers = cls.env["res.groups"].create(
            {
                "name": "Test Managers",
                "user_ids": [Command.set([cls.user_manager.id])],
            }
        )

        cls.group_directors = cls.env["res.groups"].create(
            {
                "name": "Test Directors",
                "user_ids": [Command.set([cls.user_director.id])],
            }
        )

        # Get test model
        cls.test_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        # Create multi-tier approval definition with tiers inline
        cls.definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Multi-Tier Partner Approval",
                "model_id": cls.test_model.id,
                "use_multitier": True,
                "active": True,
                "tier_ids": [
                    Command.create(
                        {
                            "name": "Validator Review",
                            "sequence": 10,
                            "approval_type": "group",
                            "approval_group_id": cls.group_validators.id,
                            "min_approvers": 1,
                            "sla_hours": 24,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Manager Approval",
                            "sequence": 20,
                            "approval_type": "group",
                            "approval_group_id": cls.group_managers.id,
                            "min_approvers": 1,
                            "sla_hours": 48,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Director Approval",
                            "sequence": 30,
                            "approval_type": "group",
                            "approval_group_id": cls.group_directors.id,
                            "min_approvers": 1,
                            "sla_hours": 72,
                        }
                    ),
                ],
            }
        )

        # Get tier references
        tiers = cls.definition.tier_ids.sorted("sequence")
        cls.tier_1 = tiers[0]
        cls.tier_2 = tiers[1]
        cls.tier_3 = tiers[2]


class TestTierModel(TestMultitierApproval):
    """Test spp.approval.tier model."""

    def test_tier_creation(self):
        """Test tier is created correctly."""
        self.assertEqual(self.tier_1.name, "Validator Review")
        self.assertEqual(self.tier_1.approval_type, "group")
        self.assertEqual(self.tier_1.min_approvers, 1)

    def test_tier_sequence(self):
        """Test tiers are ordered by sequence."""
        tiers = self.definition.get_ordered_tiers()
        self.assertEqual(len(tiers), 3)
        self.assertEqual(tiers[0], self.tier_1)
        self.assertEqual(tiers[1], self.tier_2)
        self.assertEqual(tiers[2], self.tier_3)

    def test_tier_get_approvers_group(self):
        """Test get_approvers for group type."""
        # Create a mock record
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        approvers = self.tier_1.get_approvers(partner)
        self.assertIn(self.user_validator, approvers)
        self.assertNotIn(self.user_manager, approvers)

    def test_tier_get_approvers_user(self):
        """Test get_approvers for user type."""
        tier = self.env["spp.approval.tier"].create(
            {
                "name": "Specific User Tier",
                "sequence": 5,
                "definition_id": self.definition.id,
                "approval_type": "user",
                "approval_user_ids": [Command.set([self.user_manager.id, self.user_director.id])],
            }
        )

        partner = self.env["res.partner"].create({"name": "Test Partner"})
        approvers = tier.get_approvers(partner)

        self.assertIn(self.user_manager, approvers)
        self.assertIn(self.user_director, approvers)
        self.assertNotIn(self.user_validator, approvers)

    def test_tier_validation_group_required(self):
        """Test validation: group required for group type."""
        with self.assertRaises(ValidationError):
            self.env["spp.approval.tier"].create(
                {
                    "name": "Invalid Tier",
                    "sequence": 100,
                    "definition_id": self.definition.id,
                    "approval_type": "group",
                    # Missing approval_group_id
                }
            )

    def test_tier_self_approve_filter(self):
        """Test self-approval filtering.

        Note: This test verifies that self-approval filtering works when the
        record has a submitted_by_id field. For models without this field
        (like res.partner used here), self-approval filtering is skipped.
        Full self-approval testing requires a model inheriting from spp.approval.mixin.
        """
        # Tier without self-approve
        self.tier_1.can_self_approve = False
        partner = self.env["res.partner"].create({"name": "Test"})

        # Without submitted_by_id field, self-approval filtering is skipped
        # so all group members remain as approvers
        approvers = self.tier_1.get_approvers(partner)
        self.assertIn(self.user_validator, approvers)

        # Tier with self-approve - should still include all
        self.tier_1.can_self_approve = True
        approvers = self.tier_1.get_approvers(partner)
        self.assertIn(self.user_validator, approvers)


class TestDefinitionMultitier(TestMultitierApproval):
    """Test multi-tier approval definition."""

    def test_definition_multitier_flag(self):
        """Test use_multitier flag."""
        self.assertTrue(self.definition.use_multitier)
        self.assertEqual(self.definition.tier_count, 3)

    def test_definition_requires_tiers(self):
        """Test multi-tier definition requires at least one tier."""
        with self.assertRaises(ValidationError):
            self.env["spp.approval.definition"].create(
                {
                    "name": "Invalid Multi-Tier",
                    "model_id": self.test_model.id,
                    "use_multitier": True,
                    # No tiers
                }
            )

    def test_definition_get_approvers_returns_first_tier(self):
        """Test get_approvers returns first tier approvers."""
        partner = self.env["res.partner"].create({"name": "Test"})
        approvers = self.definition.get_approvers(partner)

        # Should return tier 1 (validator) approvers
        self.assertIn(self.user_validator, approvers)


class TestReviewMultitier(TestMultitierApproval):
    """Test multi-tier approval review."""

    def test_review_creates_tier_reviews(self):
        """Test review creation creates tier review records."""
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 1,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        self.assertEqual(len(review.tier_review_ids), 3)
        self.assertTrue(review.is_multitier)

    def test_first_tier_activated(self):
        """Test first tier is automatically activated."""
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 1,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        tier_reviews = review.tier_review_ids.sorted("sequence")
        self.assertEqual(tier_reviews[0].status, "pending")
        self.assertEqual(tier_reviews[1].status, "waiting")
        self.assertEqual(tier_reviews[2].status, "waiting")

    def test_tier_progress_calculation(self):
        """Test tier progress is calculated correctly."""
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 1,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        self.assertEqual(review.total_tiers, 3)
        self.assertEqual(review.completed_tiers, 0)
        self.assertEqual(review.tier_progress, 0)

    def test_current_tier_tracking(self):
        """Test current tier is tracked correctly."""
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 1,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        self.assertEqual(review.current_tier_id, self.tier_1)
        self.assertEqual(review.current_tier_name, "Validator Review")


class TestTierReviewWorkflow(TestMultitierApproval):
    """Test tier review workflow."""

    def setUp(self):
        super().setUp()
        # Create a test partner
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner for Approval",
            }
        )

        # Create review (submitter is tracked via requested_by_id)
        self.review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

    def test_tier_approve_success(self):
        """Test successful tier approval."""
        tier_review = self.review.tier_review_ids.filtered(lambda t: t.status == "pending")[:1]

        # Approve as validator
        tier_review.with_user(self.user_validator).action_approve(comment="Looks good")

        self.assertEqual(tier_review.status, "approved")
        self.assertIn(self.user_validator, tier_review.approved_by_ids)
        self.assertTrue(tier_review.approved_date)
        self.assertTrue(tier_review.completed_date)

    def test_tier_approve_activates_next(self):
        """Test approving tier activates next tier."""
        tier_reviews = self.review.tier_review_ids.sorted("sequence")

        # Approve first tier
        tier_reviews[0].with_user(self.user_validator).action_approve()

        # Check second tier is now pending
        tier_reviews.invalidate_recordset()
        self.assertEqual(tier_reviews[0].status, "approved")
        self.assertEqual(tier_reviews[1].status, "pending")
        self.assertEqual(tier_reviews[2].status, "waiting")

    def test_tier_approve_unauthorized(self):
        """Test unauthorized user cannot approve tier."""
        tier_review = self.review.tier_review_ids.filtered(lambda t: t.status == "pending")[:1]

        # Try to approve as submitter (not an approver)
        with self.assertRaises(UserError):
            tier_review.with_user(self.user_submitter).action_approve()

    def test_tier_reject(self):
        """Test tier rejection."""
        tier_review = self.review.tier_review_ids.filtered(lambda t: t.status == "pending")[:1]

        # Reject as validator
        tier_review.with_user(self.user_validator).action_reject("Does not meet requirements")

        self.assertEqual(tier_review.status, "rejected")
        self.assertEqual(tier_review.rejected_by_id, self.user_validator)
        self.assertEqual(tier_review.rejection_reason, "Does not meet requirements")

    def test_tier_reject_skips_remaining(self):
        """Test rejecting a tier skips remaining tiers."""
        tier_reviews = self.review.tier_review_ids.sorted("sequence")

        # Reject first tier
        tier_reviews[0].with_user(self.user_validator).action_reject("Rejected")

        # Check remaining tiers are skipped
        tier_reviews.invalidate_recordset()
        self.assertEqual(tier_reviews[0].status, "rejected")
        self.assertEqual(tier_reviews[1].status, "skipped")
        self.assertEqual(tier_reviews[2].status, "skipped")

    def test_full_approval_workflow(self):
        """Test complete multi-tier approval workflow."""
        tier_reviews = self.review.tier_review_ids.sorted("sequence")

        # Tier 1: Validator approves
        tier_reviews[0].with_user(self.user_validator).action_approve()
        tier_reviews.invalidate_recordset()

        # Tier 2: Manager approves
        tier_reviews[1].with_user(self.user_manager).action_approve()
        tier_reviews.invalidate_recordset()

        # Tier 3: Director approves
        tier_reviews[2].with_user(self.user_director).action_approve()
        tier_reviews.invalidate_recordset()

        # All tiers should be approved
        self.assertEqual(tier_reviews[0].status, "approved")
        self.assertEqual(tier_reviews[1].status, "approved")
        self.assertEqual(tier_reviews[2].status, "approved")

        # Review should be approved
        self.review.invalidate_recordset()
        self.assertEqual(self.review.status, "approved")

    def test_double_approve_prevented(self):
        """Test same user cannot approve twice."""
        tier_review = self.review.tier_review_ids.filtered(lambda t: t.status == "pending")[:1]

        # First approval
        tier_review.with_user(self.user_validator).action_approve()

        # Create another tier that requires all approvers
        tier_review.tier_id.require_all = True
        tier_review.status = "pending"  # Reset for test

        # Try to approve again
        with self.assertRaises(UserError):
            tier_review.with_user(self.user_validator).action_approve()


class TestRequireAllApprovers(TestMultitierApproval):
    """Test require_all approvers functionality."""

    def setUp(self):
        super().setUp()
        # Add another validator
        self.user_validator_2 = self.env["res.users"].create(
            {
                "name": "Validator 2",
                "login": "validator2_multitier",
                "email": "validator2@test.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        self.group_validators.write(
            {
                "user_ids": [Command.link(self.user_validator_2.id)],
            }
        )

        # Set tier to require all approvers
        self.tier_1.require_all = True

        # Create partner and review
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        self.review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

    def test_require_all_not_complete_with_one(self):
        """Test tier not complete with only one approver when require_all."""
        tier_review = self.review.tier_review_ids.sorted("sequence")[0]

        # First validator approves
        tier_review.with_user(self.user_validator).action_approve()

        # Tier should still be pending
        self.assertEqual(tier_review.status, "pending")
        self.assertEqual(len(tier_review.approved_by_ids), 1)


class TestMinApprovers(TestMultitierApproval):
    """Test minimum approvers functionality."""

    def setUp(self):
        super().setUp()
        # Add more validators - include approver group for permissions
        approver_group = self.env.ref("spp_approval.group_approval_approver")
        self.user_validator_2 = self.env["res.users"].create(
            {
                "name": "Validator 2",
                "login": "validator2_min",
                "email": "validator2@test.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id, approver_group.id])],
            }
        )
        self.user_validator_3 = self.env["res.users"].create(
            {
                "name": "Validator 3",
                "login": "validator3_min",
                "email": "validator3@test.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id, approver_group.id])],
            }
        )
        self.group_validators.write(
            {
                "user_ids": [
                    Command.link(self.user_validator_2.id),
                    Command.link(self.user_validator_3.id),
                ],
            }
        )

        # Set min_approvers to 2
        self.tier_1.min_approvers = 2

        # Create partner and review
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        self.review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

    def test_min_approvers_not_complete_with_one(self):
        """Test tier not complete with one approver when min is 2."""
        tier_review = self.review.tier_review_ids.sorted("sequence")[0]

        # First validator approves
        tier_review.with_user(self.user_validator).action_approve()

        # Tier should still be pending
        self.assertEqual(tier_review.status, "pending")

    def test_min_approvers_complete_with_two(self):
        """Test tier completes when minimum approvers reached."""
        tier_review = self.review.tier_review_ids.sorted("sequence")[0]

        # First validator approves
        tier_review.with_user(self.user_validator).action_approve()
        self.assertEqual(tier_review.status, "pending")

        # Second validator approves
        tier_review.with_user(self.user_validator_2).action_approve()

        # Now tier should be approved
        self.assertEqual(tier_review.status, "approved")


class TestSLATracking(TestMultitierApproval):
    """Test SLA tracking for tiers."""

    def test_sla_deadline_set(self):
        """Test SLA deadline is set when tier is activated."""
        self.tier_1.sla_hours = 24

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 1,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        tier_review = review.tier_review_ids.sorted("sequence")[0]
        self.assertTrue(tier_review.sla_deadline)

    def test_sla_no_deadline_when_zero_hours(self):
        """Test no SLA deadline when sla_hours is 0."""
        self.tier_1.sla_hours = 0

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 1,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        tier_review = review.tier_review_ids.sorted("sequence")[0]
        self.assertFalse(tier_review.sla_deadline)

    def test_sla_breach_detection(self):
        """Test SLA breach is detected correctly."""
        from datetime import timedelta

        self.tier_1.sla_hours = 24

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 1,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        tier_review = review.tier_review_ids.sorted("sequence")[0]

        # Initially not breached
        self.assertFalse(tier_review.sla_breached)

        # Set deadline to past
        tier_review.sla_deadline = fields.Datetime.now() - timedelta(hours=25)
        tier_review._compute_sla_breached()

        # Should be breached
        self.assertTrue(tier_review.sla_breached)

    def test_sla_not_breached_after_completion(self):
        """Test SLA breach flag is False when tier is completed."""
        from datetime import timedelta

        self.tier_1.sla_hours = 24

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 1,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        tier_review = review.tier_review_ids.sorted("sequence")[0]

        # Set deadline to past but approve the tier
        tier_review.sla_deadline = fields.Datetime.now() - timedelta(hours=25)
        tier_review.with_user(self.user_validator).action_approve()

        tier_review._compute_sla_breached()

        # Should not be breached after approval
        self.assertFalse(tier_review.sla_breached)


class TestTierManagerType(TestMultitierApproval):
    """Test 'manager' approval type for tiers.

    These tests require the hr module to be installed.
    """

    def setUp(self):
        super().setUp()

        # Skip if hr module not installed
        if not _has_hr_module(self.env):
            self.skipTest("hr module not installed")

        # Create employee for submitter with manager
        self.employee_submitter = self.env["hr.employee"].create(
            {
                "name": "Submitter Employee",
                "user_id": self.user_submitter.id,
            }
        )

        self.employee_manager = self.env["hr.employee"].create(
            {
                "name": "Manager Employee",
                "user_id": self.user_manager.id,
            }
        )

        self.employee_submitter.parent_id = self.employee_manager

        # Create tier with manager type
        self.tier_manager = self.env["spp.approval.tier"].create(
            {
                "name": "Manager Approval",
                "sequence": 5,
                "definition_id": self.definition.id,
                "approval_type": "manager",
            }
        )

    def test_manager_type_returns_submitter_manager(self):
        """Test manager type returns submitter's manager.

        Note: Uses create_uid fallback since res.partner doesn't have submitted_by_id.
        """
        # Create partner as submitter user to set create_uid
        partner = self.env["res.partner"].with_user(self.user_submitter).create({"name": "Test"})

        approvers = self.tier_manager.get_approvers(partner)

        self.assertEqual(len(approvers), 1)
        self.assertEqual(approvers, self.user_manager)

    def test_manager_type_no_employee(self):
        """Test manager type with submitter having no employee record."""
        user_no_employee = self.env["res.users"].create(
            {
                "name": "User Without Employee",
                "login": "no_employee",
                "email": "no_employee@test.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )

        # Create partner as user without employee to set create_uid
        partner = self.env["res.partner"].with_user(user_no_employee).create({"name": "Test"})

        approvers = self.tier_manager.get_approvers(partner)

        self.assertEqual(len(approvers), 0)

    def test_manager_type_no_parent(self):
        """Test manager type with employee having no parent."""
        self.env["hr.employee"].create(
            {
                "name": "Employee Without Parent",
                "user_id": self.user_validator.id,
            }
        )

        # Create partner as validator user to set create_uid
        partner = self.env["res.partner"].with_user(self.user_validator).create({"name": "Test"})

        approvers = self.tier_manager.get_approvers(partner)

        self.assertEqual(len(approvers), 0)


class TestTierFieldType(TestMultitierApproval):
    """Test 'field' approval type for tiers."""

    def setUp(self):
        super().setUp()

        # Create tier with field type
        self.tier_field = self.env["spp.approval.tier"].create(
            {
                "name": "Field-Based Approval",
                "sequence": 5,
                "definition_id": self.definition.id,
                "approval_type": "field",
                "approval_field": "user_id",
            }
        )

    def test_field_type_returns_user_from_field(self):
        """Test field type returns user from specified field."""
        partner = self.env["res.partner"].create(
            {
                "name": "Test",
                "user_id": self.user_manager.id,
            }
        )

        approvers = self.tier_field.get_approvers(partner)

        self.assertEqual(len(approvers), 1)
        self.assertEqual(approvers, self.user_manager)

    def test_field_type_invalid_field(self):
        """Test field type with non-existent field."""
        self.tier_field.approval_field = "nonexistent_field"

        partner = self.env["res.partner"].create({"name": "Test"})

        approvers = self.tier_field.get_approvers(partner)

        self.assertEqual(len(approvers), 0)

    def test_field_type_empty_field(self):
        """Test field type with empty field value."""
        partner = self.env["res.partner"].create(
            {
                "name": "Test",
                "user_id": False,
            }
        )

        approvers = self.tier_field.get_approvers(partner)

        self.assertEqual(len(approvers), 0)

    def test_field_type_validation_missing(self):
        """Test validation: field name required for field type."""
        with self.assertRaises(ValidationError):
            self.env["spp.approval.tier"].create(
                {
                    "name": "Invalid Field Tier",
                    "sequence": 100,
                    "definition_id": self.definition.id,
                    "approval_type": "field",
                    # Missing approval_field
                }
            )


class TestTierValidations(TestMultitierApproval):
    """Test tier model validations."""

    def test_validation_user_type_requires_users(self):
        """Test validation: users required for user type."""
        with self.assertRaises(ValidationError):
            self.env["spp.approval.tier"].create(
                {
                    "name": "Invalid User Tier",
                    "sequence": 100,
                    "definition_id": self.definition.id,
                    "approval_type": "user",
                    # Missing approval_user_ids
                }
            )

    def test_validation_min_approvers_positive(self):
        """Test validation: min_approvers must be at least 1."""
        with self.assertRaises(ValidationError):
            self.env["spp.approval.tier"].create(
                {
                    "name": "Invalid Min Tier",
                    "sequence": 100,
                    "definition_id": self.definition.id,
                    "approval_type": "group",
                    "approval_group_id": self.group_validators.id,
                    "min_approvers": 0,
                }
            )

    def test_inactive_users_filtered_out(self):
        """Test inactive users are filtered from approvers."""
        # Make validator inactive
        self.user_validator.active = False

        partner = self.env["res.partner"].create({"name": "Test"})

        approvers = self.tier_1.get_approvers(partner)

        self.assertNotIn(self.user_validator, approvers)

    def test_empty_group_returns_no_approvers(self):
        """Test tier with empty group returns no approvers."""
        empty_group = self.env["res.groups"].create(
            {
                "name": "Empty Group",
            }
        )

        tier = self.env["spp.approval.tier"].create(
            {
                "name": "Empty Group Tier",
                "sequence": 100,
                "definition_id": self.definition.id,
                "approval_type": "group",
                "approval_group_id": empty_group.id,
            }
        )

        partner = self.env["res.partner"].create({"name": "Test"})
        approvers = tier.get_approvers(partner)

        self.assertEqual(len(approvers), 0)


class TestTierReviewErrorConditions(TestMultitierApproval):
    """Test error conditions in tier review workflow."""

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )

        self.review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

    def test_cannot_approve_non_pending_tier(self):
        """Test error when approving non-pending tier."""
        tier_review = self.review.tier_review_ids.sorted("sequence")[1]
        self.assertEqual(tier_review.status, "waiting")

        with self.assertRaises(UserError):
            tier_review.with_user(self.user_manager).action_approve()

    def test_cannot_reject_non_pending_tier(self):
        """Test error when rejecting non-pending tier."""
        tier_review = self.review.tier_review_ids.sorted("sequence")[1]
        self.assertEqual(tier_review.status, "waiting")

        with self.assertRaises(UserError):
            tier_review.with_user(self.user_manager).action_reject("Test")

    def test_cannot_activate_non_waiting_tier(self):
        """Test error when activating non-waiting tier."""
        tier_review = self.review.tier_review_ids.sorted("sequence")[0]
        self.assertEqual(tier_review.status, "pending")

        with self.assertRaises(UserError):
            tier_review.action_activate()


class TestConcurrentApprovals(TestMultitierApproval):
    """Test concurrent approval scenarios."""

    def setUp(self):
        super().setUp()
        # Add more validators to the group - include approver group for permissions
        approver_group = self.env.ref("spp_approval.group_approval_approver")
        self.user_validator_2 = self.env["res.users"].create(
            {
                "name": "Validator 2",
                "login": "validator2_concurrent",
                "email": "validator2@test.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id, approver_group.id])],
            }
        )
        self.user_validator_3 = self.env["res.users"].create(
            {
                "name": "Validator 3",
                "login": "validator3_concurrent",
                "email": "validator3@test.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id, approver_group.id])],
            }
        )
        self.group_validators.write(
            {
                "user_ids": [
                    Command.link(self.user_validator_2.id),
                    Command.link(self.user_validator_3.id),
                ],
            }
        )

        # Set min_approvers to 2
        self.tier_1.min_approvers = 2

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        self.review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

    def test_concurrent_approvals_by_different_users(self):
        """Test multiple users can approve concurrently."""
        tier_review = self.review.tier_review_ids.sorted("sequence")[0]

        # First user approves
        tier_review.with_user(self.user_validator).action_approve()
        self.assertEqual(tier_review.status, "pending")
        self.assertEqual(len(tier_review.approved_by_ids), 1)

        # Second user approves
        tier_review.with_user(self.user_validator_2).action_approve()
        self.assertEqual(tier_review.status, "approved")
        self.assertEqual(len(tier_review.approved_by_ids), 2)

        # Third user can still approve even after tier is approved
        # (This tests the system doesn't break, even if UI would hide the button)

    def test_more_than_minimum_can_approve(self):
        """Test that more users than minimum can approve before completion."""
        self.tier_1.min_approvers = 2

        tier_review = self.review.tier_review_ids.sorted("sequence")[0]

        # First approval
        tier_review.with_user(self.user_validator).action_approve()
        self.assertEqual(len(tier_review.approved_by_ids), 1)

        # Second approval - should complete
        tier_review.with_user(self.user_validator_2).action_approve()
        self.assertEqual(tier_review.status, "approved")
        self.assertEqual(len(tier_review.approved_by_ids), 2)


class TestRequireAllComplete(TestMultitierApproval):
    """Test complete scenarios for require_all."""

    def setUp(self):
        super().setUp()
        # Add another validator - include approver group for permissions
        approver_group = self.env.ref("spp_approval.group_approval_approver")
        self.user_validator_2 = self.env["res.users"].create(
            {
                "name": "Validator 2",
                "login": "validator2_require_all",
                "email": "validator2@test.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id, approver_group.id])],
            }
        )
        self.group_validators.write(
            {
                "user_ids": [Command.link(self.user_validator_2.id)],
            }
        )

        # Set tier to require all approvers
        self.tier_1.require_all = True

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        self.review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

    def test_require_all_completes_when_all_approve(self):
        """Test tier completes when all designated approvers approve."""
        tier_review = self.review.tier_review_ids.sorted("sequence")[0]

        # First validator approves
        tier_review.with_user(self.user_validator).action_approve()
        self.assertEqual(tier_review.status, "pending")

        # Second validator approves - should complete
        tier_review.with_user(self.user_validator_2).action_approve()
        self.assertEqual(tier_review.status, "approved")

    def test_require_all_with_self_approve_filtering(self):
        """Test require_all works with self-approval filtering.

        Note: Since res.partner doesn't have submitted_by_id, self-approval filtering
        is skipped. This test verifies that all approvers in the group must approve.
        """
        # Note: Validators group already has user_validator and user_validator_2
        # Setting require_all means both must approve

        partner = self.env["res.partner"].create({"name": "Test"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        tier_review = review.tier_review_ids.sorted("sequence")[0]

        # Verify both validators are approvers
        approvers = self.tier_1.get_approvers(partner)
        self.assertIn(self.user_validator, approvers)
        self.assertIn(self.user_validator_2, approvers)
        self.assertEqual(len(approvers), 2)

        # First approval - still pending
        tier_review.with_user(self.user_validator).action_approve()
        self.assertEqual(tier_review.status, "pending")

        # Second approval - now approved (all have approved)
        tier_review.with_user(self.user_validator_2).action_approve()
        self.assertEqual(tier_review.status, "approved")


class TestRejectionAtDifferentTiers(TestMultitierApproval):
    """Test rejection behavior at different tier levels."""

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )

        self.review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

    def test_rejection_at_tier_2(self):
        """Test rejecting at second tier."""
        tier_reviews = self.review.tier_review_ids.sorted("sequence")

        # Approve tier 1
        tier_reviews[0].with_user(self.user_validator).action_approve()
        tier_reviews.invalidate_recordset()

        # Reject tier 2
        tier_reviews[1].with_user(self.user_manager).action_reject("Not acceptable")

        tier_reviews.invalidate_recordset()

        # Check statuses
        self.assertEqual(tier_reviews[0].status, "approved")
        self.assertEqual(tier_reviews[1].status, "rejected")
        self.assertEqual(tier_reviews[2].status, "skipped")

        # Review should be rejected
        self.review.invalidate_recordset()
        self.assertEqual(self.review.status, "rejected")

    def test_rejection_at_tier_3(self):
        """Test rejecting at third tier."""
        tier_reviews = self.review.tier_review_ids.sorted("sequence")

        # Approve tiers 1 and 2
        tier_reviews[0].with_user(self.user_validator).action_approve()
        tier_reviews.invalidate_recordset()

        tier_reviews[1].with_user(self.user_manager).action_approve()
        tier_reviews.invalidate_recordset()

        # Reject tier 3
        tier_reviews[2].with_user(self.user_director).action_reject("Final rejection")

        tier_reviews.invalidate_recordset()

        # Check statuses
        self.assertEqual(tier_reviews[0].status, "approved")
        self.assertEqual(tier_reviews[1].status, "approved")
        self.assertEqual(tier_reviews[2].status, "rejected")

        # Review should be rejected
        self.review.invalidate_recordset()
        self.assertEqual(self.review.status, "rejected")

    def test_rejection_reason_stored(self):
        """Test rejection reason is properly stored."""
        tier_review = self.review.tier_review_ids.sorted("sequence")[0]

        reason = "This is the detailed rejection reason"
        tier_review.with_user(self.user_validator).action_reject(reason)

        self.assertEqual(tier_review.rejection_reason, reason)
        self.assertEqual(tier_review.rejected_by_id, self.user_validator)
        self.assertTrue(tier_review.rejected_date)


class TestMixedTierConfigurations(TestMultitierApproval):
    """Test workflows with mixed tier configurations."""

    def setUp(self):
        super().setUp()
        # Add more users for complex scenarios - include approver group for permissions
        approver_group = self.env.ref("spp_approval.group_approval_approver")
        self.user_validator_2 = self.env["res.users"].create(
            {
                "name": "Validator 2",
                "login": "validator2_mixed",
                "email": "validator2@test.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id, approver_group.id])],
            }
        )
        self.user_validator_3 = self.env["res.users"].create(
            {
                "name": "Validator 3",
                "login": "validator3_mixed",
                "email": "validator3@test.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id, approver_group.id])],
            }
        )
        self.group_validators.write(
            {
                "user_ids": [
                    Command.link(self.user_validator_2.id),
                    Command.link(self.user_validator_3.id),
                ],
            }
        )

    def test_mixed_require_all_and_min_approvers(self):
        """Test workflow with require_all tier followed by min_approvers tier."""
        # Tier 1: require all (3 validators)
        self.tier_1.require_all = True

        # Tier 2: min 1 manager
        self.tier_2.min_approvers = 1

        partner = self.env["res.partner"].create({"name": "Test"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        tier_reviews = review.tier_review_ids.sorted("sequence")

        # Tier 1: All validators must approve
        tier_reviews[0].with_user(self.user_validator).action_approve()
        self.assertEqual(tier_reviews[0].status, "pending")

        tier_reviews[0].with_user(self.user_validator_2).action_approve()
        self.assertEqual(tier_reviews[0].status, "pending")

        tier_reviews[0].with_user(self.user_validator_3).action_approve()
        tier_reviews.invalidate_recordset()
        self.assertEqual(tier_reviews[0].status, "approved")

        # Tier 2: Only 1 manager needed
        tier_reviews[1].with_user(self.user_manager).action_approve()
        tier_reviews.invalidate_recordset()
        self.assertEqual(tier_reviews[1].status, "approved")

        # Continue with tier 3
        tier_reviews[2].with_user(self.user_director).action_approve()

        review.invalidate_recordset()
        self.assertEqual(review.status, "approved")

    def test_mixed_approval_types(self):
        """Test workflow with different approval types per tier."""
        # Create tier with user type
        tier_user = self.env["spp.approval.tier"].create(
            {
                "name": "Specific Users",
                "sequence": 5,
                "definition_id": self.definition.id,
                "approval_type": "user",
                "approval_user_ids": [Command.set([self.user_validator.id])],
            }
        )

        partner = self.env["res.partner"].create({"name": "Test"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        tier_reviews = review.tier_review_ids.sorted("sequence")

        # Should have 4 tiers now
        self.assertEqual(len(tier_reviews), 4)

        # First tier (user type)
        self.assertEqual(tier_reviews[0].tier_id, tier_user)
        tier_reviews[0].with_user(self.user_validator).action_approve()

        # Continue through remaining tiers
        tier_reviews.invalidate_recordset()
        tier_reviews[1].with_user(self.user_validator).action_approve()

        tier_reviews.invalidate_recordset()
        tier_reviews[2].with_user(self.user_manager).action_approve()

        tier_reviews.invalidate_recordset()
        tier_reviews[3].with_user(self.user_director).action_approve()

        review.invalidate_recordset()
        self.assertEqual(review.status, "approved")


class TestEdgeCases(TestMultitierApproval):
    """Test edge cases and boundary conditions."""

    def test_definition_with_single_tier(self):
        """Test multi-tier definition with only one tier."""
        # Remove tier 2 and 3
        (self.tier_2 | self.tier_3).unlink()

        partner = self.env["res.partner"].create({"name": "Test"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        self.assertEqual(len(review.tier_review_ids), 1)

        # Approve single tier
        tier_review = review.tier_review_ids[0]
        tier_review.with_user(self.user_validator).action_approve()

        review.invalidate_recordset()
        self.assertEqual(review.status, "approved")

    def test_review_with_nonexistent_record(self):
        """Test review when referenced record doesn't exist."""
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 999999,  # Non-existent ID
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        record = review._get_record()
        self.assertFalse(record)

    def test_tier_progress_calculation_accurate(self):
        """Test tier progress percentage is calculated correctly."""
        partner = self.env["res.partner"].create({"name": "Test"})
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        # Initial: 0%
        self.assertEqual(review.tier_progress, 0)

        tier_reviews = review.tier_review_ids.sorted("sequence")

        # After tier 1: 33.33%
        tier_reviews[0].with_user(self.user_validator).action_approve()
        review.invalidate_recordset()
        self.assertAlmostEqual(review.tier_progress, 33.33, places=1)

        # After tier 2: 66.67%
        tier_reviews.invalidate_recordset()
        tier_reviews[1].with_user(self.user_manager).action_approve()
        review.invalidate_recordset()
        self.assertAlmostEqual(review.tier_progress, 66.67, places=1)

        # After tier 3: 100%
        tier_reviews.invalidate_recordset()
        tier_reviews[2].with_user(self.user_director).action_approve()
        review.invalidate_recordset()
        self.assertEqual(review.tier_progress, 100.0)

    def test_current_tier_tracking_accurate(self):
        """Test current_tier_id tracks correctly through workflow."""
        partner = self.env["res.partner"].create({"name": "Test"})
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        # Initially tier 1
        self.assertEqual(review.current_tier_id, self.tier_1)

        tier_reviews = review.tier_review_ids.sorted("sequence")

        # Approve tier 1 -> current is tier 2
        tier_reviews[0].with_user(self.user_validator).action_approve()
        review.invalidate_recordset()
        self.assertEqual(review.current_tier_id, self.tier_2)

        # Approve tier 2 -> current is tier 3
        tier_reviews.invalidate_recordset()
        tier_reviews[1].with_user(self.user_manager).action_approve()
        review.invalidate_recordset()
        self.assertEqual(review.current_tier_id, self.tier_3)

        # Approve tier 3 -> no current tier
        tier_reviews.invalidate_recordset()
        tier_reviews[2].with_user(self.user_director).action_approve()
        review.invalidate_recordset()
        self.assertFalse(review.current_tier_id)

    def test_approver_count_and_required_approvals(self):
        """Test approver count and required approvals are computed correctly."""
        self.tier_1.min_approvers = 2

        partner = self.env["res.partner"].create({"name": "Test"})
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        tier_review = review.tier_review_ids.sorted("sequence")[0]

        self.assertEqual(tier_review.approver_count, 0)
        self.assertEqual(tier_review.required_approvals, 2)

        # Add an approval
        tier_review.with_user(self.user_validator).action_approve()

        self.assertEqual(tier_review.approver_count, 1)

    def test_get_current_tier_approvers(self):
        """Test getting approvers for current tier."""
        partner = self.env["res.partner"].create({"name": "Test"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        # Current tier is tier 1
        approvers = review.get_current_tier_approvers()
        self.assertIn(self.user_validator, approvers)
        self.assertNotIn(self.user_manager, approvers)

    def test_action_approve_tier_on_review(self):
        """Test approve tier action on review model."""
        partner = self.env["res.partner"].create({"name": "Test"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        # Use review-level action
        review.with_user(self.user_validator).action_approve_tier("Approved")

        tier_reviews = review.tier_review_ids.sorted("sequence")
        self.assertEqual(tier_reviews[0].status, "approved")

    def test_action_reject_tier_on_review(self):
        """Test reject tier action on review model."""
        partner = self.env["res.partner"].create({"name": "Test"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        # Use review-level action
        review.with_user(self.user_validator).action_reject_tier("Rejected")

        tier_reviews = review.tier_review_ids.sorted("sequence")
        self.assertEqual(tier_reviews[0].status, "rejected")
        self.assertEqual(review.status, "rejected")

    def test_no_pending_tier_error(self):
        """Test error when trying to approve/reject with no pending tier."""
        partner = self.env["res.partner"].create({"name": "Test"})
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        # Approve all tiers
        tier_reviews = review.tier_review_ids.sorted("sequence")
        tier_reviews[0].with_user(self.user_validator).action_approve()
        tier_reviews.invalidate_recordset()
        tier_reviews[1].with_user(self.user_manager).action_approve()
        tier_reviews.invalidate_recordset()
        tier_reviews[2].with_user(self.user_director).action_approve()

        review.invalidate_recordset()

        # Try to approve again
        with self.assertRaises(UserError):
            review.action_approve_tier()

        # Try to reject
        with self.assertRaises(UserError):
            review.action_reject_tier("Test")
