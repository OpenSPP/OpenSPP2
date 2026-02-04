# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# AUTO-GENERATED from compliance.yaml - DO NOT EDIT MANUALLY
# Regenerate with: python -m scripts.compliance.test_generator spp_approval

"""
Access control compliance tests for spp_approval.

Generated from: spp_approval/security/compliance.yaml
Tests validate:
- Group hierarchy and implied_ids
- Model CRUD permissions per role
- Menu visibility per role
- Action access restrictions
"""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestComplianceBase(TransactionCase):
    """Base class for spp_approval compliance tests."""

    @classmethod
    def setUpClass(cls):
        """Set up test users with different roles."""
        super().setUpClass()

        # Helper to safely get reference
        def safe_ref(xml_id):
            try:
                return cls.env.ref(xml_id)
            except ValueError:
                return None

        # Store all role groups and users
        cls.role_groups = {}
        cls.role_users = {}

        # Viewer role
        cls.role_groups["viewer"] = safe_ref("spp_approval.group_approval_viewer")
        cls.role_users["viewer"] = cls._create_test_user("viewer", cls.role_groups["viewer"])

        # Officer role
        cls.role_groups["officer"] = safe_ref("spp_approval.group_approval_officer")
        cls.role_users["officer"] = cls._create_test_user("officer", cls.role_groups["officer"])

        # Manager role
        cls.role_groups["manager"] = safe_ref("spp_approval.group_approval_manager")
        cls.role_users["manager"] = cls._create_test_user("manager", cls.role_groups["manager"])

        # Approver role
        cls.role_groups["approver"] = safe_ref("spp_approval.group_approval_approver")
        cls.role_users["approver"] = cls._create_test_user("approver", cls.role_groups["approver"])

        # Read role
        cls.role_groups["read"] = safe_ref("spp_approval.group_approval_read")
        cls.role_users["read"] = cls._create_test_user("read", cls.role_groups["read"])

        # Write role
        cls.role_groups["write"] = safe_ref("spp_approval.group_approval_write")
        cls.role_users["write"] = cls._create_test_user("write", cls.role_groups["write"])

        # Admin role
        cls.role_groups["admin"] = safe_ref("spp_approval.group_approval_admin")
        cls.role_users["admin"] = cls._create_test_user("admin", cls.role_groups["admin"])

        # Backward-compatible aliases for standard roles
        cls.group_viewer = cls.role_groups.get("viewer")
        cls.group_officer = cls.role_groups.get("officer")
        cls.group_manager = cls.role_groups.get("manager")
        cls.user_viewer = cls.role_users.get("viewer")
        cls.user_officer = cls.role_users.get("officer")
        cls.user_manager = cls.role_users.get("manager")

        # Admin user
        admin_group = safe_ref("spp_security.group_spp_admin")
        cls.user_admin = cls._create_test_user("admin", admin_group)

    @classmethod
    def _create_test_user(cls, role, group):
        """Create a test user with the specified group."""
        if not group:
            return None
        return cls.env["res.users"].create(
            {
                "name": f"Test {role.title()}",
                "login": f"test_{role}_compliance",
                "email": f"{role}_compliance@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(group.id),
                ],
            }
        )

    def _get_user_for_role(self, role):
        """Get test user for a given role name."""
        return self.role_users.get(role)

    def _assert_access(self, model, user, perm, should_have):
        """Assert user has or doesn't have permission on model."""
        Model = self.env[model].with_user(user)
        has_access = Model.check_access_rights(perm, raise_exception=False)
        if should_have:
            self.assertTrue(has_access, f"{user.name} should have {perm} on {model}")
        else:
            self.assertFalse(has_access, f"{user.name} should NOT have {perm} on {model}")


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestGroupHierarchy(TestComplianceBase):
    """Test group hierarchy and implied_ids."""

    def test_manager_implies_officer(self):
        """Manager group should imply officer group."""
        if not self.user_manager or not self.group_officer:
            self.skipTest("Required groups not found")
        self.assertTrue(
            self.user_manager.has_group("spp_approval.group_approval_officer"),
            "Manager should have officer privileges",
        )

    def test_officer_implies_viewer(self):
        """Officer group should imply viewer group."""
        if not self.user_officer or not self.group_viewer:
            self.skipTest("Required groups not found")
        self.assertTrue(
            self.user_officer.has_group("spp_approval.group_approval_viewer"),
            "Officer should have viewer privileges",
        )

    def test_group_approval_write_implies(self):
        """Test group_approval_write implies correct groups."""
        group = self.env.ref("spp_approval.group_approval_write", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_approval_write not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_approval.group_approval_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id,
                implied_ids,
                "group_approval_write should imply group_approval_read",
            )

    def test_group_approval_viewer_implies(self):
        """Test group_approval_viewer implies correct groups."""
        group = self.env.ref("spp_approval.group_approval_viewer", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_approval_viewer not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_approval.group_approval_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id,
                implied_ids,
                "group_approval_viewer should imply group_approval_read",
            )

    def test_group_approval_officer_implies(self):
        """Test group_approval_officer implies correct groups."""
        group = self.env.ref("spp_approval.group_approval_officer", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_approval_officer not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_approval.group_approval_viewer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id,
                implied_ids,
                "group_approval_officer should imply group_approval_viewer",
            )
        implied_group = self.env.ref("spp_approval.group_approval_write", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id,
                implied_ids,
                "group_approval_officer should imply group_approval_write",
            )

    def test_group_approval_manager_implies(self):
        """Test group_approval_manager implies correct groups."""
        group = self.env.ref("spp_approval.group_approval_manager", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_approval_manager not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_approval.group_approval_officer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id,
                implied_ids,
                "group_approval_manager should imply group_approval_officer",
            )

    def test_group_approval_approver_implies(self):
        """Test group_approval_approver implies correct groups."""
        group = self.env.ref("spp_approval.group_approval_approver", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_approval_approver not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_approval.group_approval_viewer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id,
                implied_ids,
                "group_approval_approver should imply group_approval_viewer",
            )

    def test_group_approval_admin_implies(self):
        """Test group_approval_admin implies correct groups."""
        group = self.env.ref("spp_approval.group_approval_admin", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_approval_admin not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_approval.group_approval_manager", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id,
                implied_ids,
                "group_approval_admin should imply group_approval_manager",
            )


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestModelAccess(TestComplianceBase):
    """Test model CRUD permissions per role."""

    def test_spp_approval_definition_viewer_access(self):
        """Test viewer permissions on spp.approval.definition."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.approval.definition", user, "read", True)
        self._assert_access("spp.approval.definition", user, "write", False)
        self._assert_access("spp.approval.definition", user, "create", False)
        self._assert_access("spp.approval.definition", user, "unlink", False)

    def test_spp_approval_definition_officer_access(self):
        """Test officer permissions on spp.approval.definition."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.approval.definition", user, "read", True)
        self._assert_access("spp.approval.definition", user, "write", True)
        self._assert_access("spp.approval.definition", user, "create", True)
        self._assert_access("spp.approval.definition", user, "unlink", False)

    def test_spp_approval_definition_manager_access(self):
        """Test manager permissions on spp.approval.definition."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.approval.definition", user, "read", True)
        self._assert_access("spp.approval.definition", user, "write", True)
        self._assert_access("spp.approval.definition", user, "create", True)
        self._assert_access("spp.approval.definition", user, "unlink", True)

    def test_spp_approval_review_viewer_access(self):
        """Test viewer permissions on spp.approval.review."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.approval.review", user, "read", True)
        self._assert_access("spp.approval.review", user, "write", False)
        self._assert_access("spp.approval.review", user, "create", False)
        self._assert_access("spp.approval.review", user, "unlink", False)

    def test_spp_approval_review_manager_access(self):
        """Test manager permissions on spp.approval.review."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.approval.review", user, "read", True)
        self._assert_access("spp.approval.review", user, "write", True)
        self._assert_access("spp.approval.review", user, "create", True)
        self._assert_access("spp.approval.review", user, "unlink", True)

    def test_spp_approval_review_approver_access(self):
        """Test approver permissions on spp.approval.review."""
        user = self._get_user_for_role("approver")
        if not user:
            self.skipTest("Approver user not found")
        self._assert_access("spp.approval.review", user, "read", True)
        self._assert_access("spp.approval.review", user, "write", True)
        self._assert_access("spp.approval.review", user, "create", False)
        self._assert_access("spp.approval.review", user, "unlink", False)

    def test_spp_approval_config_viewer_access(self):
        """Test viewer permissions on spp.approval.config."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.approval.config", user, "read", True)
        self._assert_access("spp.approval.config", user, "write", False)
        self._assert_access("spp.approval.config", user, "create", False)
        self._assert_access("spp.approval.config", user, "unlink", False)

    def test_spp_approval_config_manager_access(self):
        """Test manager permissions on spp.approval.config."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.approval.config", user, "read", True)
        self._assert_access("spp.approval.config", user, "write", True)
        self._assert_access("spp.approval.config", user, "create", True)
        self._assert_access("spp.approval.config", user, "unlink", True)

    def test_spp_approval_freeze_viewer_access(self):
        """Test viewer permissions on spp.approval.freeze."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.approval.freeze", user, "read", True)
        self._assert_access("spp.approval.freeze", user, "write", False)
        self._assert_access("spp.approval.freeze", user, "create", False)
        self._assert_access("spp.approval.freeze", user, "unlink", False)

    def test_spp_approval_freeze_officer_access(self):
        """Test officer permissions on spp.approval.freeze."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.approval.freeze", user, "read", True)
        self._assert_access("spp.approval.freeze", user, "write", True)
        self._assert_access("spp.approval.freeze", user, "create", True)
        self._assert_access("spp.approval.freeze", user, "unlink", False)

    def test_spp_approval_freeze_manager_access(self):
        """Test manager permissions on spp.approval.freeze."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.approval.freeze", user, "read", True)
        self._assert_access("spp.approval.freeze", user, "write", True)
        self._assert_access("spp.approval.freeze", user, "create", True)
        self._assert_access("spp.approval.freeze", user, "unlink", True)

    def test_spp_approval_rejection_wizard_approver_access(self):
        """Test approver permissions on spp.approval.rejection.wizard."""
        user = self._get_user_for_role("approver")
        if not user:
            self.skipTest("Approver user not found")
        self._assert_access("spp.approval.rejection.wizard", user, "read", True)
        self._assert_access("spp.approval.rejection.wizard", user, "write", True)
        self._assert_access("spp.approval.rejection.wizard", user, "create", True)
        self._assert_access("spp.approval.rejection.wizard", user, "unlink", True)

    def test_spp_approval_revision_wizard_approver_access(self):
        """Test approver permissions on spp.approval.revision.wizard."""
        user = self._get_user_for_role("approver")
        if not user:
            self.skipTest("Approver user not found")
        self._assert_access("spp.approval.revision.wizard", user, "read", True)
        self._assert_access("spp.approval.revision.wizard", user, "write", True)
        self._assert_access("spp.approval.revision.wizard", user, "create", True)
        self._assert_access("spp.approval.revision.wizard", user, "unlink", True)


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestMenuVisibility(TestComplianceBase):
    """Test menu visibility per role."""

    def _menu_visible(self, menu_xml_id, user):
        """Check if menu is visible to user."""
        menu = self.env.ref(menu_xml_id, raise_if_not_found=False)
        if not menu:
            return None  # Menu not found
        # Get visible menus for user
        visible_menus = self.env["ir.ui.menu"].with_user(user).search([])
        return menu in visible_menus

    def test_menu_menu_approval_root_visibility(self):
        """Test visibility of menu Approvals."""
        if self.user_viewer:
            visible = self._menu_visible("spp_approval.menu_approval_root", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Approvals")
        if self.user_manager:
            visible = self._menu_visible("spp_approval.menu_approval_root", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Approvals")

    def test_menu_menu_my_approvals_visibility(self):
        """Test visibility of menu My Approvals."""
        if self.user_viewer:
            visible = self._menu_visible("spp_approval.menu_my_approvals", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see My Approvals")
        if self.user_manager:
            visible = self._menu_visible("spp_approval.menu_my_approvals", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see My Approvals")

    def test_menu_menu_my_pending_approvals_visibility(self):
        """Test visibility of menu Pending Approvals."""
        if self.user_viewer:
            visible = self._menu_visible("spp_approval.menu_my_pending_approvals", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Pending Approvals")
        if self.user_manager:
            visible = self._menu_visible("spp_approval.menu_my_pending_approvals", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Pending Approvals")

    def test_menu_menu_all_reviews_visibility(self):
        """Test visibility of menu All Reviews."""
        if self.user_viewer:
            visible = self._menu_visible("spp_approval.menu_all_reviews", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see All Reviews")
        if self.user_manager:
            visible = self._menu_visible("spp_approval.menu_all_reviews", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see All Reviews")

    def test_menu_menu_approval_config_visibility(self):
        """Test visibility of menu Configuration."""
        if self.user_viewer:
            visible = self._menu_visible("spp_approval.menu_approval_config", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Configuration")
        if self.user_manager:
            visible = self._menu_visible("spp_approval.menu_approval_config", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Configuration")

    def test_menu_menu_approval_definitions_visibility(self):
        """Test visibility of menu Approval Definitions."""
        if self.user_viewer:
            visible = self._menu_visible("spp_approval.menu_approval_definitions", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Approval Definitions")
        if self.user_manager:
            visible = self._menu_visible("spp_approval.menu_approval_definitions", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Approval Definitions")

    def test_menu_menu_approval_freeze_visibility(self):
        """Test visibility of menu Freeze Periods."""
        if self.user_viewer:
            visible = self._menu_visible("spp_approval.menu_approval_freeze", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Freeze Periods")
        if self.user_manager:
            visible = self._menu_visible("spp_approval.menu_approval_freeze", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Freeze Periods")


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestActionAccess(TestComplianceBase):
    """Test action access restrictions."""

    def _can_access_action(self, action_xml_id, user):
        """Check if user can access an action."""
        action = self.env.ref(action_xml_id, raise_if_not_found=False)
        if not action:
            return None
        # Check if user's groups intersect with action's groups
        if not action.group_ids:
            return True  # No restriction
        user_groups = user.group_ids
        return bool(action.group_ids & user_groups)

    def test_action_approval_review_my_pending_action_access(self):
        """Test access to action My Pending Approvals."""
        # Test viewer access
        if self.user_viewer:
            can_access = self._can_access_action("spp_approval.approval_review_my_pending_action", self.user_viewer)
            if can_access is not None:
                self.assertFalse(can_access, "Viewer should NOT access My Pending Approvals")

        # Test manager access
        if self.user_manager:
            can_access = self._can_access_action("spp_approval.approval_review_my_pending_action", self.user_manager)
            if can_access is not None:
                self.assertTrue(can_access, "Manager should access My Pending Approvals")

    def test_action_approval_review_action_access(self):
        """Test access to action All Approval Reviews."""
        # Test viewer access
        if self.user_viewer:
            can_access = self._can_access_action("spp_approval.approval_review_action", self.user_viewer)
            if can_access is not None:
                self.assertFalse(can_access, "Viewer should NOT access All Approval Reviews")

        # Test manager access
        if self.user_manager:
            can_access = self._can_access_action("spp_approval.approval_review_action", self.user_manager)
            if can_access is not None:
                self.assertTrue(can_access, "Manager should access All Approval Reviews")

    def test_action_approval_definition_action_access(self):
        """Test access to action Approval Definitions."""
        # Test viewer access
        if self.user_viewer:
            can_access = self._can_access_action("spp_approval.approval_definition_action", self.user_viewer)
            if can_access is not None:
                self.assertFalse(can_access, "Viewer should NOT access Approval Definitions")

        # Test manager access
        if self.user_manager:
            can_access = self._can_access_action("spp_approval.approval_definition_action", self.user_manager)
            if can_access is not None:
                self.assertTrue(can_access, "Manager should access Approval Definitions")

    def test_action_approval_freeze_action_access(self):
        """Test access to action Freeze Periods."""
        # Test viewer access
        if self.user_viewer:
            can_access = self._can_access_action("spp_approval.approval_freeze_action", self.user_viewer)
            if can_access is not None:
                self.assertFalse(can_access, "Viewer should NOT access Freeze Periods")

        # Test manager access
        if self.user_manager:
            can_access = self._can_access_action("spp_approval.approval_freeze_action", self.user_manager)
            if can_access is not None:
                self.assertTrue(can_access, "Manager should access Freeze Periods")


@tagged("post_install", "-at_install", "access_control", "compliance", "record_rules")
class TestRecordRules(TestComplianceBase):
    """Test record rules (data visibility filtering).

    These tests verify that users can only see records they are allowed
    to see based on ir.rule domain filters.
    """

    def _rule_exists(self, rule_xml_id):
        """Check if a record rule exists."""
        return bool(self.env.ref(rule_xml_id, raise_if_not_found=False))

    def _get_rule(self, rule_xml_id):
        """Get a record rule by XML ID."""
        return self.env.ref(rule_xml_id, raise_if_not_found=False)

    def test_rule_rule_spp_approval_review_approver_exists(self):
        """Test record rule rule_spp_approval_review_approver exists and is configured."""
        rule = self._get_rule("spp_approval.rule_spp_approval_review_approver")
        if not rule:
            self.skipTest("Rule rule_spp_approval_review_approver not found")

        # Verify rule model
        self.assertEqual(
            rule.model_id.model,
            "spp.approval.review",
            "Rule should be for model spp.approval.review",
        )

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, False)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_approval_review_approver_groups(self):
        """Test record rule rule_spp_approval_review_approver is assigned to correct groups."""
        rule = self._get_rule("spp_approval.rule_spp_approval_review_approver")
        if not rule:
            self.skipTest("Rule rule_spp_approval_review_approver not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_approval.group_approval_approver", raise_if_not_found=False)
        if expected_group:
            self.assertIn(
                expected_group,
                rule.groups,
                "Rule should include group group_approval_approver",
            )

    def test_rule_rule_spp_approval_review_manager_exists(self):
        """Test record rule rule_spp_approval_review_manager exists and is configured."""
        rule = self._get_rule("spp_approval.rule_spp_approval_review_manager")
        if not rule:
            self.skipTest("Rule rule_spp_approval_review_manager not found")

        # Verify rule model
        self.assertEqual(
            rule.model_id.model,
            "spp.approval.review",
            "Rule should be for model spp.approval.review",
        )

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_approval_review_manager_groups(self):
        """Test record rule rule_spp_approval_review_manager is assigned to correct groups."""
        rule = self._get_rule("spp_approval.rule_spp_approval_review_manager")
        if not rule:
            self.skipTest("Rule rule_spp_approval_review_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_approval.group_approval_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(
                expected_group,
                rule.groups,
                "Rule should include group group_approval_manager",
            )

    def test_rule_rule_spp_approval_definition_company_exists(self):
        """Test record rule rule_spp_approval_definition_company exists and is configured."""
        rule = self._get_rule("spp_approval.rule_spp_approval_definition_company")
        if not rule:
            self.skipTest("Rule rule_spp_approval_definition_company not found")

        # Verify rule model
        self.assertEqual(
            rule.model_id.model,
            "spp.approval.definition",
            "Rule should be for model spp.approval.definition",
        )

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_approval_freeze_company_exists(self):
        """Test record rule rule_spp_approval_freeze_company exists and is configured."""
        rule = self._get_rule("spp_approval.rule_spp_approval_freeze_company")
        if not rule:
            self.skipTest("Rule rule_spp_approval_freeze_company not found")

        # Verify rule model
        self.assertEqual(
            rule.model_id.model,
            "spp.approval.freeze",
            "Rule should be for model spp.approval.freeze",
        )

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestAdminLinkage(TestComplianceBase):
    """Test that admin group inherits manager permissions."""

    def test_admin_has_manager_group(self):
        """Test admin user has group_approval_manager permissions."""
        if not self.user_admin:
            self.skipTest("Admin user not created")
        self.assertTrue(
            self.user_admin.has_group("spp_approval.group_approval_manager"),
            "Admin should have group_approval_manager permissions",
        )

    def test_admin_group_implies_manager(self):
        """Test spp_security.group_spp_admin implies group_approval_manager."""
        admin_group = self.env.ref("spp_security.group_spp_admin", raise_if_not_found=False)
        manager_group = self.env.ref("spp_approval.group_approval_manager", raise_if_not_found=False)
        if not admin_group or not manager_group:
            self.skipTest("Required groups not found")

        # Check implied_ids (direct or transitive)
        def get_all_implied(group, visited=None):
            """Recursively get all implied groups."""
            if visited is None:
                visited = set()
            if group.id in visited:
                return set()
            visited.add(group.id)
            result = set(group.implied_ids.ids)
            for implied in group.implied_ids:
                result |= get_all_implied(implied, visited)
            return result

        all_implied = get_all_implied(admin_group)
        self.assertIn(
            manager_group.id,
            all_implied,
            "Admin group should imply group_approval_manager (directly or transitively)",
        )
