from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApprovalDefinition(TransactionCase):
    """Test cases for the approval definition model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test users
        cls.user_approver = cls.env["res.users"].create(
            {
                "name": "Test Approver",
                "login": "test_approver_def",
                "email": "approver_def@test.com",
            }
        )

        cls.user_approver2 = cls.env["res.users"].create(
            {
                "name": "Test Approver 2",
                "login": "test_approver_def2",
                "email": "approver_def2@test.com",
            }
        )

        cls.user_manager = cls.env["res.users"].create(
            {
                "name": "Test Manager User",
                "login": "test_manager_user",
                "email": "manager@test.com",
            }
        )

        # Create test group
        cls.test_group = cls.env["res.groups"].create(
            {
                "name": "Test Approval Group",
                "user_ids": [Command.link(cls.user_approver.id)],
            }
        )

        # Create test company
        cls.test_company = cls.env["res.company"].create(
            {
                "name": "Test Company",
            }
        )

    # === Creation Tests ===

    def test_definition_creation_user_type(self):
        """Test creating a definition with user-based approval."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "User Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
            }
        )

        self.assertTrue(definition.active)
        self.assertEqual(definition.approval_type, "user")
        self.assertIn(self.user_approver, definition.approval_user_ids)
        self.assertEqual(definition.sequence, 10)

    def test_definition_creation_group_type(self):
        """Test creating a definition with group-based approval."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Group Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "group",
                "approval_group_id": self.test_group.id,
            }
        )

        self.assertEqual(definition.approval_type, "group")
        self.assertEqual(definition.approval_group_id, self.test_group)

    def test_definition_creation_manager_type(self):
        """Test creating a definition with manager-based approval."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Manager Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "manager",
            }
        )

        self.assertEqual(definition.approval_type, "manager")

    def test_definition_creation_field_type(self):
        """Test creating a definition with field-based approval."""
        # Get a user field from res.partner
        user_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", self.env.ref("base.model_res_partner").id),
                ("name", "=", "user_id"),
            ],
            limit=1,
        )

        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Field Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "field",
                "approval_field_id": user_field.id,
            }
        )

        self.assertEqual(definition.approval_type, "field")
        self.assertEqual(definition.approval_field_id, user_field)

    # === Validation Tests ===

    def test_definition_validation_missing_user(self):
        """Test that user type requires approval_user_ids."""
        with self.assertRaises(ValidationError):
            self.env["spp.approval.definition"].create(
                {
                    "name": "Invalid User Approval",
                    "model_id": self.env.ref("base.model_res_partner").id,
                    "approval_type": "user",
                    # Missing approval_user_ids
                }
            )

    def test_definition_validation_missing_group(self):
        """Test that group type requires approval_group_id."""
        with self.assertRaises(ValidationError):
            self.env["spp.approval.definition"].create(
                {
                    "name": "Invalid Group Approval",
                    "model_id": self.env.ref("base.model_res_partner").id,
                    "approval_type": "group",
                    # Missing approval_group_id
                }
            )

    def test_definition_validation_missing_field(self):
        """Test that field type requires approval_field_id."""
        with self.assertRaises(ValidationError):
            self.env["spp.approval.definition"].create(
                {
                    "name": "Invalid Field Approval",
                    "model_id": self.env.ref("base.model_res_partner").id,
                    "approval_type": "field",
                    # Missing approval_field_id
                }
            )

    def test_definition_invalid_domain(self):
        """Test that invalid domain syntax raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.approval.definition"].create(
                {
                    "name": "Invalid Domain",
                    "model_id": self.env.ref("base.model_res_partner").id,
                    "approval_type": "user",
                    "approval_user_ids": [Command.link(self.user_approver.id)],
                    "domain": "not a valid domain",
                }
            )

    def test_definition_valid_domain(self):
        """Test that valid domain syntax is accepted."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "With Domain",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "domain": "[('is_company', '=', True)]",
            }
        )

        self.assertEqual(definition.domain, "[('is_company', '=', True)]")

    # === get_approvers Tests ===

    def test_get_approvers_user_type(self):
        """Test getting approvers for user type definition."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "User Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
            }
        )

        partner = self.env["res.partner"].create({"name": "Test Partner"})
        approvers = definition.get_approvers(partner)

        self.assertEqual(len(approvers), 1)
        self.assertIn(self.user_approver, approvers)

    def test_get_approvers_user_type_multiple(self):
        """Test getting multiple approvers for user type definition."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "User Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [
                    Command.link(self.user_approver.id),
                    Command.link(self.user_approver2.id),
                ],
            }
        )

        partner = self.env["res.partner"].create({"name": "Test Partner"})
        approvers = definition.get_approvers(partner)

        self.assertEqual(len(approvers), 2)
        self.assertIn(self.user_approver, approvers)
        self.assertIn(self.user_approver2, approvers)

    def test_get_approvers_group_type(self):
        """Test getting approvers for group type definition."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Group Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "group",
                "approval_group_id": self.test_group.id,
            }
        )

        partner = self.env["res.partner"].create({"name": "Test Partner"})
        approvers = definition.get_approvers(partner)

        self.assertIn(self.user_approver, approvers)

    def test_get_approvers_manager_type_no_employee(self):
        """Test getting approvers for manager type when user has no employee."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Manager Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "manager",
            }
        )

        # Create partner (user doesn't need special permissions for this test)
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        approvers = definition.get_approvers(partner)

        # Should return empty recordset
        self.assertEqual(len(approvers), 0)

    def test_get_approvers_field_type(self):
        """Test getting approvers for field type definition."""
        # Get user_id field from res.partner
        user_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", self.env.ref("base.model_res_partner").id),
                ("name", "=", "user_id"),
            ],
            limit=1,
        )

        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Field Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "field",
                "approval_field_id": user_field.id,
            }
        )

        partner = self.env["res.partner"].create({"name": "Test Partner", "user_id": self.user_approver.id})
        approvers = definition.get_approvers(partner)

        self.assertEqual(len(approvers), 1)
        self.assertIn(self.user_approver, approvers)

    def test_get_approvers_field_type_no_value(self):
        """Test getting approvers for field type when field is empty."""
        user_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", self.env.ref("base.model_res_partner").id),
                ("name", "=", "user_id"),
            ],
            limit=1,
        )

        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Field Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "field",
                "approval_field_id": user_field.id,
            }
        )

        partner = self.env["res.partner"].create({"name": "Test Partner"})
        approvers = definition.get_approvers(partner)

        # Should return empty recordset
        self.assertEqual(len(approvers), 0)

    # === matches_record Tests ===

    def test_matches_record_empty_domain(self):
        """Test that empty domain matches all records."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "No Domain",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
            }
        )

        partner = self.env["res.partner"].create({"name": "Test Partner"})
        self.assertTrue(definition.matches_record(partner))

    def test_matches_record_with_domain_match(self):
        """Test that domain filters records correctly - matching case."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Company Only",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "domain": "[('is_company', '=', True)]",
            }
        )

        # Create a company
        company_partner = self.env["res.partner"].create({"name": "Test Company", "is_company": True})

        self.assertTrue(definition.matches_record(company_partner))

    def test_matches_record_with_domain_no_match(self):
        """Test that domain filters records correctly - non-matching case."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Company Only",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "domain": "[('is_company', '=', True)]",
            }
        )

        # Create an individual
        individual_partner = self.env["res.partner"].create({"name": "Test Individual", "is_company": False})

        self.assertFalse(definition.matches_record(individual_partner))

    def test_matches_record_complex_domain(self):
        """Test complex domain with multiple conditions."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Complex Domain",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "domain": "[('is_company', '=', True), ('active', '=', True)]",
            }
        )

        # Create matching partner
        matching_partner = self.env["res.partner"].create(
            {"name": "Active Company", "is_company": True, "active": True}
        )

        # Create non-matching partner
        non_matching_partner = self.env["res.partner"].create(
            {"name": "Inactive Company", "is_company": True, "active": False}
        )

        self.assertTrue(definition.matches_record(matching_partner))
        self.assertFalse(definition.matches_record(non_matching_partner))

    # === get_definitions_for_model Tests ===

    def test_get_definitions_for_model_basic(self):
        """Test fetching definitions for a specific model."""
        # Create definitions for different models
        definition1 = self.env["spp.approval.definition"].create(
            {
                "name": "Partner Approval 1",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "sequence": 10,
            }
        )
        definition2 = self.env["spp.approval.definition"].create(
            {
                "name": "Partner Approval 2",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "sequence": 20,
            }
        )

        # Create definition for different model (should not be returned)
        self.env["spp.approval.definition"].create(
            {
                "name": "User Approval",
                "model_id": self.env.ref("base.model_res_users").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
            }
        )

        definitions = self.env["spp.approval.definition"].get_definitions_for_model("res.partner")

        self.assertIn(definition1, definitions)
        self.assertIn(definition2, definitions)
        self.assertEqual(len(definitions), 2)

    def test_get_definitions_for_model_ordering(self):
        """Test definitions are returned in sequence order."""
        definition1 = self.env["spp.approval.definition"].create(
            {
                "name": "Partner Approval 1",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "sequence": 20,
            }
        )
        definition2 = self.env["spp.approval.definition"].create(
            {
                "name": "Partner Approval 2",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "sequence": 10,
            }
        )

        definitions = self.env["spp.approval.definition"].get_definitions_for_model("res.partner")

        # Should be ordered by sequence
        self.assertEqual(definitions[0], definition2)  # sequence 10
        self.assertEqual(definitions[1], definition1)  # sequence 20

    def test_get_definitions_for_model_inactive_excluded(self):
        """Test that inactive definitions are excluded."""
        active_definition = self.env["spp.approval.definition"].create(
            {
                "name": "Active Definition",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "active": True,
            }
        )
        inactive_definition = self.env["spp.approval.definition"].create(
            {
                "name": "Inactive Definition",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "active": False,
            }
        )

        definitions = self.env["spp.approval.definition"].get_definitions_for_model("res.partner")

        self.assertIn(active_definition, definitions)
        self.assertNotIn(inactive_definition, definitions)

    def test_get_definitions_for_model_with_company(self):
        """Test company filtering in get_definitions_for_model."""
        # Create definition for specific company
        company_definition = self.env["spp.approval.definition"].create(
            {
                "name": "Company Specific",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "company_id": self.test_company.id,
            }
        )

        # Create definition without company (global)
        global_definition = self.env["spp.approval.definition"].create(
            {
                "name": "Global",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "company_id": False,
            }
        )

        # Get definitions for the test company
        definitions = self.env["spp.approval.definition"].get_definitions_for_model(
            "res.partner", company_id=self.test_company.id
        )

        # Should include both company-specific and global definitions
        self.assertIn(company_definition, definitions)
        self.assertIn(global_definition, definitions)

        # Get definitions for different company
        other_company = self.env["res.company"].create({"name": "Other Company"})
        definitions = self.env["spp.approval.definition"].get_definitions_for_model(
            "res.partner", company_id=other_company.id
        )

        # Should only include global definition
        self.assertNotIn(company_definition, definitions)
        self.assertIn(global_definition, definitions)

    # === SLA Configuration Tests ===

    def test_sla_configuration(self):
        """Test SLA configuration on definition."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "SLA Approval",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "sla_days": 5,
            }
        )

        self.assertEqual(definition.sla_days, 5)

    def test_sla_escalation(self):
        """Test SLA escalation configuration."""
        escalation_definition = self.env["spp.approval.definition"].create(
            {
                "name": "Escalation Definition",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [(4, self.user_manager.id)],
            }
        )

        definition = self.env["spp.approval.definition"].create(
            {
                "name": "SLA with Escalation",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "sla_days": 3,
                "escalation_definition_id": escalation_definition.id,
            }
        )

        self.assertEqual(definition.sla_days, 3)
        self.assertEqual(definition.escalation_definition_id, escalation_definition)

    # === Behavior Settings Tests ===

    def test_freeze_settings(self):
        """Test freeze and emergency settings."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Freeze Test",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "is_respect_system_freeze": True,
                "is_emergency_bypass_allowed": True,
            }
        )

        self.assertTrue(definition.is_respect_system_freeze)
        self.assertTrue(definition.is_emergency_bypass_allowed)

    def test_auto_approve_setting(self):
        """Test auto-approve same user setting."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Auto Approve Test",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "auto_approve_same_user": True,
            }
        )

        self.assertTrue(definition.auto_approve_same_user)

    def test_notification_settings(self):
        """Test notification configuration."""
        definition = self.env["spp.approval.definition"].create(
            {
                "name": "Notification Test",
                "model_id": self.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
                "notify_on_submit": True,
                "notify_on_approve": True,
                "notify_on_reject": True,
                "is_require_comment": True,
            }
        )

        self.assertTrue(definition.notify_on_submit)
        self.assertTrue(definition.notify_on_approve)
        self.assertTrue(definition.notify_on_reject)
        self.assertTrue(definition.is_require_comment)
