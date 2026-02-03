# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# AUTO-GENERATED from compliance.yaml - DO NOT EDIT MANUALLY
# Regenerate with: python -m scripts.compliance.test_generator spp_vocabulary

"""
Access control compliance tests for spp_vocabulary.

Generated from: spp_vocabulary/security/compliance.yaml
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
    """Base class for spp_vocabulary compliance tests."""

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
        cls.role_groups["viewer"] = safe_ref("spp_vocabulary.group_vocabulary_viewer")
        cls.role_users["viewer"] = cls._create_test_user("viewer", cls.role_groups["viewer"])

        # Officer role
        cls.role_groups["officer"] = safe_ref("spp_vocabulary.group_vocabulary_officer")
        cls.role_users["officer"] = cls._create_test_user("officer", cls.role_groups["officer"])

        # Manager role
        cls.role_groups["manager"] = safe_ref("spp_vocabulary.group_vocabulary_manager")
        cls.role_users["manager"] = cls._create_test_user("manager", cls.role_groups["manager"])

        # Read role
        cls.role_groups["read"] = safe_ref("spp_vocabulary.group_vocabulary_read")
        cls.role_users["read"] = cls._create_test_user("read", cls.role_groups["read"])

        # Write role
        cls.role_groups["write"] = safe_ref("spp_vocabulary.group_vocabulary_write")
        cls.role_users["write"] = cls._create_test_user("write", cls.role_groups["write"])

        # Create role
        cls.role_groups["create"] = safe_ref("spp_vocabulary.group_vocabulary_create")
        cls.role_users["create"] = cls._create_test_user("create", cls.role_groups["create"])

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
            self.user_manager.has_group("spp_vocabulary.group_vocabulary_officer"),
            "Manager should have officer privileges",
        )

    def test_officer_implies_viewer(self):
        """Officer group should imply viewer group."""
        if not self.user_officer or not self.group_viewer:
            self.skipTest("Required groups not found")
        self.assertTrue(
            self.user_officer.has_group("spp_vocabulary.group_vocabulary_viewer"),
            "Officer should have viewer privileges",
        )

    def test_group_vocabulary_write_implies(self):
        """Test group_vocabulary_write implies correct groups."""
        group = self.env.ref("spp_vocabulary.group_vocabulary_write", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_vocabulary_write not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_vocabulary.group_vocabulary_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_vocabulary_write should imply group_vocabulary_read")

    def test_group_vocabulary_create_implies(self):
        """Test group_vocabulary_create implies correct groups."""
        group = self.env.ref("spp_vocabulary.group_vocabulary_create", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_vocabulary_create not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_vocabulary.group_vocabulary_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_vocabulary_create should imply group_vocabulary_read")

    def test_group_vocabulary_viewer_implies(self):
        """Test group_vocabulary_viewer implies correct groups."""
        group = self.env.ref("spp_vocabulary.group_vocabulary_viewer", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_vocabulary_viewer not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_vocabulary.group_vocabulary_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_vocabulary_viewer should imply group_vocabulary_read")

    def test_group_vocabulary_officer_implies(self):
        """Test group_vocabulary_officer implies correct groups."""
        group = self.env.ref("spp_vocabulary.group_vocabulary_officer", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_vocabulary_officer not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_vocabulary.group_vocabulary_viewer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id, implied_ids, "group_vocabulary_officer should imply group_vocabulary_viewer"
            )
        implied_group = self.env.ref("spp_vocabulary.group_vocabulary_write", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_vocabulary_officer should imply group_vocabulary_write")
        implied_group = self.env.ref("spp_vocabulary.group_vocabulary_create", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id, implied_ids, "group_vocabulary_officer should imply group_vocabulary_create"
            )

    def test_group_vocabulary_manager_implies(self):
        """Test group_vocabulary_manager implies correct groups."""
        group = self.env.ref("spp_vocabulary.group_vocabulary_manager", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_vocabulary_manager not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_vocabulary.group_vocabulary_officer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(
                implied_group.id, implied_ids, "group_vocabulary_manager should imply group_vocabulary_officer"
            )


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestModelAccess(TestComplianceBase):
    """Test model CRUD permissions per role."""

    def test_spp_vocabulary_viewer_access(self):
        """Test viewer permissions on spp.vocabulary."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.vocabulary", user, "read", True)
        self._assert_access("spp.vocabulary", user, "write", False)
        self._assert_access("spp.vocabulary", user, "create", False)
        self._assert_access("spp.vocabulary", user, "unlink", False)

    def test_spp_vocabulary_officer_access(self):
        """Test officer permissions on spp.vocabulary."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.vocabulary", user, "read", True)
        self._assert_access("spp.vocabulary", user, "write", True)
        self._assert_access("spp.vocabulary", user, "create", True)
        self._assert_access("spp.vocabulary", user, "unlink", False)

    def test_spp_vocabulary_manager_access(self):
        """Test manager permissions on spp.vocabulary."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.vocabulary", user, "read", True)
        self._assert_access("spp.vocabulary", user, "write", True)
        self._assert_access("spp.vocabulary", user, "create", True)
        self._assert_access("spp.vocabulary", user, "unlink", True)

    def test_spp_vocabulary_code_viewer_access(self):
        """Test viewer permissions on spp.vocabulary.code."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.vocabulary.code", user, "read", True)
        self._assert_access("spp.vocabulary.code", user, "write", False)
        self._assert_access("spp.vocabulary.code", user, "create", False)
        self._assert_access("spp.vocabulary.code", user, "unlink", False)

    def test_spp_vocabulary_code_officer_access(self):
        """Test officer permissions on spp.vocabulary.code."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.vocabulary.code", user, "read", True)
        self._assert_access("spp.vocabulary.code", user, "write", True)
        self._assert_access("spp.vocabulary.code", user, "create", True)
        self._assert_access("spp.vocabulary.code", user, "unlink", False)

    def test_spp_vocabulary_code_manager_access(self):
        """Test manager permissions on spp.vocabulary.code."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.vocabulary.code", user, "read", True)
        self._assert_access("spp.vocabulary.code", user, "write", True)
        self._assert_access("spp.vocabulary.code", user, "create", True)
        self._assert_access("spp.vocabulary.code", user, "unlink", True)

    def test_spp_vocabulary_mapping_viewer_access(self):
        """Test viewer permissions on spp.vocabulary.mapping."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.vocabulary.mapping", user, "read", True)
        self._assert_access("spp.vocabulary.mapping", user, "write", False)
        self._assert_access("spp.vocabulary.mapping", user, "create", False)
        self._assert_access("spp.vocabulary.mapping", user, "unlink", False)

    def test_spp_vocabulary_mapping_officer_access(self):
        """Test officer permissions on spp.vocabulary.mapping."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.vocabulary.mapping", user, "read", True)
        self._assert_access("spp.vocabulary.mapping", user, "write", True)
        self._assert_access("spp.vocabulary.mapping", user, "create", True)
        self._assert_access("spp.vocabulary.mapping", user, "unlink", False)

    def test_spp_vocabulary_mapping_manager_access(self):
        """Test manager permissions on spp.vocabulary.mapping."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.vocabulary.mapping", user, "read", True)
        self._assert_access("spp.vocabulary.mapping", user, "write", True)
        self._assert_access("spp.vocabulary.mapping", user, "create", True)
        self._assert_access("spp.vocabulary.mapping", user, "unlink", True)


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

    def test_menu_menu_vocabulary_root_visibility(self):
        """Test visibility of menu Vocabularies."""
        if self.user_viewer:
            visible = self._menu_visible("spp_vocabulary.menu_vocabulary_root", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Vocabularies")
        if self.user_manager:
            visible = self._menu_visible("spp_vocabulary.menu_vocabulary_root", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Vocabularies")

    def test_menu_menu_vocabulary_visibility(self):
        """Test visibility of menu Manage Vocabularies."""
        if self.user_viewer:
            visible = self._menu_visible("spp_vocabulary.menu_vocabulary", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Manage Vocabularies")
        if self.user_manager:
            visible = self._menu_visible("spp_vocabulary.menu_vocabulary", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Manage Vocabularies")

    def test_menu_menu_vocabulary_code_visibility(self):
        """Test visibility of menu All Codes."""
        if self.user_viewer:
            visible = self._menu_visible("spp_vocabulary.menu_vocabulary_code", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see All Codes")
        if self.user_manager:
            visible = self._menu_visible("spp_vocabulary.menu_vocabulary_code", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see All Codes")

    def test_menu_menu_vocabulary_mapping_visibility(self):
        """Test visibility of menu Code Mappings."""
        if self.user_viewer:
            visible = self._menu_visible("spp_vocabulary.menu_vocabulary_mapping", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Code Mappings")
        if self.user_manager:
            visible = self._menu_visible("spp_vocabulary.menu_vocabulary_mapping", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Code Mappings")


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

    def test_rule_rule_vocabulary_global_read_exists(self):
        """Test record rule rule_vocabulary_global_read exists and is configured."""
        rule = self._get_rule("spp_vocabulary.rule_vocabulary_global_read")
        if not rule:
            self.skipTest("Rule rule_vocabulary_global_read not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.vocabulary", "Rule should be for model spp.vocabulary")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, False)
        self.assertEqual(rule.perm_create, False)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_vocabulary_code_global_read_exists(self):
        """Test record rule rule_vocabulary_code_global_read exists and is configured."""
        rule = self._get_rule("spp_vocabulary.rule_vocabulary_code_global_read")
        if not rule:
            self.skipTest("Rule rule_vocabulary_code_global_read not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.vocabulary.code", "Rule should be for model spp.vocabulary.code")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, False)
        self.assertEqual(rule.perm_create, False)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_vocabulary_mapping_global_read_exists(self):
        """Test record rule rule_vocabulary_mapping_global_read exists and is configured."""
        rule = self._get_rule("spp_vocabulary.rule_vocabulary_mapping_global_read")
        if not rule:
            self.skipTest("Rule rule_vocabulary_mapping_global_read not found")

        # Verify rule model
        self.assertEqual(
            rule.model_id.model, "spp.vocabulary.mapping", "Rule should be for model spp.vocabulary.mapping"
        )

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, False)
        self.assertEqual(rule.perm_create, False)
        self.assertEqual(rule.perm_unlink, False)


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestAdminLinkage(TestComplianceBase):
    """Test that admin group inherits manager permissions."""

    def test_admin_has_manager_group(self):
        """Test admin user has group_vocabulary_manager permissions."""
        if not self.user_admin:
            self.skipTest("Admin user not created")
        self.assertTrue(
            self.user_admin.has_group("spp_vocabulary.group_vocabulary_manager"),
            "Admin should have group_vocabulary_manager permissions",
        )

    def test_admin_group_implies_manager(self):
        """Test spp_security.group_spp_admin implies group_vocabulary_manager."""
        admin_group = self.env.ref("spp_security.group_spp_admin", raise_if_not_found=False)
        manager_group = self.env.ref("spp_vocabulary.group_vocabulary_manager", raise_if_not_found=False)
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
            "Admin group should imply group_vocabulary_manager (directly or transitively)",
        )
