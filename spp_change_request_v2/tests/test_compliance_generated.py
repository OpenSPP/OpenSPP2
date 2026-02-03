# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# AUTO-GENERATED from compliance.yaml - DO NOT EDIT MANUALLY
# Regenerate with: python -m scripts.compliance.test_generator spp_change_request_v2

"""
Access control compliance tests for spp_change_request_v2.

Generated from: spp_change_request_v2/security/compliance.yaml
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
    """Base class for spp_change_request_v2 compliance tests."""

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
        cls.role_groups["viewer"] = safe_ref("spp_change_request_v2.group_change_request_viewer")
        cls.role_users["viewer"] = cls._create_test_user("viewer", cls.role_groups["viewer"])

        # Officer role
        cls.role_groups["officer"] = safe_ref("spp_change_request_v2.group_change_request_officer")
        cls.role_users["officer"] = cls._create_test_user("officer", cls.role_groups["officer"])

        # Manager role
        cls.role_groups["manager"] = safe_ref("spp_change_request_v2.group_change_request_manager")
        cls.role_users["manager"] = cls._create_test_user("manager", cls.role_groups["manager"])

        # User role
        cls.role_groups["user"] = safe_ref("spp_change_request_v2.group_change_request_user")
        cls.role_users["user"] = cls._create_test_user("user", cls.role_groups["user"])

        # Validator role
        cls.role_groups["validator"] = safe_ref("spp_change_request_v2.group_change_request_validator")
        cls.role_users["validator"] = cls._create_test_user("validator", cls.role_groups["validator"])

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
            self.user_manager.has_group("spp_change_request_v2.group_change_request_officer"),
            "Manager should have officer privileges",
        )

    def test_officer_implies_viewer(self):
        """Officer group should imply viewer group."""
        if not self.user_officer or not self.group_viewer:
            self.skipTest("Required groups not found")
        self.assertTrue(
            self.user_officer.has_group("spp_change_request_v2.group_change_request_viewer"),
            "Officer should have viewer privileges",
        )

    def test_group_cr_write_implies(self):
        """Test group_cr_write implies correct groups."""
        group = self.env.ref("spp_change_request_v2.group_cr_write", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_cr_write not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_change_request_v2.group_cr_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_cr_write should imply group_cr_read")

    def test_group_cr_user_implies(self):
        """Test group_cr_user implies correct groups."""
        group = self.env.ref("spp_change_request_v2.group_cr_user", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_cr_user not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_change_request_v2.group_cr_write", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_cr_user should imply group_cr_write")

    def test_group_cr_validator_implies(self):
        """Test group_cr_validator implies correct groups."""
        group = self.env.ref("spp_change_request_v2.group_cr_validator", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_cr_validator not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_change_request_v2.group_cr_user", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_cr_validator should imply group_cr_user")

    def test_group_cr_manager_implies(self):
        """Test group_cr_manager implies correct groups."""
        group = self.env.ref("spp_change_request_v2.group_cr_manager", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_cr_manager not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_change_request_v2.group_cr_validator", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_cr_manager should imply group_cr_validator")


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestModelAccess(TestComplianceBase):
    """Test model CRUD permissions per role."""

    def test_spp_change_request_type_manager_access(self):
        """Test manager permissions on spp.change.request.type."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.change.request.type", user, "read", True)
        self._assert_access("spp.change.request.type", user, "write", True)
        self._assert_access("spp.change.request.type", user, "create", True)
        self._assert_access("spp.change.request.type", user, "unlink", True)

    def test_spp_change_request_type_user_access(self):
        """Test user permissions on spp.change.request.type."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.change.request.type", user, "read", True)
        self._assert_access("spp.change.request.type", user, "write", False)
        self._assert_access("spp.change.request.type", user, "create", False)
        self._assert_access("spp.change.request.type", user, "unlink", False)

    def test_spp_change_request_type_validator_access(self):
        """Test validator permissions on spp.change.request.type."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.change.request.type", user, "read", True)
        self._assert_access("spp.change.request.type", user, "write", False)
        self._assert_access("spp.change.request.type", user, "create", False)
        self._assert_access("spp.change.request.type", user, "unlink", False)

    def test_spp_change_request_type_mapping_manager_access(self):
        """Test manager permissions on spp.change.request.type.mapping."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.change.request.type.mapping", user, "read", True)
        self._assert_access("spp.change.request.type.mapping", user, "write", True)
        self._assert_access("spp.change.request.type.mapping", user, "create", True)
        self._assert_access("spp.change.request.type.mapping", user, "unlink", True)

    def test_spp_change_request_type_mapping_user_access(self):
        """Test user permissions on spp.change.request.type.mapping."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.change.request.type.mapping", user, "read", True)
        self._assert_access("spp.change.request.type.mapping", user, "write", False)
        self._assert_access("spp.change.request.type.mapping", user, "create", False)
        self._assert_access("spp.change.request.type.mapping", user, "unlink", False)

    def test_spp_change_request_type_mapping_validator_access(self):
        """Test validator permissions on spp.change.request.type.mapping."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.change.request.type.mapping", user, "read", True)
        self._assert_access("spp.change.request.type.mapping", user, "write", False)
        self._assert_access("spp.change.request.type.mapping", user, "create", False)
        self._assert_access("spp.change.request.type.mapping", user, "unlink", False)

    def test_spp_change_request_manager_access(self):
        """Test manager permissions on spp.change.request."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.change.request", user, "read", True)
        self._assert_access("spp.change.request", user, "write", True)
        self._assert_access("spp.change.request", user, "create", True)
        self._assert_access("spp.change.request", user, "unlink", True)

    def test_spp_change_request_user_access(self):
        """Test user permissions on spp.change.request."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.change.request", user, "read", True)
        self._assert_access("spp.change.request", user, "write", True)
        self._assert_access("spp.change.request", user, "create", True)
        self._assert_access("spp.change.request", user, "unlink", False)

    def test_spp_change_request_validator_access(self):
        """Test validator permissions on spp.change.request."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.change.request", user, "read", True)
        self._assert_access("spp.change.request", user, "write", True)
        self._assert_access("spp.change.request", user, "create", True)
        self._assert_access("spp.change.request", user, "unlink", False)

    def test_spp_cr_detail_add_member_manager_access(self):
        """Test manager permissions on spp.cr.detail.add_member."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.add_member", user, "read", True)
        self._assert_access("spp.cr.detail.add_member", user, "write", True)
        self._assert_access("spp.cr.detail.add_member", user, "create", True)
        self._assert_access("spp.cr.detail.add_member", user, "unlink", True)

    def test_spp_cr_detail_add_member_user_access(self):
        """Test user permissions on spp.cr.detail.add_member."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.add_member", user, "read", True)
        self._assert_access("spp.cr.detail.add_member", user, "write", True)
        self._assert_access("spp.cr.detail.add_member", user, "create", True)
        self._assert_access("spp.cr.detail.add_member", user, "unlink", False)

    def test_spp_cr_detail_add_member_validator_access(self):
        """Test validator permissions on spp.cr.detail.add_member."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.add_member", user, "read", True)
        self._assert_access("spp.cr.detail.add_member", user, "write", True)
        self._assert_access("spp.cr.detail.add_member", user, "create", True)
        self._assert_access("spp.cr.detail.add_member", user, "unlink", False)

    def test_spp_cr_detail_edit_individual_manager_access(self):
        """Test manager permissions on spp.cr.detail.edit_individual."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.edit_individual", user, "read", True)
        self._assert_access("spp.cr.detail.edit_individual", user, "write", True)
        self._assert_access("spp.cr.detail.edit_individual", user, "create", True)
        self._assert_access("spp.cr.detail.edit_individual", user, "unlink", True)

    def test_spp_cr_detail_edit_individual_user_access(self):
        """Test user permissions on spp.cr.detail.edit_individual."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.edit_individual", user, "read", True)
        self._assert_access("spp.cr.detail.edit_individual", user, "write", True)
        self._assert_access("spp.cr.detail.edit_individual", user, "create", True)
        self._assert_access("spp.cr.detail.edit_individual", user, "unlink", False)

    def test_spp_cr_detail_edit_individual_validator_access(self):
        """Test validator permissions on spp.cr.detail.edit_individual."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.edit_individual", user, "read", True)
        self._assert_access("spp.cr.detail.edit_individual", user, "write", True)
        self._assert_access("spp.cr.detail.edit_individual", user, "create", True)
        self._assert_access("spp.cr.detail.edit_individual", user, "unlink", False)

    def test_spp_cr_detail_edit_group_manager_access(self):
        """Test manager permissions on spp.cr.detail.edit_group."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.edit_group", user, "read", True)
        self._assert_access("spp.cr.detail.edit_group", user, "write", True)
        self._assert_access("spp.cr.detail.edit_group", user, "create", True)
        self._assert_access("spp.cr.detail.edit_group", user, "unlink", True)

    def test_spp_cr_detail_edit_group_user_access(self):
        """Test user permissions on spp.cr.detail.edit_group."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.edit_group", user, "read", True)
        self._assert_access("spp.cr.detail.edit_group", user, "write", True)
        self._assert_access("spp.cr.detail.edit_group", user, "create", True)
        self._assert_access("spp.cr.detail.edit_group", user, "unlink", False)

    def test_spp_cr_detail_edit_group_validator_access(self):
        """Test validator permissions on spp.cr.detail.edit_group."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.edit_group", user, "read", True)
        self._assert_access("spp.cr.detail.edit_group", user, "write", True)
        self._assert_access("spp.cr.detail.edit_group", user, "create", True)
        self._assert_access("spp.cr.detail.edit_group", user, "unlink", False)

    def test_spp_cr_detail_remove_member_manager_access(self):
        """Test manager permissions on spp.cr.detail.remove_member."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.remove_member", user, "read", True)
        self._assert_access("spp.cr.detail.remove_member", user, "write", True)
        self._assert_access("spp.cr.detail.remove_member", user, "create", True)
        self._assert_access("spp.cr.detail.remove_member", user, "unlink", True)

    def test_spp_cr_detail_remove_member_user_access(self):
        """Test user permissions on spp.cr.detail.remove_member."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.remove_member", user, "read", True)
        self._assert_access("spp.cr.detail.remove_member", user, "write", True)
        self._assert_access("spp.cr.detail.remove_member", user, "create", True)
        self._assert_access("spp.cr.detail.remove_member", user, "unlink", False)

    def test_spp_cr_detail_remove_member_validator_access(self):
        """Test validator permissions on spp.cr.detail.remove_member."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.remove_member", user, "read", True)
        self._assert_access("spp.cr.detail.remove_member", user, "write", True)
        self._assert_access("spp.cr.detail.remove_member", user, "create", True)
        self._assert_access("spp.cr.detail.remove_member", user, "unlink", False)

    def test_spp_cr_detail_change_hoh_manager_access(self):
        """Test manager permissions on spp.cr.detail.change_hoh."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.change_hoh", user, "read", True)
        self._assert_access("spp.cr.detail.change_hoh", user, "write", True)
        self._assert_access("spp.cr.detail.change_hoh", user, "create", True)
        self._assert_access("spp.cr.detail.change_hoh", user, "unlink", True)

    def test_spp_cr_detail_change_hoh_user_access(self):
        """Test user permissions on spp.cr.detail.change_hoh."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.change_hoh", user, "read", True)
        self._assert_access("spp.cr.detail.change_hoh", user, "write", True)
        self._assert_access("spp.cr.detail.change_hoh", user, "create", True)
        self._assert_access("spp.cr.detail.change_hoh", user, "unlink", False)

    def test_spp_cr_detail_change_hoh_validator_access(self):
        """Test validator permissions on spp.cr.detail.change_hoh."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.change_hoh", user, "read", True)
        self._assert_access("spp.cr.detail.change_hoh", user, "write", True)
        self._assert_access("spp.cr.detail.change_hoh", user, "create", True)
        self._assert_access("spp.cr.detail.change_hoh", user, "unlink", False)

    def test_spp_cr_detail_exit_registrant_manager_access(self):
        """Test manager permissions on spp.cr.detail.exit_registrant."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.exit_registrant", user, "read", True)
        self._assert_access("spp.cr.detail.exit_registrant", user, "write", True)
        self._assert_access("spp.cr.detail.exit_registrant", user, "create", True)
        self._assert_access("spp.cr.detail.exit_registrant", user, "unlink", True)

    def test_spp_cr_detail_exit_registrant_user_access(self):
        """Test user permissions on spp.cr.detail.exit_registrant."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.exit_registrant", user, "read", True)
        self._assert_access("spp.cr.detail.exit_registrant", user, "write", True)
        self._assert_access("spp.cr.detail.exit_registrant", user, "create", True)
        self._assert_access("spp.cr.detail.exit_registrant", user, "unlink", False)

    def test_spp_cr_detail_exit_registrant_validator_access(self):
        """Test validator permissions on spp.cr.detail.exit_registrant."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.exit_registrant", user, "read", True)
        self._assert_access("spp.cr.detail.exit_registrant", user, "write", True)
        self._assert_access("spp.cr.detail.exit_registrant", user, "create", True)
        self._assert_access("spp.cr.detail.exit_registrant", user, "unlink", False)

    def test_spp_cr_detail_transfer_member_manager_access(self):
        """Test manager permissions on spp.cr.detail.transfer_member."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.transfer_member", user, "read", True)
        self._assert_access("spp.cr.detail.transfer_member", user, "write", True)
        self._assert_access("spp.cr.detail.transfer_member", user, "create", True)
        self._assert_access("spp.cr.detail.transfer_member", user, "unlink", True)

    def test_spp_cr_detail_transfer_member_user_access(self):
        """Test user permissions on spp.cr.detail.transfer_member."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.transfer_member", user, "read", True)
        self._assert_access("spp.cr.detail.transfer_member", user, "write", True)
        self._assert_access("spp.cr.detail.transfer_member", user, "create", True)
        self._assert_access("spp.cr.detail.transfer_member", user, "unlink", False)

    def test_spp_cr_detail_transfer_member_validator_access(self):
        """Test validator permissions on spp.cr.detail.transfer_member."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.transfer_member", user, "read", True)
        self._assert_access("spp.cr.detail.transfer_member", user, "write", True)
        self._assert_access("spp.cr.detail.transfer_member", user, "create", True)
        self._assert_access("spp.cr.detail.transfer_member", user, "unlink", False)

    def test_spp_cr_detail_update_id_manager_access(self):
        """Test manager permissions on spp.cr.detail.update_id."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.update_id", user, "read", True)
        self._assert_access("spp.cr.detail.update_id", user, "write", True)
        self._assert_access("spp.cr.detail.update_id", user, "create", True)
        self._assert_access("spp.cr.detail.update_id", user, "unlink", True)

    def test_spp_cr_detail_update_id_user_access(self):
        """Test user permissions on spp.cr.detail.update_id."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.update_id", user, "read", True)
        self._assert_access("spp.cr.detail.update_id", user, "write", True)
        self._assert_access("spp.cr.detail.update_id", user, "create", True)
        self._assert_access("spp.cr.detail.update_id", user, "unlink", False)

    def test_spp_cr_detail_update_id_validator_access(self):
        """Test validator permissions on spp.cr.detail.update_id."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.update_id", user, "read", True)
        self._assert_access("spp.cr.detail.update_id", user, "write", True)
        self._assert_access("spp.cr.detail.update_id", user, "create", True)
        self._assert_access("spp.cr.detail.update_id", user, "unlink", False)

    def test_spp_cr_detail_create_group_manager_access(self):
        """Test manager permissions on spp.cr.detail.create_group."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.create_group", user, "read", True)
        self._assert_access("spp.cr.detail.create_group", user, "write", True)
        self._assert_access("spp.cr.detail.create_group", user, "create", True)
        self._assert_access("spp.cr.detail.create_group", user, "unlink", True)

    def test_spp_cr_detail_create_group_user_access(self):
        """Test user permissions on spp.cr.detail.create_group."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.create_group", user, "read", True)
        self._assert_access("spp.cr.detail.create_group", user, "write", True)
        self._assert_access("spp.cr.detail.create_group", user, "create", True)
        self._assert_access("spp.cr.detail.create_group", user, "unlink", False)

    def test_spp_cr_detail_create_group_validator_access(self):
        """Test validator permissions on spp.cr.detail.create_group."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.create_group", user, "read", True)
        self._assert_access("spp.cr.detail.create_group", user, "write", True)
        self._assert_access("spp.cr.detail.create_group", user, "create", True)
        self._assert_access("spp.cr.detail.create_group", user, "unlink", False)

    def test_spp_cr_detail_merge_registrants_manager_access(self):
        """Test manager permissions on spp.cr.detail.merge_registrants."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.merge_registrants", user, "read", True)
        self._assert_access("spp.cr.detail.merge_registrants", user, "write", True)
        self._assert_access("spp.cr.detail.merge_registrants", user, "create", True)
        self._assert_access("spp.cr.detail.merge_registrants", user, "unlink", True)

    def test_spp_cr_detail_merge_registrants_user_access(self):
        """Test user permissions on spp.cr.detail.merge_registrants."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.merge_registrants", user, "read", True)
        self._assert_access("spp.cr.detail.merge_registrants", user, "write", True)
        self._assert_access("spp.cr.detail.merge_registrants", user, "create", True)
        self._assert_access("spp.cr.detail.merge_registrants", user, "unlink", False)

    def test_spp_cr_detail_merge_registrants_validator_access(self):
        """Test validator permissions on spp.cr.detail.merge_registrants."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.merge_registrants", user, "read", True)
        self._assert_access("spp.cr.detail.merge_registrants", user, "write", True)
        self._assert_access("spp.cr.detail.merge_registrants", user, "create", True)
        self._assert_access("spp.cr.detail.merge_registrants", user, "unlink", False)

    def test_spp_cr_detail_split_household_manager_access(self):
        """Test manager permissions on spp.cr.detail.split_household."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.detail.split_household", user, "read", True)
        self._assert_access("spp.cr.detail.split_household", user, "write", True)
        self._assert_access("spp.cr.detail.split_household", user, "create", True)
        self._assert_access("spp.cr.detail.split_household", user, "unlink", True)

    def test_spp_cr_detail_split_household_user_access(self):
        """Test user permissions on spp.cr.detail.split_household."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.detail.split_household", user, "read", True)
        self._assert_access("spp.cr.detail.split_household", user, "write", True)
        self._assert_access("spp.cr.detail.split_household", user, "create", True)
        self._assert_access("spp.cr.detail.split_household", user, "unlink", False)

    def test_spp_cr_detail_split_household_validator_access(self):
        """Test validator permissions on spp.cr.detail.split_household."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.detail.split_household", user, "read", True)
        self._assert_access("spp.cr.detail.split_household", user, "write", True)
        self._assert_access("spp.cr.detail.split_household", user, "create", True)
        self._assert_access("spp.cr.detail.split_household", user, "unlink", False)

    def test_spp_cr_preview_wizard_manager_access(self):
        """Test manager permissions on spp.cr.preview.wizard."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.cr.preview.wizard", user, "read", True)
        self._assert_access("spp.cr.preview.wizard", user, "write", True)
        self._assert_access("spp.cr.preview.wizard", user, "create", True)
        self._assert_access("spp.cr.preview.wizard", user, "unlink", True)

    def test_spp_cr_preview_wizard_user_access(self):
        """Test user permissions on spp.cr.preview.wizard."""
        user = self._get_user_for_role("user")
        if not user:
            self.skipTest("User user not found")
        self._assert_access("spp.cr.preview.wizard", user, "read", True)
        self._assert_access("spp.cr.preview.wizard", user, "write", True)
        self._assert_access("spp.cr.preview.wizard", user, "create", True)
        self._assert_access("spp.cr.preview.wizard", user, "unlink", True)

    def test_spp_cr_preview_wizard_validator_access(self):
        """Test validator permissions on spp.cr.preview.wizard."""
        user = self._get_user_for_role("validator")
        if not user:
            self.skipTest("Validator user not found")
        self._assert_access("spp.cr.preview.wizard", user, "read", True)
        self._assert_access("spp.cr.preview.wizard", user, "write", True)
        self._assert_access("spp.cr.preview.wizard", user, "create", True)
        self._assert_access("spp.cr.preview.wizard", user, "unlink", True)


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

    def test_menu_menu_change_request_root_visibility(self):
        """Test visibility of menu Change Requests."""
        if self.user_viewer:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_root", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Change Requests")
        if self.user_manager:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_root", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Change Requests")

    def test_menu_menu_change_requests_visibility(self):
        """Test visibility of menu All Requests."""
        if self.user_viewer:
            visible = self._menu_visible("spp_change_request_v2.menu_change_requests", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see All Requests")
        if self.user_manager:
            visible = self._menu_visible("spp_change_request_v2.menu_change_requests", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see All Requests")

    def test_menu_menu_my_change_requests_visibility(self):
        """Test visibility of menu My Requests."""
        if self.user_viewer:
            visible = self._menu_visible("spp_change_request_v2.menu_my_change_requests", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see My Requests")
        if self.user_manager:
            visible = self._menu_visible("spp_change_request_v2.menu_my_change_requests", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see My Requests")

    def test_menu_menu_pending_change_requests_visibility(self):
        """Test visibility of menu Pending Approval."""
        if self.user_viewer:
            visible = self._menu_visible("spp_change_request_v2.menu_pending_change_requests", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Pending Approval")
        if self.user_manager:
            visible = self._menu_visible("spp_change_request_v2.menu_pending_change_requests", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Pending Approval")

    def test_menu_menu_approved_change_requests_visibility(self):
        """Test visibility of menu Ready to Apply."""
        if self.user_viewer:
            visible = self._menu_visible("spp_change_request_v2.menu_approved_change_requests", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Ready to Apply")
        if self.user_manager:
            visible = self._menu_visible("spp_change_request_v2.menu_approved_change_requests", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Ready to Apply")

    def test_menu_menu_change_request_reporting_visibility(self):
        """Test visibility of menu Reporting."""
        if self.user_viewer:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_reporting", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Reporting")
        if self.user_manager:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_reporting", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Reporting")

    def test_menu_menu_change_request_analytics_visibility(self):
        """Test visibility of menu Analytics."""
        if self.user_viewer:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_analytics", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Analytics")
        if self.user_manager:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_analytics", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Analytics")

    def test_menu_menu_change_request_config_visibility(self):
        """Test visibility of menu Configuration."""
        if self.user_viewer:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_config", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Configuration")
        if self.user_manager:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_config", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Configuration")

    def test_menu_menu_change_request_types_visibility(self):
        """Test visibility of menu Change Request Types."""
        if self.user_viewer:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_types", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Change Request Types")
        if self.user_manager:
            visible = self._menu_visible("spp_change_request_v2.menu_change_request_types", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Change Request Types")


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

    def test_rule_rule_cr_user_exists(self):
        """Test record rule rule_cr_user exists and is configured."""
        rule = self._get_rule("spp_change_request_v2.rule_cr_user")
        if not rule:
            self.skipTest("Rule rule_cr_user not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.change.request", "Rule should be for model spp.change.request")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_cr_user_groups(self):
        """Test record rule rule_cr_user is assigned to correct groups."""
        rule = self._get_rule("spp_change_request_v2.rule_cr_user")
        if not rule:
            self.skipTest("Rule rule_cr_user not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_change_request_v2.group_cr_user", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_cr_user")

    def test_rule_rule_cr_validator_exists(self):
        """Test record rule rule_cr_validator exists and is configured."""
        rule = self._get_rule("spp_change_request_v2.rule_cr_validator")
        if not rule:
            self.skipTest("Rule rule_cr_validator not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.change.request", "Rule should be for model spp.change.request")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_cr_validator_groups(self):
        """Test record rule rule_cr_validator is assigned to correct groups."""
        rule = self._get_rule("spp_change_request_v2.rule_cr_validator")
        if not rule:
            self.skipTest("Rule rule_cr_validator not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_change_request_v2.group_cr_validator", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_cr_validator")

    def test_rule_rule_cr_manager_exists(self):
        """Test record rule rule_cr_manager exists and is configured."""
        rule = self._get_rule("spp_change_request_v2.rule_cr_manager")
        if not rule:
            self.skipTest("Rule rule_cr_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.change.request", "Rule should be for model spp.change.request")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_cr_manager_groups(self):
        """Test record rule rule_cr_manager is assigned to correct groups."""
        rule = self._get_rule("spp_change_request_v2.rule_cr_manager")
        if not rule:
            self.skipTest("Rule rule_cr_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_change_request_v2.group_cr_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_cr_manager")


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestAdminLinkage(TestComplianceBase):
    """Test that admin group inherits manager permissions."""

    def test_admin_has_manager_group(self):
        """Test admin user has group_cr_manager permissions."""
        if not self.user_admin:
            self.skipTest("Admin user not created")
        self.assertTrue(
            self.user_admin.has_group("spp_change_request_v2.group_cr_manager"),
            "Admin should have group_cr_manager permissions",
        )

    def test_admin_group_implies_manager(self):
        """Test spp_security.group_spp_admin implies group_cr_manager."""
        admin_group = self.env.ref("spp_security.group_spp_admin", raise_if_not_found=False)
        manager_group = self.env.ref("spp_change_request_v2.group_cr_manager", raise_if_not_found=False)
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
            manager_group.id, all_implied, "Admin group should imply group_cr_manager (directly or transitively)"
        )
