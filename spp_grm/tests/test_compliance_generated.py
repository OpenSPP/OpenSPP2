# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# AUTO-GENERATED from compliance.yaml - DO NOT EDIT MANUALLY
# Regenerate with: python -m scripts.compliance.test_generator spp_grm

"""
Access control compliance tests for spp_grm.

Generated from: spp_grm/security/compliance.yaml
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
    """Base class for spp_grm compliance tests."""

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
        cls.role_groups["viewer"] = safe_ref("spp_grm.group_grm_viewer")
        cls.role_users["viewer"] = cls._create_test_user("viewer", cls.role_groups["viewer"])

        # Officer role
        cls.role_groups["officer"] = safe_ref("spp_grm.group_grm_officer")
        cls.role_users["officer"] = cls._create_test_user("officer", cls.role_groups["officer"])

        # Manager role
        cls.role_groups["manager"] = safe_ref("spp_grm.group_grm_manager")
        cls.role_users["manager"] = cls._create_test_user("manager", cls.role_groups["manager"])

        # Read role
        cls.role_groups["read"] = safe_ref("spp_grm.group_grm_read")
        cls.role_users["read"] = cls._create_test_user("read", cls.role_groups["read"])

        # Write role
        cls.role_groups["write"] = safe_ref("spp_grm.group_grm_write")
        cls.role_users["write"] = cls._create_test_user("write", cls.role_groups["write"])

        # Supervisor role
        cls.role_groups["supervisor"] = safe_ref("spp_grm.group_grm_supervisor")
        cls.role_users["supervisor"] = cls._create_test_user("supervisor", cls.role_groups["supervisor"])

        # User role
        cls.role_groups["user"] = safe_ref("spp_grm.group_grm_user")
        cls.role_users["user"] = cls._create_test_user("user", cls.role_groups["user"])

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
            self.user_manager.has_group("spp_grm.group_grm_officer"), "Manager should have officer privileges"
        )

    def test_officer_implies_viewer(self):
        """Officer group should imply viewer group."""
        if not self.user_officer or not self.group_viewer:
            self.skipTest("Required groups not found")
        self.assertTrue(
            self.user_officer.has_group("spp_grm.group_grm_viewer"), "Officer should have viewer privileges"
        )

    def test_group_grm_write_implies(self):
        """Test group_grm_write implies correct groups."""
        group = self.env.ref("spp_grm.group_grm_write", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_grm_write not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_grm.group_grm_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_grm_write should imply group_grm_read")

    def test_group_grm_viewer_implies(self):
        """Test group_grm_viewer implies correct groups."""
        group = self.env.ref("spp_grm.group_grm_viewer", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_grm_viewer not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_grm.group_grm_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_grm_viewer should imply group_grm_read")

    def test_group_grm_officer_implies(self):
        """Test group_grm_officer implies correct groups."""
        group = self.env.ref("spp_grm.group_grm_officer", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_grm_officer not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_grm.group_grm_viewer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_grm_officer should imply group_grm_viewer")
        implied_group = self.env.ref("spp_grm.group_grm_write", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_grm_officer should imply group_grm_write")

    def test_group_grm_manager_implies(self):
        """Test group_grm_manager implies correct groups."""
        group = self.env.ref("spp_grm.group_grm_manager", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_grm_manager not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_grm.group_grm_officer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_grm_manager should imply group_grm_officer")

    def test_group_grm_supervisor_implies(self):
        """Test group_grm_supervisor implies correct groups."""
        group = self.env.ref("spp_grm.group_grm_supervisor", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_grm_supervisor not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_grm.group_grm_officer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_grm_supervisor should imply group_grm_officer")

    def test_group_grm_user_implies(self):
        """Test group_grm_user implies correct groups."""
        group = self.env.ref("spp_grm.group_grm_user", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_grm_user not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_grm.group_grm_viewer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_grm_user should imply group_grm_viewer")


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestModelAccess(TestComplianceBase):
    """Test model CRUD permissions per role."""

    def test_spp_grm_ticket_viewer_access(self):
        """Test viewer permissions on spp.grm.ticket."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.grm.ticket", user, "read", True)
        self._assert_access("spp.grm.ticket", user, "write", False)
        self._assert_access("spp.grm.ticket", user, "create", False)
        self._assert_access("spp.grm.ticket", user, "unlink", False)

    def test_spp_grm_ticket_officer_access(self):
        """Test officer permissions on spp.grm.ticket."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.grm.ticket", user, "read", True)
        self._assert_access("spp.grm.ticket", user, "write", True)
        self._assert_access("spp.grm.ticket", user, "create", True)
        self._assert_access("spp.grm.ticket", user, "unlink", False)

    def test_spp_grm_ticket_manager_access(self):
        """Test manager permissions on spp.grm.ticket."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.grm.ticket", user, "read", True)
        self._assert_access("spp.grm.ticket", user, "write", True)
        self._assert_access("spp.grm.ticket", user, "create", True)
        self._assert_access("spp.grm.ticket", user, "unlink", True)

    def test_spp_grm_ticket_stage_viewer_access(self):
        """Test viewer permissions on spp.grm.ticket.stage."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.grm.ticket.stage", user, "read", True)
        self._assert_access("spp.grm.ticket.stage", user, "write", False)
        self._assert_access("spp.grm.ticket.stage", user, "create", False)
        self._assert_access("spp.grm.ticket.stage", user, "unlink", False)

    def test_spp_grm_ticket_stage_officer_access(self):
        """Test officer permissions on spp.grm.ticket.stage."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.grm.ticket.stage", user, "read", True)
        self._assert_access("spp.grm.ticket.stage", user, "write", False)
        self._assert_access("spp.grm.ticket.stage", user, "create", False)
        self._assert_access("spp.grm.ticket.stage", user, "unlink", False)

    def test_spp_grm_ticket_stage_manager_access(self):
        """Test manager permissions on spp.grm.ticket.stage."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.grm.ticket.stage", user, "read", True)
        self._assert_access("spp.grm.ticket.stage", user, "write", True)
        self._assert_access("spp.grm.ticket.stage", user, "create", True)
        self._assert_access("spp.grm.ticket.stage", user, "unlink", True)

    def test_spp_grm_ticket_tag_viewer_access(self):
        """Test viewer permissions on spp.grm.ticket.tag."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.grm.ticket.tag", user, "read", True)
        self._assert_access("spp.grm.ticket.tag", user, "write", False)
        self._assert_access("spp.grm.ticket.tag", user, "create", False)
        self._assert_access("spp.grm.ticket.tag", user, "unlink", False)

    def test_spp_grm_ticket_tag_officer_access(self):
        """Test officer permissions on spp.grm.ticket.tag."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.grm.ticket.tag", user, "read", True)
        self._assert_access("spp.grm.ticket.tag", user, "write", True)
        self._assert_access("spp.grm.ticket.tag", user, "create", True)
        self._assert_access("spp.grm.ticket.tag", user, "unlink", False)

    def test_spp_grm_ticket_tag_manager_access(self):
        """Test manager permissions on spp.grm.ticket.tag."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.grm.ticket.tag", user, "read", True)
        self._assert_access("spp.grm.ticket.tag", user, "write", True)
        self._assert_access("spp.grm.ticket.tag", user, "create", True)
        self._assert_access("spp.grm.ticket.tag", user, "unlink", True)

    def test_spp_grm_ticket_channel_viewer_access(self):
        """Test viewer permissions on spp.grm.ticket.channel."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.grm.ticket.channel", user, "read", True)
        self._assert_access("spp.grm.ticket.channel", user, "write", False)
        self._assert_access("spp.grm.ticket.channel", user, "create", False)
        self._assert_access("spp.grm.ticket.channel", user, "unlink", False)

    def test_spp_grm_ticket_channel_officer_access(self):
        """Test officer permissions on spp.grm.ticket.channel."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.grm.ticket.channel", user, "read", True)
        self._assert_access("spp.grm.ticket.channel", user, "write", False)
        self._assert_access("spp.grm.ticket.channel", user, "create", False)
        self._assert_access("spp.grm.ticket.channel", user, "unlink", False)

    def test_spp_grm_ticket_channel_manager_access(self):
        """Test manager permissions on spp.grm.ticket.channel."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.grm.ticket.channel", user, "read", True)
        self._assert_access("spp.grm.ticket.channel", user, "write", True)
        self._assert_access("spp.grm.ticket.channel", user, "create", True)
        self._assert_access("spp.grm.ticket.channel", user, "unlink", True)

    def test_spp_grm_ticket_category_viewer_access(self):
        """Test viewer permissions on spp.grm.ticket.category."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.grm.ticket.category", user, "read", True)
        self._assert_access("spp.grm.ticket.category", user, "write", False)
        self._assert_access("spp.grm.ticket.category", user, "create", False)
        self._assert_access("spp.grm.ticket.category", user, "unlink", False)

    def test_spp_grm_ticket_category_officer_access(self):
        """Test officer permissions on spp.grm.ticket.category."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.grm.ticket.category", user, "read", True)
        self._assert_access("spp.grm.ticket.category", user, "write", False)
        self._assert_access("spp.grm.ticket.category", user, "create", False)
        self._assert_access("spp.grm.ticket.category", user, "unlink", False)

    def test_spp_grm_ticket_category_manager_access(self):
        """Test manager permissions on spp.grm.ticket.category."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.grm.ticket.category", user, "read", True)
        self._assert_access("spp.grm.ticket.category", user, "write", True)
        self._assert_access("spp.grm.ticket.category", user, "create", True)
        self._assert_access("spp.grm.ticket.category", user, "unlink", True)

    def test_spp_grm_ticket_subcategory_viewer_access(self):
        """Test viewer permissions on spp.grm.ticket.subcategory."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.grm.ticket.subcategory", user, "read", True)
        self._assert_access("spp.grm.ticket.subcategory", user, "write", False)
        self._assert_access("spp.grm.ticket.subcategory", user, "create", False)
        self._assert_access("spp.grm.ticket.subcategory", user, "unlink", False)

    def test_spp_grm_ticket_subcategory_officer_access(self):
        """Test officer permissions on spp.grm.ticket.subcategory."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.grm.ticket.subcategory", user, "read", True)
        self._assert_access("spp.grm.ticket.subcategory", user, "write", False)
        self._assert_access("spp.grm.ticket.subcategory", user, "create", False)
        self._assert_access("spp.grm.ticket.subcategory", user, "unlink", False)

    def test_spp_grm_ticket_subcategory_manager_access(self):
        """Test manager permissions on spp.grm.ticket.subcategory."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.grm.ticket.subcategory", user, "read", True)
        self._assert_access("spp.grm.ticket.subcategory", user, "write", True)
        self._assert_access("spp.grm.ticket.subcategory", user, "create", True)
        self._assert_access("spp.grm.ticket.subcategory", user, "unlink", True)

    def test_spp_grm_team_viewer_access(self):
        """Test viewer permissions on spp.grm.team."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.grm.team", user, "read", True)
        self._assert_access("spp.grm.team", user, "write", False)
        self._assert_access("spp.grm.team", user, "create", False)
        self._assert_access("spp.grm.team", user, "unlink", False)

    def test_spp_grm_team_officer_access(self):
        """Test officer permissions on spp.grm.team."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.grm.team", user, "read", True)
        self._assert_access("spp.grm.team", user, "write", False)
        self._assert_access("spp.grm.team", user, "create", False)
        self._assert_access("spp.grm.team", user, "unlink", False)

    def test_spp_grm_team_manager_access(self):
        """Test manager permissions on spp.grm.team."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.grm.team", user, "read", True)
        self._assert_access("spp.grm.team", user, "write", True)
        self._assert_access("spp.grm.team", user, "create", True)
        self._assert_access("spp.grm.team", user, "unlink", True)

    def test_spp_grm_sla_rule_viewer_access(self):
        """Test viewer permissions on spp.grm.sla.rule."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.grm.sla.rule", user, "read", True)
        self._assert_access("spp.grm.sla.rule", user, "write", False)
        self._assert_access("spp.grm.sla.rule", user, "create", False)
        self._assert_access("spp.grm.sla.rule", user, "unlink", False)

    def test_spp_grm_sla_rule_officer_access(self):
        """Test officer permissions on spp.grm.sla.rule."""
        user = self._get_user_for_role("officer")
        if not user:
            self.skipTest("Officer user not found")
        self._assert_access("spp.grm.sla.rule", user, "read", True)
        self._assert_access("spp.grm.sla.rule", user, "write", False)
        self._assert_access("spp.grm.sla.rule", user, "create", False)
        self._assert_access("spp.grm.sla.rule", user, "unlink", False)

    def test_spp_grm_sla_rule_manager_access(self):
        """Test manager permissions on spp.grm.sla.rule."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.grm.sla.rule", user, "read", True)
        self._assert_access("spp.grm.sla.rule", user, "write", True)
        self._assert_access("spp.grm.sla.rule", user, "create", True)
        self._assert_access("spp.grm.sla.rule", user, "unlink", True)


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

    def test_menu_spp_grm_ticket_main_menu_visibility(self):
        """Test visibility of menu GRM."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_main_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see GRM")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_main_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see GRM")

    def test_menu_spp_grm_ticket_menu_visibility(self):
        """Test visibility of menu Tickets."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Tickets")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Tickets")

    def test_menu_spp_grm_ticket_config_main_menu_visibility(self):
        """Test visibility of menu Configuration."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_config_main_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Configuration")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_config_main_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Configuration")

    def test_menu_spp_grm_ticket_stage_menu_visibility(self):
        """Test visibility of menu Stages."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_stage_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Stages")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_stage_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Stages")

    def test_menu_spp_grm_ticket_tag_menu_visibility(self):
        """Test visibility of menu Tags."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_tag_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Tags")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_tag_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Tags")

    def test_menu_spp_grm_ticket_channel_menu_visibility(self):
        """Test visibility of menu Channels."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_channel_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Channels")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_channel_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Channels")

    def test_menu_spp_grm_ticket_category_menu_visibility(self):
        """Test visibility of menu Categories."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_category_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Categories")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_category_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Categories")

    def test_menu_spp_grm_ticket_subcategory_menu_visibility(self):
        """Test visibility of menu Subcategories."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_subcategory_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Subcategories")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_ticket_subcategory_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Subcategories")

    def test_menu_spp_grm_team_menu_visibility(self):
        """Test visibility of menu Teams."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_team_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Teams")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_team_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Teams")

    def test_menu_spp_grm_sla_rule_menu_visibility(self):
        """Test visibility of menu SLA Rules."""
        if self.user_viewer:
            visible = self._menu_visible("spp_grm.spp_grm_sla_rule_menu", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see SLA Rules")
        if self.user_manager:
            visible = self._menu_visible("spp_grm.spp_grm_sla_rule_menu", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see SLA Rules")


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

    def test_rule_rule_spp_grm_ticket_viewer_exists(self):
        """Test record rule rule_spp_grm_ticket_viewer exists and is configured."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_viewer")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_viewer not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.grm.ticket", "Rule should be for model spp.grm.ticket")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, False)
        self.assertEqual(rule.perm_create, False)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_grm_ticket_viewer_groups(self):
        """Test record rule rule_spp_grm_ticket_viewer is assigned to correct groups."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_viewer")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_viewer not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_grm.group_grm_viewer", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_grm_viewer")

    def test_rule_rule_spp_grm_ticket_officer_exists(self):
        """Test record rule rule_spp_grm_ticket_officer exists and is configured."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_officer")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_officer not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.grm.ticket", "Rule should be for model spp.grm.ticket")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_grm_ticket_officer_groups(self):
        """Test record rule rule_spp_grm_ticket_officer is assigned to correct groups."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_officer")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_officer not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_grm.group_grm_officer", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_grm_officer")

    def test_rule_rule_spp_grm_ticket_supervisor_exists(self):
        """Test record rule rule_spp_grm_ticket_supervisor exists and is configured."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_supervisor not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.grm.ticket", "Rule should be for model spp.grm.ticket")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_grm_ticket_supervisor_groups(self):
        """Test record rule rule_spp_grm_ticket_supervisor is assigned to correct groups."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_supervisor not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_grm.group_grm_supervisor", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_grm_supervisor")

    def test_rule_rule_spp_grm_ticket_manager_exists(self):
        """Test record rule rule_spp_grm_ticket_manager exists and is configured."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.grm.ticket", "Rule should be for model spp.grm.ticket")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_grm_ticket_manager_groups(self):
        """Test record rule rule_spp_grm_ticket_manager is assigned to correct groups."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_grm.group_grm_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_grm_manager")

    def test_rule_rule_spp_grm_team_manager_exists(self):
        """Test record rule rule_spp_grm_team_manager exists and is configured."""
        rule = self._get_rule("spp_grm.rule_spp_grm_team_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_team_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.grm.team", "Rule should be for model spp.grm.team")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_grm_team_manager_groups(self):
        """Test record rule rule_spp_grm_team_manager is assigned to correct groups."""
        rule = self._get_rule("spp_grm.rule_spp_grm_team_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_team_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_grm.group_grm_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_grm_manager")

    def test_rule_rule_spp_grm_ticket_category_manager_exists(self):
        """Test record rule rule_spp_grm_ticket_category_manager exists and is configured."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_category_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_category_manager not found")

        # Verify rule model
        self.assertEqual(
            rule.model_id.model, "spp.grm.ticket.category", "Rule should be for model spp.grm.ticket.category"
        )

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_grm_ticket_category_manager_groups(self):
        """Test record rule rule_spp_grm_ticket_category_manager is assigned to correct groups."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_category_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_category_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_grm.group_grm_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_grm_manager")

    def test_rule_rule_spp_grm_ticket_stage_manager_exists(self):
        """Test record rule rule_spp_grm_ticket_stage_manager exists and is configured."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_stage_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_stage_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.grm.ticket.stage", "Rule should be for model spp.grm.ticket.stage")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_grm_ticket_stage_manager_groups(self):
        """Test record rule rule_spp_grm_ticket_stage_manager is assigned to correct groups."""
        rule = self._get_rule("spp_grm.rule_spp_grm_ticket_stage_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_ticket_stage_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_grm.group_grm_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_grm_manager")

    def test_rule_rule_spp_grm_sla_rule_manager_exists(self):
        """Test record rule rule_spp_grm_sla_rule_manager exists and is configured."""
        rule = self._get_rule("spp_grm.rule_spp_grm_sla_rule_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_sla_rule_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.grm.sla.rule", "Rule should be for model spp.grm.sla.rule")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_grm_sla_rule_manager_groups(self):
        """Test record rule rule_spp_grm_sla_rule_manager is assigned to correct groups."""
        rule = self._get_rule("spp_grm.rule_spp_grm_sla_rule_manager")
        if not rule:
            self.skipTest("Rule rule_spp_grm_sla_rule_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_grm.group_grm_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_grm_manager")


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestAdminLinkage(TestComplianceBase):
    """Test that admin group inherits manager permissions."""

    def test_admin_has_manager_group(self):
        """Test admin user has group_grm_manager permissions."""
        if not self.user_admin:
            self.skipTest("Admin user not created")
        self.assertTrue(
            self.user_admin.has_group("spp_grm.group_grm_manager"), "Admin should have group_grm_manager permissions"
        )

    def test_admin_group_implies_manager(self):
        """Test spp_security.group_spp_admin implies group_grm_manager."""
        admin_group = self.env.ref("spp_security.group_spp_admin", raise_if_not_found=False)
        manager_group = self.env.ref("spp_grm.group_grm_manager", raise_if_not_found=False)
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
            manager_group.id, all_implied, "Admin group should imply group_grm_manager (directly or transitively)"
        )
