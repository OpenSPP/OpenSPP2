# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# AUTO-GENERATED from compliance.yaml - DO NOT EDIT MANUALLY
# Regenerate with: python -m scripts.compliance.test_generator spp_case_base

"""
Access control compliance tests for spp_case_base.

Generated from: spp_case_base/security/compliance.yaml
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
    """Base class for spp_case_base compliance tests."""

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
        cls.role_groups["viewer"] = safe_ref("spp_case_base.group_case_viewer")
        cls.role_users["viewer"] = cls._create_test_user("viewer", cls.role_groups["viewer"])

        # Officer role
        cls.role_groups["officer"] = safe_ref("spp_case_base.group_case_officer")
        cls.role_users["officer"] = cls._create_test_user("officer", cls.role_groups["officer"])

        # Manager role
        cls.role_groups["manager"] = safe_ref("spp_case_base.group_case_manager")
        cls.role_users["manager"] = cls._create_test_user("manager", cls.role_groups["manager"])

        # Supervisor role
        cls.role_groups["supervisor"] = safe_ref("spp_case_base.group_case_supervisor")
        cls.role_users["supervisor"] = cls._create_test_user("supervisor", cls.role_groups["supervisor"])

        # Worker role
        cls.role_groups["worker"] = safe_ref("spp_case_base.group_case_worker")
        cls.role_users["worker"] = cls._create_test_user("worker", cls.role_groups["worker"])

        # Read role
        cls.role_groups["read"] = safe_ref("spp_case_base.group_case_read")
        cls.role_users["read"] = cls._create_test_user("read", cls.role_groups["read"])

        # Write role
        cls.role_groups["write"] = safe_ref("spp_case_base.group_case_write")
        cls.role_users["write"] = cls._create_test_user("write", cls.role_groups["write"])

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
            self.user_manager.has_group("spp_case_base.group_case_officer"), "Manager should have officer privileges"
        )

    def test_officer_implies_viewer(self):
        """Officer group should imply viewer group."""
        if not self.user_officer or not self.group_viewer:
            self.skipTest("Required groups not found")
        self.assertTrue(
            self.user_officer.has_group("spp_case_base.group_case_viewer"), "Officer should have viewer privileges"
        )

    def test_group_case_write_implies(self):
        """Test group_case_write implies correct groups."""
        group = self.env.ref("spp_case_base.group_case_write", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_case_write not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_case_base.group_case_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_case_write should imply group_case_read")

    def test_group_case_viewer_implies(self):
        """Test group_case_viewer implies correct groups."""
        group = self.env.ref("spp_case_base.group_case_viewer", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_case_viewer not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_case_base.group_case_read", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_case_viewer should imply group_case_read")

    def test_group_case_officer_implies(self):
        """Test group_case_officer implies correct groups."""
        group = self.env.ref("spp_case_base.group_case_officer", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_case_officer not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_case_base.group_case_viewer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_case_officer should imply group_case_viewer")
        implied_group = self.env.ref("spp_case_base.group_case_write", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_case_officer should imply group_case_write")

    def test_group_case_worker_implies(self):
        """Test group_case_worker implies correct groups."""
        group = self.env.ref("spp_case_base.group_case_worker", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_case_worker not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_case_base.group_case_viewer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_case_worker should imply group_case_viewer")

    def test_group_case_supervisor_implies(self):
        """Test group_case_supervisor implies correct groups."""
        group = self.env.ref("spp_case_base.group_case_supervisor", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_case_supervisor not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_case_base.group_case_worker", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_case_supervisor should imply group_case_worker")

    def test_group_case_manager_implies(self):
        """Test group_case_manager implies correct groups."""
        group = self.env.ref("spp_case_base.group_case_manager", raise_if_not_found=False)
        if not group:
            self.skipTest("Group group_case_manager not found")
        implied_ids = group.implied_ids.mapped("id")
        implied_group = self.env.ref("spp_case_base.group_case_officer", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_case_manager should imply group_case_officer")
        implied_group = self.env.ref("spp_case_base.group_case_supervisor", raise_if_not_found=False)
        if implied_group:
            self.assertIn(implied_group.id, implied_ids, "group_case_manager should imply group_case_supervisor")


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestModelAccess(TestComplianceBase):
    """Test model CRUD permissions per role."""

    def test_spp_case_viewer_access(self):
        """Test viewer permissions on spp.case."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case", user, "read", True)
        self._assert_access("spp.case", user, "write", False)
        self._assert_access("spp.case", user, "create", False)
        self._assert_access("spp.case", user, "unlink", False)

    def test_spp_case_manager_access(self):
        """Test manager permissions on spp.case."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case", user, "read", True)
        self._assert_access("spp.case", user, "write", True)
        self._assert_access("spp.case", user, "create", True)
        self._assert_access("spp.case", user, "unlink", True)

    def test_spp_case_supervisor_access(self):
        """Test supervisor permissions on spp.case."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case", user, "read", True)
        self._assert_access("spp.case", user, "write", True)
        self._assert_access("spp.case", user, "create", True)
        self._assert_access("spp.case", user, "unlink", True)

    def test_spp_case_worker_access(self):
        """Test worker permissions on spp.case."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case", user, "read", True)
        self._assert_access("spp.case", user, "write", True)
        self._assert_access("spp.case", user, "create", True)
        self._assert_access("spp.case", user, "unlink", True)

    def test_spp_case_assessment_viewer_access(self):
        """Test viewer permissions on spp.case.assessment."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.assessment", user, "read", True)
        self._assert_access("spp.case.assessment", user, "write", False)
        self._assert_access("spp.case.assessment", user, "create", False)
        self._assert_access("spp.case.assessment", user, "unlink", False)

    def test_spp_case_assessment_manager_access(self):
        """Test manager permissions on spp.case.assessment."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.assessment", user, "read", True)
        self._assert_access("spp.case.assessment", user, "write", True)
        self._assert_access("spp.case.assessment", user, "create", True)
        self._assert_access("spp.case.assessment", user, "unlink", True)

    def test_spp_case_assessment_supervisor_access(self):
        """Test supervisor permissions on spp.case.assessment."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.assessment", user, "read", True)
        self._assert_access("spp.case.assessment", user, "write", True)
        self._assert_access("spp.case.assessment", user, "create", True)
        self._assert_access("spp.case.assessment", user, "unlink", True)

    def test_spp_case_assessment_worker_access(self):
        """Test worker permissions on spp.case.assessment."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.assessment", user, "read", True)
        self._assert_access("spp.case.assessment", user, "write", True)
        self._assert_access("spp.case.assessment", user, "create", True)
        self._assert_access("spp.case.assessment", user, "unlink", True)

    def test_spp_case_stage_viewer_access(self):
        """Test viewer permissions on spp.case.stage."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.stage", user, "read", True)
        self._assert_access("spp.case.stage", user, "write", False)
        self._assert_access("spp.case.stage", user, "create", False)
        self._assert_access("spp.case.stage", user, "unlink", False)

    def test_spp_case_stage_manager_access(self):
        """Test manager permissions on spp.case.stage."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.stage", user, "read", True)
        self._assert_access("spp.case.stage", user, "write", True)
        self._assert_access("spp.case.stage", user, "create", True)
        self._assert_access("spp.case.stage", user, "unlink", True)

    def test_spp_case_stage_supervisor_access(self):
        """Test supervisor permissions on spp.case.stage."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.stage", user, "read", True)
        self._assert_access("spp.case.stage", user, "write", False)
        self._assert_access("spp.case.stage", user, "create", False)
        self._assert_access("spp.case.stage", user, "unlink", False)

    def test_spp_case_stage_worker_access(self):
        """Test worker permissions on spp.case.stage."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.stage", user, "read", True)
        self._assert_access("spp.case.stage", user, "write", False)
        self._assert_access("spp.case.stage", user, "create", False)
        self._assert_access("spp.case.stage", user, "unlink", False)

    def test_spp_case_type_viewer_access(self):
        """Test viewer permissions on spp.case.type."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.type", user, "read", True)
        self._assert_access("spp.case.type", user, "write", False)
        self._assert_access("spp.case.type", user, "create", False)
        self._assert_access("spp.case.type", user, "unlink", False)

    def test_spp_case_type_manager_access(self):
        """Test manager permissions on spp.case.type."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.type", user, "read", True)
        self._assert_access("spp.case.type", user, "write", True)
        self._assert_access("spp.case.type", user, "create", True)
        self._assert_access("spp.case.type", user, "unlink", True)

    def test_spp_case_type_supervisor_access(self):
        """Test supervisor permissions on spp.case.type."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.type", user, "read", True)
        self._assert_access("spp.case.type", user, "write", False)
        self._assert_access("spp.case.type", user, "create", False)
        self._assert_access("spp.case.type", user, "unlink", False)

    def test_spp_case_type_worker_access(self):
        """Test worker permissions on spp.case.type."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.type", user, "read", True)
        self._assert_access("spp.case.type", user, "write", False)
        self._assert_access("spp.case.type", user, "create", False)
        self._assert_access("spp.case.type", user, "unlink", False)

    def test_spp_case_intervention_plan_viewer_access(self):
        """Test viewer permissions on spp.case.intervention.plan."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.intervention.plan", user, "read", True)
        self._assert_access("spp.case.intervention.plan", user, "write", False)
        self._assert_access("spp.case.intervention.plan", user, "create", False)
        self._assert_access("spp.case.intervention.plan", user, "unlink", False)

    def test_spp_case_intervention_plan_manager_access(self):
        """Test manager permissions on spp.case.intervention.plan."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.intervention.plan", user, "read", True)
        self._assert_access("spp.case.intervention.plan", user, "write", True)
        self._assert_access("spp.case.intervention.plan", user, "create", True)
        self._assert_access("spp.case.intervention.plan", user, "unlink", True)

    def test_spp_case_intervention_plan_supervisor_access(self):
        """Test supervisor permissions on spp.case.intervention.plan."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.intervention.plan", user, "read", True)
        self._assert_access("spp.case.intervention.plan", user, "write", True)
        self._assert_access("spp.case.intervention.plan", user, "create", True)
        self._assert_access("spp.case.intervention.plan", user, "unlink", True)

    def test_spp_case_intervention_plan_worker_access(self):
        """Test worker permissions on spp.case.intervention.plan."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.intervention.plan", user, "read", True)
        self._assert_access("spp.case.intervention.plan", user, "write", True)
        self._assert_access("spp.case.intervention.plan", user, "create", True)
        self._assert_access("spp.case.intervention.plan", user, "unlink", True)

    def test_spp_case_intervention_viewer_access(self):
        """Test viewer permissions on spp.case.intervention."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.intervention", user, "read", True)
        self._assert_access("spp.case.intervention", user, "write", False)
        self._assert_access("spp.case.intervention", user, "create", False)
        self._assert_access("spp.case.intervention", user, "unlink", False)

    def test_spp_case_intervention_manager_access(self):
        """Test manager permissions on spp.case.intervention."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.intervention", user, "read", True)
        self._assert_access("spp.case.intervention", user, "write", True)
        self._assert_access("spp.case.intervention", user, "create", True)
        self._assert_access("spp.case.intervention", user, "unlink", True)

    def test_spp_case_intervention_supervisor_access(self):
        """Test supervisor permissions on spp.case.intervention."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.intervention", user, "read", True)
        self._assert_access("spp.case.intervention", user, "write", True)
        self._assert_access("spp.case.intervention", user, "create", True)
        self._assert_access("spp.case.intervention", user, "unlink", True)

    def test_spp_case_intervention_worker_access(self):
        """Test worker permissions on spp.case.intervention."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.intervention", user, "read", True)
        self._assert_access("spp.case.intervention", user, "write", True)
        self._assert_access("spp.case.intervention", user, "create", True)
        self._assert_access("spp.case.intervention", user, "unlink", True)

    def test_spp_case_visit_viewer_access(self):
        """Test viewer permissions on spp.case.visit."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.visit", user, "read", True)
        self._assert_access("spp.case.visit", user, "write", False)
        self._assert_access("spp.case.visit", user, "create", False)
        self._assert_access("spp.case.visit", user, "unlink", False)

    def test_spp_case_visit_manager_access(self):
        """Test manager permissions on spp.case.visit."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.visit", user, "read", True)
        self._assert_access("spp.case.visit", user, "write", True)
        self._assert_access("spp.case.visit", user, "create", True)
        self._assert_access("spp.case.visit", user, "unlink", True)

    def test_spp_case_visit_supervisor_access(self):
        """Test supervisor permissions on spp.case.visit."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.visit", user, "read", True)
        self._assert_access("spp.case.visit", user, "write", True)
        self._assert_access("spp.case.visit", user, "create", True)
        self._assert_access("spp.case.visit", user, "unlink", True)

    def test_spp_case_visit_worker_access(self):
        """Test worker permissions on spp.case.visit."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.visit", user, "read", True)
        self._assert_access("spp.case.visit", user, "write", True)
        self._assert_access("spp.case.visit", user, "create", True)
        self._assert_access("spp.case.visit", user, "unlink", True)

    def test_spp_case_note_viewer_access(self):
        """Test viewer permissions on spp.case.note."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.note", user, "read", True)
        self._assert_access("spp.case.note", user, "write", False)
        self._assert_access("spp.case.note", user, "create", False)
        self._assert_access("spp.case.note", user, "unlink", False)

    def test_spp_case_note_manager_access(self):
        """Test manager permissions on spp.case.note."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.note", user, "read", True)
        self._assert_access("spp.case.note", user, "write", True)
        self._assert_access("spp.case.note", user, "create", True)
        self._assert_access("spp.case.note", user, "unlink", True)

    def test_spp_case_note_supervisor_access(self):
        """Test supervisor permissions on spp.case.note."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.note", user, "read", True)
        self._assert_access("spp.case.note", user, "write", True)
        self._assert_access("spp.case.note", user, "create", True)
        self._assert_access("spp.case.note", user, "unlink", True)

    def test_spp_case_note_worker_access(self):
        """Test worker permissions on spp.case.note."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.note", user, "read", True)
        self._assert_access("spp.case.note", user, "write", True)
        self._assert_access("spp.case.note", user, "create", True)
        self._assert_access("spp.case.note", user, "unlink", True)

    def test_spp_case_referral_viewer_access(self):
        """Test viewer permissions on spp.case.referral."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.referral", user, "read", True)
        self._assert_access("spp.case.referral", user, "write", False)
        self._assert_access("spp.case.referral", user, "create", False)
        self._assert_access("spp.case.referral", user, "unlink", False)

    def test_spp_case_referral_manager_access(self):
        """Test manager permissions on spp.case.referral."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.referral", user, "read", True)
        self._assert_access("spp.case.referral", user, "write", True)
        self._assert_access("spp.case.referral", user, "create", True)
        self._assert_access("spp.case.referral", user, "unlink", True)

    def test_spp_case_referral_supervisor_access(self):
        """Test supervisor permissions on spp.case.referral."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.referral", user, "read", True)
        self._assert_access("spp.case.referral", user, "write", True)
        self._assert_access("spp.case.referral", user, "create", True)
        self._assert_access("spp.case.referral", user, "unlink", True)

    def test_spp_case_referral_worker_access(self):
        """Test worker permissions on spp.case.referral."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.referral", user, "read", True)
        self._assert_access("spp.case.referral", user, "write", True)
        self._assert_access("spp.case.referral", user, "create", True)
        self._assert_access("spp.case.referral", user, "unlink", True)

    def test_spp_case_risk_factor_viewer_access(self):
        """Test viewer permissions on spp.case.risk.factor."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.risk.factor", user, "read", True)
        self._assert_access("spp.case.risk.factor", user, "write", False)
        self._assert_access("spp.case.risk.factor", user, "create", False)
        self._assert_access("spp.case.risk.factor", user, "unlink", False)

    def test_spp_case_risk_factor_manager_access(self):
        """Test manager permissions on spp.case.risk.factor."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.risk.factor", user, "read", True)
        self._assert_access("spp.case.risk.factor", user, "write", True)
        self._assert_access("spp.case.risk.factor", user, "create", True)
        self._assert_access("spp.case.risk.factor", user, "unlink", True)

    def test_spp_case_risk_factor_supervisor_access(self):
        """Test supervisor permissions on spp.case.risk.factor."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.risk.factor", user, "read", True)
        self._assert_access("spp.case.risk.factor", user, "write", False)
        self._assert_access("spp.case.risk.factor", user, "create", False)
        self._assert_access("spp.case.risk.factor", user, "unlink", False)

    def test_spp_case_risk_factor_worker_access(self):
        """Test worker permissions on spp.case.risk.factor."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.risk.factor", user, "read", True)
        self._assert_access("spp.case.risk.factor", user, "write", False)
        self._assert_access("spp.case.risk.factor", user, "create", False)
        self._assert_access("spp.case.risk.factor", user, "unlink", False)

    def test_spp_case_vulnerability_viewer_access(self):
        """Test viewer permissions on spp.case.vulnerability."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.vulnerability", user, "read", True)
        self._assert_access("spp.case.vulnerability", user, "write", False)
        self._assert_access("spp.case.vulnerability", user, "create", False)
        self._assert_access("spp.case.vulnerability", user, "unlink", False)

    def test_spp_case_vulnerability_manager_access(self):
        """Test manager permissions on spp.case.vulnerability."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.vulnerability", user, "read", True)
        self._assert_access("spp.case.vulnerability", user, "write", True)
        self._assert_access("spp.case.vulnerability", user, "create", True)
        self._assert_access("spp.case.vulnerability", user, "unlink", True)

    def test_spp_case_vulnerability_supervisor_access(self):
        """Test supervisor permissions on spp.case.vulnerability."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.vulnerability", user, "read", True)
        self._assert_access("spp.case.vulnerability", user, "write", False)
        self._assert_access("spp.case.vulnerability", user, "create", False)
        self._assert_access("spp.case.vulnerability", user, "unlink", False)

    def test_spp_case_vulnerability_worker_access(self):
        """Test worker permissions on spp.case.vulnerability."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.vulnerability", user, "read", True)
        self._assert_access("spp.case.vulnerability", user, "write", False)
        self._assert_access("spp.case.vulnerability", user, "create", False)
        self._assert_access("spp.case.vulnerability", user, "unlink", False)

    def test_spp_case_closure_reason_viewer_access(self):
        """Test viewer permissions on spp.case.closure.reason."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.closure.reason", user, "read", True)
        self._assert_access("spp.case.closure.reason", user, "write", False)
        self._assert_access("spp.case.closure.reason", user, "create", False)
        self._assert_access("spp.case.closure.reason", user, "unlink", False)

    def test_spp_case_closure_reason_manager_access(self):
        """Test manager permissions on spp.case.closure.reason."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.closure.reason", user, "read", True)
        self._assert_access("spp.case.closure.reason", user, "write", True)
        self._assert_access("spp.case.closure.reason", user, "create", True)
        self._assert_access("spp.case.closure.reason", user, "unlink", True)

    def test_spp_case_closure_reason_supervisor_access(self):
        """Test supervisor permissions on spp.case.closure.reason."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.closure.reason", user, "read", True)
        self._assert_access("spp.case.closure.reason", user, "write", False)
        self._assert_access("spp.case.closure.reason", user, "create", False)
        self._assert_access("spp.case.closure.reason", user, "unlink", False)

    def test_spp_case_closure_reason_worker_access(self):
        """Test worker permissions on spp.case.closure.reason."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.closure.reason", user, "read", True)
        self._assert_access("spp.case.closure.reason", user, "write", False)
        self._assert_access("spp.case.closure.reason", user, "create", False)
        self._assert_access("spp.case.closure.reason", user, "unlink", False)

    def test_spp_case_team_viewer_access(self):
        """Test viewer permissions on spp.case.team."""
        user = self._get_user_for_role("viewer")
        if not user:
            self.skipTest("Viewer user not found")
        self._assert_access("spp.case.team", user, "read", True)
        self._assert_access("spp.case.team", user, "write", False)
        self._assert_access("spp.case.team", user, "create", False)
        self._assert_access("spp.case.team", user, "unlink", False)

    def test_spp_case_team_manager_access(self):
        """Test manager permissions on spp.case.team."""
        user = self._get_user_for_role("manager")
        if not user:
            self.skipTest("Manager user not found")
        self._assert_access("spp.case.team", user, "read", True)
        self._assert_access("spp.case.team", user, "write", True)
        self._assert_access("spp.case.team", user, "create", True)
        self._assert_access("spp.case.team", user, "unlink", True)

    def test_spp_case_team_supervisor_access(self):
        """Test supervisor permissions on spp.case.team."""
        user = self._get_user_for_role("supervisor")
        if not user:
            self.skipTest("Supervisor user not found")
        self._assert_access("spp.case.team", user, "read", True)
        self._assert_access("spp.case.team", user, "write", False)
        self._assert_access("spp.case.team", user, "create", False)
        self._assert_access("spp.case.team", user, "unlink", False)

    def test_spp_case_team_worker_access(self):
        """Test worker permissions on spp.case.team."""
        user = self._get_user_for_role("worker")
        if not user:
            self.skipTest("Worker user not found")
        self._assert_access("spp.case.team", user, "read", True)
        self._assert_access("spp.case.team", user, "write", False)
        self._assert_access("spp.case.team", user, "create", False)
        self._assert_access("spp.case.team", user, "unlink", False)


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

    def test_menu_menu_case_management_root_visibility(self):
        """Test visibility of menu Case Management."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_management_root", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Case Management")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_management_root", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Case Management")

    def test_menu_menu_case_management_cases_visibility(self):
        """Test visibility of menu Cases."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_management_cases", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Cases")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_management_cases", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Cases")

    def test_menu_menu_case_my_cases_visibility(self):
        """Test visibility of menu My Cases."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_my_cases", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see My Cases")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_my_cases", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see My Cases")

    def test_menu_menu_case_unassigned_visibility(self):
        """Test visibility of menu Unassigned."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_unassigned", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Unassigned")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_unassigned", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Unassigned")

    def test_menu_menu_case_all_visibility(self):
        """Test visibility of menu All Cases."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_all", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see All Cases")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_all", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see All Cases")

    def test_menu_menu_case_management_activities_visibility(self):
        """Test visibility of menu Activities."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_management_activities", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Activities")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_management_activities", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Activities")

    def test_menu_menu_case_visits_visibility(self):
        """Test visibility of menu Visits."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_visits", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Visits")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_visits", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Visits")

    def test_menu_menu_case_notes_visibility(self):
        """Test visibility of menu Notes."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_notes", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Notes")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_notes", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Notes")

    def test_menu_menu_case_referrals_visibility(self):
        """Test visibility of menu Referrals."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_referrals", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Referrals")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_referrals", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Referrals")

    def test_menu_menu_case_assessment_visibility(self):
        """Test visibility of menu Assessments."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_assessment", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Assessments")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_assessment", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Assessments")

    def test_menu_menu_case_management_planning_visibility(self):
        """Test visibility of menu Planning."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_management_planning", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Planning")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_management_planning", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Planning")

    def test_menu_menu_case_intervention_plans_visibility(self):
        """Test visibility of menu Intervention Plans."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_intervention_plans", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Intervention Plans")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_intervention_plans", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Intervention Plans")

    def test_menu_menu_case_interventions_visibility(self):
        """Test visibility of menu Interventions."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_interventions", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Interventions")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_interventions", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Interventions")

    def test_menu_menu_case_management_config_visibility(self):
        """Test visibility of menu Configuration."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_management_config", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Configuration")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_management_config", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Configuration")

    def test_menu_menu_case_config_case_setup_visibility(self):
        """Test visibility of menu Case Setup."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_config_case_setup", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Case Setup")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_config_case_setup", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Case Setup")

    def test_menu_menu_case_types_visibility(self):
        """Test visibility of menu Case Types."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_types", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Case Types")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_types", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Case Types")

    def test_menu_menu_case_stages_visibility(self):
        """Test visibility of menu Stages."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_stages", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Stages")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_stages", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Stages")

    def test_menu_menu_case_teams_visibility(self):
        """Test visibility of menu Teams."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_teams", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Teams")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_teams", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Teams")

    def test_menu_menu_case_config_assessment_visibility(self):
        """Test visibility of menu Assessment."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_config_assessment", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Assessment")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_config_assessment", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Assessment")

    def test_menu_menu_case_risk_factors_visibility(self):
        """Test visibility of menu Risk Factors."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_risk_factors", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Risk Factors")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_risk_factors", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Risk Factors")

    def test_menu_menu_case_vulnerabilities_visibility(self):
        """Test visibility of menu Vulnerabilities."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_vulnerabilities", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Vulnerabilities")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_vulnerabilities", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Vulnerabilities")

    def test_menu_menu_case_config_closure_visibility(self):
        """Test visibility of menu Closure."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_config_closure", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Closure")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_config_closure", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Closure")

    def test_menu_menu_case_closure_reasons_visibility(self):
        """Test visibility of menu Closure Reasons."""
        if self.user_viewer:
            visible = self._menu_visible("spp_case_base.menu_case_closure_reasons", self.user_viewer)
            if visible is not None:
                self.assertFalse(visible, "Viewer should NOT see Closure Reasons")
        if self.user_manager:
            visible = self._menu_visible("spp_case_base.menu_case_closure_reasons", self.user_manager)
            if visible is not None:
                self.assertTrue(visible, "Manager should see Closure Reasons")


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

    def test_rule_rule_spp_case_worker_exists(self):
        """Test record rule rule_spp_case_worker exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_worker not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case", "Rule should be for model spp.case")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_worker_groups(self):
        """Test record rule rule_spp_case_worker is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_worker not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_worker", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_worker")

    def test_rule_rule_spp_case_supervisor_exists(self):
        """Test record rule rule_spp_case_supervisor exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_supervisor not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case", "Rule should be for model spp.case")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_supervisor_groups(self):
        """Test record rule rule_spp_case_supervisor is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_supervisor not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_supervisor", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_supervisor")

    def test_rule_rule_spp_case_manager_exists(self):
        """Test record rule rule_spp_case_manager exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case", "Rule should be for model spp.case")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_case_manager_groups(self):
        """Test record rule rule_spp_case_manager is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_manager")

    def test_rule_rule_spp_case_intervention_plan_worker_exists(self):
        """Test record rule rule_spp_case_intervention_plan_worker exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_plan_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_plan_worker not found")

        # Verify rule model
        self.assertEqual(
            rule.model_id.model, "spp.case.intervention.plan", "Rule should be for model spp.case.intervention.plan"
        )

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_intervention_plan_worker_groups(self):
        """Test record rule rule_spp_case_intervention_plan_worker is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_plan_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_plan_worker not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_worker", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_worker")

    def test_rule_rule_spp_case_intervention_plan_supervisor_exists(self):
        """Test record rule rule_spp_case_intervention_plan_supervisor exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_plan_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_plan_supervisor not found")

        # Verify rule model
        self.assertEqual(
            rule.model_id.model, "spp.case.intervention.plan", "Rule should be for model spp.case.intervention.plan"
        )

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_intervention_plan_supervisor_groups(self):
        """Test record rule rule_spp_case_intervention_plan_supervisor is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_plan_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_plan_supervisor not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_supervisor", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_supervisor")

    def test_rule_rule_spp_case_intervention_plan_manager_exists(self):
        """Test record rule rule_spp_case_intervention_plan_manager exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_plan_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_plan_manager not found")

        # Verify rule model
        self.assertEqual(
            rule.model_id.model, "spp.case.intervention.plan", "Rule should be for model spp.case.intervention.plan"
        )

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_case_intervention_plan_manager_groups(self):
        """Test record rule rule_spp_case_intervention_plan_manager is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_plan_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_plan_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_manager")

    def test_rule_rule_spp_case_intervention_worker_exists(self):
        """Test record rule rule_spp_case_intervention_worker exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_worker not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.intervention", "Rule should be for model spp.case.intervention")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_intervention_worker_groups(self):
        """Test record rule rule_spp_case_intervention_worker is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_worker not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_worker", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_worker")

    def test_rule_rule_spp_case_intervention_supervisor_exists(self):
        """Test record rule rule_spp_case_intervention_supervisor exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_supervisor not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.intervention", "Rule should be for model spp.case.intervention")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_intervention_supervisor_groups(self):
        """Test record rule rule_spp_case_intervention_supervisor is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_supervisor not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_supervisor", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_supervisor")

    def test_rule_rule_spp_case_intervention_manager_exists(self):
        """Test record rule rule_spp_case_intervention_manager exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.intervention", "Rule should be for model spp.case.intervention")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_case_intervention_manager_groups(self):
        """Test record rule rule_spp_case_intervention_manager is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_intervention_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_intervention_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_manager")

    def test_rule_rule_spp_case_visit_worker_exists(self):
        """Test record rule rule_spp_case_visit_worker exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_visit_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_visit_worker not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.visit", "Rule should be for model spp.case.visit")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_visit_worker_groups(self):
        """Test record rule rule_spp_case_visit_worker is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_visit_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_visit_worker not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_worker", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_worker")

    def test_rule_rule_spp_case_visit_supervisor_exists(self):
        """Test record rule rule_spp_case_visit_supervisor exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_visit_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_visit_supervisor not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.visit", "Rule should be for model spp.case.visit")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_visit_supervisor_groups(self):
        """Test record rule rule_spp_case_visit_supervisor is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_visit_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_visit_supervisor not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_supervisor", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_supervisor")

    def test_rule_rule_spp_case_visit_manager_exists(self):
        """Test record rule rule_spp_case_visit_manager exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_visit_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_visit_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.visit", "Rule should be for model spp.case.visit")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_case_visit_manager_groups(self):
        """Test record rule rule_spp_case_visit_manager is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_visit_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_visit_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_manager")

    def test_rule_rule_spp_case_note_worker_exists(self):
        """Test record rule rule_spp_case_note_worker exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_note_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_note_worker not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.note", "Rule should be for model spp.case.note")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_note_worker_groups(self):
        """Test record rule rule_spp_case_note_worker is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_note_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_note_worker not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_worker", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_worker")

    def test_rule_rule_spp_case_note_supervisor_exists(self):
        """Test record rule rule_spp_case_note_supervisor exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_note_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_note_supervisor not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.note", "Rule should be for model spp.case.note")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_note_supervisor_groups(self):
        """Test record rule rule_spp_case_note_supervisor is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_note_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_note_supervisor not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_supervisor", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_supervisor")

    def test_rule_rule_spp_case_note_manager_exists(self):
        """Test record rule rule_spp_case_note_manager exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_note_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_note_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.note", "Rule should be for model spp.case.note")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_case_note_manager_groups(self):
        """Test record rule rule_spp_case_note_manager is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_note_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_note_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_manager")

    def test_rule_rule_spp_case_referral_worker_exists(self):
        """Test record rule rule_spp_case_referral_worker exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_referral_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_referral_worker not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.referral", "Rule should be for model spp.case.referral")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_referral_worker_groups(self):
        """Test record rule rule_spp_case_referral_worker is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_referral_worker")
        if not rule:
            self.skipTest("Rule rule_spp_case_referral_worker not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_worker", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_worker")

    def test_rule_rule_spp_case_referral_supervisor_exists(self):
        """Test record rule rule_spp_case_referral_supervisor exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_referral_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_referral_supervisor not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.referral", "Rule should be for model spp.case.referral")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, False)

    def test_rule_rule_spp_case_referral_supervisor_groups(self):
        """Test record rule rule_spp_case_referral_supervisor is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_referral_supervisor")
        if not rule:
            self.skipTest("Rule rule_spp_case_referral_supervisor not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_supervisor", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_supervisor")

    def test_rule_rule_spp_case_referral_manager_exists(self):
        """Test record rule rule_spp_case_referral_manager exists and is configured."""
        rule = self._get_rule("spp_case_base.rule_spp_case_referral_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_referral_manager not found")

        # Verify rule model
        self.assertEqual(rule.model_id.model, "spp.case.referral", "Rule should be for model spp.case.referral")

        # Verify permissions
        self.assertEqual(rule.perm_read, True)
        self.assertEqual(rule.perm_write, True)
        self.assertEqual(rule.perm_create, True)
        self.assertEqual(rule.perm_unlink, True)

    def test_rule_rule_spp_case_referral_manager_groups(self):
        """Test record rule rule_spp_case_referral_manager is assigned to correct groups."""
        rule = self._get_rule("spp_case_base.rule_spp_case_referral_manager")
        if not rule:
            self.skipTest("Rule rule_spp_case_referral_manager not found")

        rule_group_xmlids = []
        for group in rule.groups:
            xml_id = group.get_external_id().get(group.id)
            if xml_id:
                rule_group_xmlids.append(xml_id)

        expected_group = self.env.ref("spp_case_base.group_case_manager", raise_if_not_found=False)
        if expected_group:
            self.assertIn(expected_group, rule.groups, "Rule should include group group_case_manager")


@tagged("post_install", "-at_install", "access_control", "compliance", "data_visibility")
class TestDataVisibility(TestComplianceBase):
    """Test data visibility based on record rule domains.

    These tests create actual records and verify that users can only
    see the records they are allowed to see based on domain filters.
    """

    def test_spp_case_assigned_visibility(self):
        """Test spp.case: user only sees records assigned to them."""
        if not self.user_officer or not self.user_viewer:
            self.skipTest("Required users not found")

        Model = self.env["spp.case"]

        # Check model has assignment field
        if "case_worker_id" not in Model._fields:
            self.skipTest("Model missing case_worker_id field")

        # Create record assigned to officer (as admin)
        try:
            officer_assigned = Model.sudo().create(
                {
                    "name": "Assigned to Officer",
                    "case_worker_id": self.user_officer.id,
                }
            )
        except Exception as e:
            self.skipTest(f"Cannot create test record: {e}")

        # Create record assigned to viewer (as admin)
        try:
            viewer_assigned = Model.sudo().create(
                {
                    "name": "Assigned to Viewer",
                    "case_worker_id": self.user_viewer.id,
                }
            )
        except Exception:
            viewer_assigned = None

        # Test: officer should see record assigned to them
        officer_visible = Model.with_user(self.user_officer).search([("id", "=", officer_assigned.id)])
        self.assertTrue(officer_visible, "Officer should see records assigned to them")

        # Test: officer should NOT see viewer's assigned record
        if viewer_assigned:
            officer_sees_viewer = Model.with_user(self.user_officer).search([("id", "=", viewer_assigned.id)])
            self.assertFalse(officer_sees_viewer, "Officer should NOT see records assigned to others")

    def test_spp_case_sees_all(self):
        """Test spp.case: user with this rule sees all records."""
        Model = self.env["spp.case"]

        # Get initial count as admin
        admin_count = Model.sudo().search_count([])
        if admin_count == 0:
            self.skipTest("No records to test visibility")

        # Test that user sees all records
        if self.user_manager:
            user_count = Model.with_user(self.user_manager).search_count([])
            self.assertEqual(
                user_count, admin_count, f"Manager should see all {admin_count} records, but sees {user_count}"
            )

    def test_spp_case_intervention_plan_sees_all(self):
        """Test spp.case.intervention.plan: user with this rule sees all records."""
        Model = self.env["spp.case.intervention.plan"]

        # Get initial count as admin
        admin_count = Model.sudo().search_count([])
        if admin_count == 0:
            self.skipTest("No records to test visibility")

        # Test that user sees all records
        if self.user_manager:
            user_count = Model.with_user(self.user_manager).search_count([])
            self.assertEqual(
                user_count, admin_count, f"Manager should see all {admin_count} records, but sees {user_count}"
            )


@tagged("post_install", "-at_install", "access_control", "compliance")
class TestAdminLinkage(TestComplianceBase):
    """Test that admin group inherits manager permissions."""

    def test_admin_has_manager_group(self):
        """Test admin user has group_case_manager permissions."""
        if not self.user_admin:
            self.skipTest("Admin user not created")
        self.assertTrue(
            self.user_admin.has_group("spp_case_base.group_case_manager"),
            "Admin should have group_case_manager permissions",
        )

    def test_admin_group_implies_manager(self):
        """Test spp_security.group_spp_admin implies group_case_manager."""
        admin_group = self.env.ref("spp_security.group_spp_admin", raise_if_not_found=False)
        manager_group = self.env.ref("spp_case_base.group_case_manager", raise_if_not_found=False)
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
            manager_group.id, all_implied, "Admin group should imply group_case_manager (directly or transitively)"
        )
