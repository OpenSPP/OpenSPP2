# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Comprehensive access control tests for spp_mis_demo_v2 deployment.

This test suite validates access rights, record rules, menu visibility,
and group hierarchy for the complete MIS demo deployment scenario.

Tests cover:
- CRUD permissions for all key models per role
- Menu visibility per role
- Record rule filtering (data visibility)
- Group hierarchy (implied_ids)

Core modules covered in this file:
- spp_registry (Registry)
- spp_programs (Programs)
- spp_change_request_v2 (Change Requests)

Additional modules covered in separate files:
- spp_grm (Grievance/Helpdesk) - test_access_control_grm.py
- spp_case_base (Case Management) - test_access_control_case.py

IMPORTANT TEST LIMITATIONS
==========================

1. Transaction Isolation (test_enable bypass):
   The MIS Demo Generator uses `config["test_enable"]` to skip `cr.commit()`
   calls during tests. This is necessary for test isolation but means:
   - Deferred database constraints are NOT tested
   - Database triggers that fire on commit are NOT tested
   - Transaction race conditions are NOT tested

   For commit-related behavior, run integration tests in a staging environment.

2. XML Data Dependencies:
   Menu visibility tests validate that XML definitions have correct group
   restrictions. If a test fails, FIX THE XML DATA - don't modify tests to
   programmatically set the groups (that would test the test, not the system).

3. What These Tests DO Cover:
   - Model access (ir.model.access.csv) permissions
   - Record rules (ir.rule) domain filtering
   - Group hierarchy via implied_ids
   - Cross-user access attempts (read/write/delete)
   - Portal user isolation
   - Null/empty field edge cases

4. What These Tests DO NOT Cover:
   - Performance under load
   - Concurrent access patterns
   - UI-level security (view restrictions, field invisibility)
   - External API authentication

5. Role Module Compatibility (base_user_role):
   The base_user_role OCA module assigns default roles to new users via
   `_default_role_lines()`, and these roles override explicitly assigned groups.
   To test explicit group assignments and implied_ids hierarchy, we pass
   `role_line_ids: []` when creating test users. This prevents the role system
   from overriding the test's group assignments. This is NOT "adding groups" -
   it's ensuring the test controls which groups the user has.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


def _safe_ref(env, xml_id):
    """Safely get a reference, returning None if not found."""
    try:
        return env.ref(xml_id)
    except ValueError:
        return None


@tagged("post_install", "-at_install", "access_control")
class TestAccessControlBase(TransactionCase):
    """Base class for access control tests with common setup."""

    @classmethod
    def setUpClass(cls):
        """Set up test users with different roles."""
        super().setUpClass()

        # Check which modules are installed
        cls.grm_installed = bool(_safe_ref(cls.env, "spp_grm.group_grm_viewer"))
        cls.case_installed = bool(_safe_ref(cls.env, "spp_case_base.group_case_viewer"))

        # Base groups for all users
        base_groups = [Command.link(cls.env.ref("base.group_user").id)]

        # === VIEWER USER ===
        viewer_groups = base_groups.copy()
        viewer_groups.extend(
            [
                Command.link(cls.env.ref("spp_registry.group_registry_viewer").id),
                Command.link(cls.env.ref("spp_programs.group_programs_viewer").id),
                Command.link(cls.env.ref("spp_change_request_v2.group_cr_user").id),
            ]
        )
        if cls.grm_installed:
            viewer_groups.append(Command.link(cls.env.ref("spp_grm.group_grm_viewer").id))
        if cls.case_installed:
            viewer_groups.append(Command.link(cls.env.ref("spp_case_base.group_case_viewer").id))

        cls.user_viewer = cls.env["res.users"].create(
            {
                "name": "Test Viewer",
                "login": "test_viewer_ac",
                "email": "viewer_ac@test.com",
                "group_ids": viewer_groups,
                "role_line_ids": [],  # Bypass default roles to test explicit group assignments
            }
        )

        # === OFFICER USER ===
        officer_groups = base_groups.copy()
        officer_groups.extend(
            [
                Command.link(cls.env.ref("spp_registry.group_registry_officer").id),
                Command.link(cls.env.ref("spp_programs.group_programs_officer").id),
                Command.link(cls.env.ref("spp_change_request_v2.group_cr_user").id),
            ]
        )
        if cls.grm_installed:
            officer_groups.append(Command.link(cls.env.ref("spp_grm.group_grm_officer").id))
        if cls.case_installed:
            officer_groups.append(Command.link(cls.env.ref("spp_case_base.group_case_officer").id))

        cls.user_officer = cls.env["res.users"].create(
            {
                "name": "Test Officer",
                "login": "test_officer_ac",
                "email": "officer_ac@test.com",
                "group_ids": officer_groups,
                "role_line_ids": [],  # Bypass default roles to test explicit group assignments
            }
        )

        # === VALIDATOR/SUPERVISOR USER ===
        validator_groups = base_groups.copy()
        validator_groups.extend(
            [
                Command.link(cls.env.ref("spp_registry.group_registry_officer").id),
                Command.link(cls.env.ref("spp_programs.group_programs_officer").id),
                Command.link(cls.env.ref("spp_change_request_v2.group_cr_validator").id),
            ]
        )
        if cls.grm_installed:
            validator_groups.append(Command.link(cls.env.ref("spp_grm.group_grm_supervisor").id))
        if cls.case_installed:
            validator_groups.append(Command.link(cls.env.ref("spp_case_base.group_case_supervisor").id))

        cls.user_validator = cls.env["res.users"].create(
            {
                "name": "Test Validator",
                "login": "test_validator_ac",
                "email": "validator_ac@test.com",
                "group_ids": validator_groups,
                "role_line_ids": [],  # Bypass default roles to test explicit group assignments
            }
        )

        # === MANAGER USER ===
        manager_groups = base_groups.copy()
        manager_groups.extend(
            [
                Command.link(cls.env.ref("spp_registry.group_registry_manager").id),
                Command.link(cls.env.ref("spp_programs.group_programs_manager").id),
                Command.link(cls.env.ref("spp_change_request_v2.group_cr_manager").id),
            ]
        )
        if cls.grm_installed:
            manager_groups.append(Command.link(cls.env.ref("spp_grm.group_grm_manager").id))
        if cls.case_installed:
            manager_groups.append(Command.link(cls.env.ref("spp_case_base.group_case_manager").id))

        cls.user_manager = cls.env["res.users"].create(
            {
                "name": "Test Manager",
                "login": "test_manager_ac",
                "email": "manager_ac@test.com",
                "group_ids": manager_groups,
                "role_line_ids": [],  # Bypass default roles to test explicit group assignments
            }
        )

        # === ADMIN USER ===
        cls.user_admin = cls.env["res.users"].create(
            {
                "name": "Test Admin",
                "login": "test_admin_ac",
                "email": "admin_ac@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_security.group_spp_admin").id),
                ],
                "role_line_ids": [],  # Bypass default roles to test explicit group assignments
            }
        )

        # === BASIC USER (no domain groups) ===
        cls.user_basic = cls.env["res.users"].create(
            {
                "name": "Test Basic User",
                "login": "test_basic_ac",
                "email": "basic_ac@test.com",
                "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
                "role_line_ids": [],  # Bypass default roles to test explicit group assignments
            }
        )

        # Invalidate cache and refresh user records to ensure implied groups are computed
        # This is necessary because Odoo's group implication may not be immediately
        # visible after user creation in test environments
        cls.env.invalidate_all()
        cls.user_viewer = cls.env["res.users"].browse(cls.user_viewer.id)
        cls.user_officer = cls.env["res.users"].browse(cls.user_officer.id)
        cls.user_validator = cls.env["res.users"].browse(cls.user_validator.id)
        cls.user_manager = cls.env["res.users"].browse(cls.user_manager.id)
        cls.user_admin = cls.env["res.users"].browse(cls.user_admin.id)
        cls.user_basic = cls.env["res.users"].browse(cls.user_basic.id)


# =============================================================================
# GROUP HIERARCHY TESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control")
class TestGroupHierarchy(TestAccessControlBase):
    """Test security group hierarchy and implied_ids chains."""

    # === Registry Group Hierarchy ===

    def test_registry_manager_has_officer(self):
        """Test registry manager inherits officer permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_registry.group_registry_officer"),
            "Registry manager should have officer permissions",
        )

    def test_registry_manager_has_viewer(self):
        """Test registry manager inherits viewer permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_registry.group_registry_viewer"),
            "Registry manager should have viewer permissions",
        )

    def test_registry_officer_has_viewer(self):
        """Test registry officer inherits viewer permissions."""
        self.assertTrue(
            self.user_officer.has_group("spp_registry.group_registry_viewer"),
            "Registry officer should have viewer permissions",
        )

    def test_registry_officer_has_technical_groups(self):
        """Test registry officer has technical read/write/create groups."""
        self.assertTrue(
            self.user_officer.has_group("spp_registry.group_registry_read"),
            "Registry officer should have read permission",
        )
        self.assertTrue(
            self.user_officer.has_group("spp_registry.group_registry_write"),
            "Registry officer should have write permission",
        )
        self.assertTrue(
            self.user_officer.has_group("spp_registry.group_registry_create"),
            "Registry officer should have create permission",
        )

    # === Programs Group Hierarchy ===

    def test_programs_manager_has_officer(self):
        """Test programs manager inherits officer permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_programs.group_programs_officer"),
            "Programs manager should have officer permissions",
        )

    def test_programs_manager_has_viewer(self):
        """Test programs manager inherits viewer permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_programs.group_programs_viewer"),
            "Programs manager should have viewer permissions",
        )

    def test_programs_officer_has_viewer(self):
        """Test programs officer inherits viewer permissions."""
        self.assertTrue(
            self.user_officer.has_group("spp_programs.group_programs_viewer"),
            "Programs officer should have viewer permissions",
        )

    # === Change Request Group Hierarchy ===

    def test_cr_manager_has_validator(self):
        """Test CR manager inherits validator permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_change_request_v2.group_cr_validator"),
            "CR manager should have validator permissions",
        )

    def test_cr_manager_has_user(self):
        """Test CR manager inherits user permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_change_request_v2.group_cr_user"),
            "CR manager should have user permissions",
        )

    def test_cr_validator_has_user(self):
        """Test CR validator inherits user permissions."""
        self.assertTrue(
            self.user_validator.has_group("spp_change_request_v2.group_cr_user"),
            "CR validator should have user permissions",
        )

    # === Admin Group Hierarchy ===

    def test_admin_has_registry_manager(self):
        """Test admin inherits registry manager permissions."""
        self.assertTrue(
            self.user_admin.has_group("spp_registry.group_registry_manager"),
            "Admin should have registry manager permissions",
        )

    def test_admin_has_programs_manager(self):
        """Test admin inherits programs manager permissions."""
        self.assertTrue(
            self.user_admin.has_group("spp_programs.group_programs_manager"),
            "Admin should have programs manager permissions",
        )


# =============================================================================
# TECHNICAL GROUP ISOLATION TESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control")
class TestTechnicalGroups(TestAccessControlBase):
    """Test technical groups (Tier 3) work correctly when used in isolation.

    This validates that technical groups (group_registry_read, group_registry_write,
    group_registry_create) function correctly on their own, without being granted
    through user-facing groups (viewer, officer, manager).
    """

    @classmethod
    def setUpClass(cls):
        """Set up test users with only technical groups."""
        super().setUpClass()

        # User with only read permission
        cls.user_read_only = cls.env["res.users"].create(
            {
                "name": "Test Read Only",
                "login": "test_read_only_tech",
                "email": "read_only_tech@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_registry.group_registry_read").id),
                ],
                "role_line_ids": [],  # Bypass default roles to test explicit group assignments
            }
        )

        # User with read + write but NOT create
        cls.user_write_only = cls.env["res.users"].create(
            {
                "name": "Test Write Only",
                "login": "test_write_only_tech",
                "email": "write_only_tech@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_registry.group_registry_read").id),
                    Command.link(cls.env.ref("spp_registry.group_registry_write").id),
                ],
                "role_line_ids": [],  # Bypass default roles to test explicit group assignments
            }
        )

        # Create a test registrant for read/write tests
        cls.test_registrant = cls.env["res.partner"].create(
            {"name": "Technical Test Registrant", "is_registrant": True, "is_group": False}
        )

        # Invalidate cache and refresh user records
        cls.env.invalidate_all()
        cls.user_read_only = cls.env["res.users"].browse(cls.user_read_only.id)
        cls.user_write_only = cls.env["res.users"].browse(cls.user_write_only.id)

    def test_read_group_can_read_registrant(self):
        """Test user with only registry_read group can read registrants."""
        registrant = self.test_registrant.with_user(self.user_read_only)
        self.assertEqual(
            registrant.name,
            "Technical Test Registrant",
            "User with read-only technical group should be able to read registrant",
        )

    def test_read_group_cannot_write_registrant(self):
        """Test user with only registry_read group cannot write registrants."""
        with self.assertRaises(
            AccessError,
            msg="User with only read permission should not be able to write",
        ):
            self.test_registrant.with_user(self.user_read_only).write({"name": "Unauthorized Write"})

    def test_read_group_cannot_create_registrant(self):
        """Test user with only registry_read group cannot create registrants."""
        with self.assertRaises(
            AccessError,
            msg="User with only read permission should not be able to create",
        ):
            self.env["res.partner"].with_user(self.user_read_only).create(
                {"name": "Unauthorized Create", "is_registrant": True}
            )

    def test_write_group_can_modify_registrant(self):
        """Test user with read+write groups can modify registrants."""
        self.test_registrant.with_user(self.user_write_only).write({"name": "Modified by Write User"})
        self.assertEqual(
            self.test_registrant.name,
            "Modified by Write User",
            "User with read+write technical groups should be able to modify registrant",
        )

    def test_write_group_without_create_cannot_create(self):
        """Test user with read+write but not create cannot create registrants."""
        with self.assertRaises(
            AccessError,
            msg="User with read+write but without create should not be able to create",
        ):
            self.env["res.partner"].with_user(self.user_write_only).create(
                {"name": "Should Fail", "is_registrant": True}
            )


# =============================================================================
# MODEL ACCESS TESTS - REGISTRY
# =============================================================================


@tagged("post_install", "-at_install", "access_control")
class TestRegistryModelAccess(TestAccessControlBase):
    """Test CRUD access for registry models."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for registry access tests."""
        super().setUpClass()
        cls.test_registrant = cls.env["res.partner"].create(
            {"name": "Test Registrant", "is_registrant": True, "is_group": False}
        )

        # Create a registry-only viewer (without CR user which grants write/create)
        # This is needed to properly test registry viewer restrictions
        cls.user_registry_viewer_only = cls.env["res.users"].create(
            {
                "name": "Test Registry Viewer Only",
                "login": "test_registry_viewer_only_ac",
                "email": "registry_viewer_only_ac@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_registry.group_registry_viewer").id),
                ],
                "role_line_ids": [],  # Bypass default roles
            }
        )

    def test_registrant_read_viewer(self):
        """Test viewer can read registrant records."""
        registrant = self.test_registrant.with_user(self.user_viewer)
        self.assertEqual(registrant.name, "Test Registrant")

    def test_registrant_create_viewer_denied(self):
        """Test registry-only viewer cannot create registrant records.

        Uses registry_viewer_only user to isolate registry permissions from
        CR user permissions (which grant write/create on res.partner).
        """
        with self.assertRaises(AccessError):
            self.env["res.partner"].with_user(self.user_registry_viewer_only).create(
                {"name": "Unauthorized", "is_registrant": True}
            )

    def test_registrant_write_viewer_denied(self):
        """Test registry-only viewer cannot modify registrant records.

        Uses registry_viewer_only user to isolate registry permissions from
        CR user permissions (which grant write/create on res.partner).
        """
        with self.assertRaises(AccessError):
            self.test_registrant.with_user(self.user_registry_viewer_only).write({"name": "Modified"})

    def test_registrant_create_officer(self):
        """Test officer can create registrant records."""
        registrant = (
            self.env["res.partner"]
            .with_user(self.user_officer)
            .create({"name": "Officer Created", "is_registrant": True})
        )
        self.assertTrue(registrant.exists())

    def test_registrant_write_officer(self):
        """Test officer can modify registrant records."""
        self.test_registrant.with_user(self.user_officer).write({"name": "Modified"})
        self.assertEqual(self.test_registrant.name, "Modified")

    def test_registrant_unlink_officer_denied(self):
        """Test officer cannot delete registrant records."""
        registrant = self.env["res.partner"].create({"name": "To Delete", "is_registrant": True})
        with self.assertRaises(AccessError):
            registrant.with_user(self.user_officer).unlink()

    def test_registrant_unlink_manager(self):
        """Test manager can delete registrant records."""
        registrant = self.env["res.partner"].create({"name": "Manager Delete", "is_registrant": True})
        registrant.with_user(self.user_manager).unlink()
        self.assertFalse(registrant.exists())

    def test_id_type_read_viewer(self):
        """Test viewer can read ID types."""
        id_type = self.env["spp.id.type"].create({"name": "Test ID Type"})
        self.assertEqual(id_type.with_user(self.user_viewer).name, "Test ID Type")

    def test_id_type_create_officer(self):
        """Test officer can create ID types (via group_registry_create technical group)."""
        id_type = self.env["spp.id.type"].with_user(self.user_officer).create({"name": "Officer ID Type"})
        self.assertTrue(id_type.exists())

    def test_id_type_create_manager(self):
        """Test manager can create ID types."""
        id_type = self.env["spp.id.type"].with_user(self.user_manager).create({"name": "Manager ID Type"})
        self.assertTrue(id_type.exists())


# =============================================================================
# MODEL ACCESS TESTS - PROGRAMS
# =============================================================================


@tagged("post_install", "-at_install", "access_control")
class TestProgramsModelAccess(TestAccessControlBase):
    """Test CRUD access for programs models."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for programs access tests."""
        super().setUpClass()
        cls.test_program = cls.env["spp.program"].create({"name": "Test Program"})

    def test_program_read_viewer(self):
        """Test viewer can read program records."""
        self.assertEqual(self.test_program.with_user(self.user_viewer).name, "Test Program")

    def test_program_create_viewer_denied(self):
        """Test viewer cannot create programs."""
        with self.assertRaises(AccessError):
            self.env["spp.program"].with_user(self.user_viewer).create({"name": "Unauthorized"})

    def test_program_write_viewer_denied(self):
        """Test viewer cannot modify programs."""
        with self.assertRaises(AccessError):
            self.test_program.with_user(self.user_viewer).write({"name": "Modified"})

    def test_program_create_officer(self):
        """Test officer can create programs."""
        program = self.env["spp.program"].with_user(self.user_officer).create({"name": "Officer Program"})
        self.assertTrue(program.exists())

    def test_program_write_officer(self):
        """Test officer can modify programs."""
        self.test_program.with_user(self.user_officer).write({"name": "Modified"})
        self.assertEqual(self.test_program.name, "Modified")

    def test_program_unlink_officer_denied(self):
        """Test officer cannot delete programs."""
        program = self.env["spp.program"].create({"name": "To Delete"})
        with self.assertRaises(AccessError):
            program.with_user(self.user_officer).unlink()

    def test_program_unlink_manager_denied(self):
        """Test manager cannot delete programs (only admin can per ADR-004)."""
        program = self.env["spp.program"].create({"name": "Manager Delete"})
        with self.assertRaises(AccessError):
            program.with_user(self.user_manager).unlink()

    def test_program_unlink_admin(self):
        """Test admin can delete programs."""
        program = self.env["spp.program"].create({"name": "Admin Delete"})
        program.with_user(self.user_admin).unlink()
        self.assertFalse(program.exists())

    def test_cycle_read_viewer(self):
        """Test viewer can read cycle records."""
        from datetime import date, timedelta

        today = date.today()
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.test_program.id,
                "start_date": today,
                "end_date": today + timedelta(days=30),
            }
        )
        self.assertEqual(cycle.with_user(self.user_viewer).name, "Test Cycle")

    def test_cycle_create_officer(self):
        """Test officer can create cycles."""
        from datetime import date, timedelta

        today = date.today()
        cycle = (
            self.env["spp.cycle"]
            .with_user(self.user_officer)
            .create(
                {
                    "name": "Officer Cycle",
                    "program_id": self.test_program.id,
                    "start_date": today,
                    "end_date": today + timedelta(days=30),
                }
            )
        )
        self.assertTrue(cycle.exists())


# =============================================================================
# MODEL ACCESS TESTS - CHANGE REQUESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control")
class TestChangeRequestModelAccess(TestAccessControlBase):
    """Test CRUD access for change request models."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for change request access tests."""
        super().setUpClass()
        cls.test_registrant = cls.env["res.partner"].create({"name": "CR Registrant", "is_registrant": True})
        cls.cr_type = cls.env["spp.change.request.type"].search([], limit=1)
        if not cls.cr_type:
            cls.cr_type = cls.env["spp.change.request.type"].create(
                {
                    "name": "Test CR Type",
                    "code": "test_cr_type",
                    "target_type": "individual",
                    "detail_model": "res.partner",
                    "apply_strategy": "manual",
                }
            )

    def test_cr_read_user(self):
        """Test CR user can read change requests."""
        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.test_registrant.id,
            }
        )
        self.assertTrue(cr.with_user(self.user_viewer).exists())

    def test_cr_create_user(self):
        """Test CR user can create change requests."""
        cr = (
            self.env["spp.change.request"]
            .with_user(self.user_viewer)
            .create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": self.test_registrant.id,
                }
            )
        )
        self.assertTrue(cr.exists())

    def test_cr_unlink_user_denied(self):
        """Test CR user cannot delete change requests."""
        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.test_registrant.id,
            }
        )
        with self.assertRaises(AccessError):
            cr.with_user(self.user_viewer).unlink()

    def test_cr_unlink_manager(self):
        """Test CR manager can delete change requests."""
        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.test_registrant.id,
            }
        )
        cr.with_user(self.user_manager).unlink()
        self.assertFalse(cr.exists())

    def test_cr_type_create_user_denied(self):
        """Test CR user cannot create change request types."""
        with self.assertRaises(AccessError):
            self.env["spp.change.request.type"].with_user(self.user_viewer).create(
                {
                    "name": "Unauthorized",
                    "code": "unauthorized_cr",
                    "target_type": "individual",
                    "detail_model": "res.partner",
                    "apply_strategy": "manual",
                }
            )

    def test_cr_type_create_manager(self):
        """Test CR manager can create change request types."""
        cr_type = (
            self.env["spp.change.request.type"]
            .with_user(self.user_manager)
            .create(
                {
                    "name": "Manager CR Type",
                    "code": "manager_cr_type",
                    "target_type": "individual",
                    "detail_model": "res.partner",
                    "apply_strategy": "manual",
                }
            )
        )
        self.assertTrue(cr_type.exists())


# =============================================================================
# RECORD RULE TESTS - CHANGE REQUESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control")
class TestChangeRequestRecordRules(TestAccessControlBase):
    """Test Change Request record rules (data visibility)."""

    @classmethod
    def setUpClass(cls):
        """Set up test users with specific CR assignments."""
        super().setUpClass()

        cls.test_registrant = cls.env["res.partner"].create(
            {"name": "Record Rule CR Registrant", "is_registrant": True}
        )
        cls.cr_type = cls.env["spp.change.request.type"].search([], limit=1)
        if not cls.cr_type:
            cls.cr_type = cls.env["spp.change.request.type"].create(
                {
                    "name": "Record Rule CR Type",
                    "code": "record_rule_cr_type",
                    "target_type": "individual",
                    "detail_model": "res.partner",
                    "apply_strategy": "manual",
                }
            )

        # Create a second viewer user for isolation testing
        cls.user_viewer2 = cls.env["res.users"].create(
            {
                "name": "Test Viewer 2",
                "login": "test_viewer2_ac",
                "email": "viewer2_ac@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_registry.group_registry_viewer").id),
                    Command.link(cls.env.ref("spp_programs.group_programs_viewer").id),
                    Command.link(cls.env.ref("spp_change_request_v2.group_cr_user").id),
                ],
                "role_line_ids": [],  # Bypass default roles to test explicit group assignments
            }
        )

        # Invalidate cache and refresh user record
        cls.env.invalidate_all()
        cls.user_viewer2 = cls.env["res.users"].browse(cls.user_viewer2.id)

    def test_cr_user_sees_own_crs(self):
        """Test CR user can see their own change requests."""
        cr = (
            self.env["spp.change.request"]
            .with_user(self.user_viewer)
            .create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": self.test_registrant.id,
                }
            )
        )
        viewer_crs = self.env["spp.change.request"].with_user(self.user_viewer).search([("id", "=", cr.id)])
        self.assertIn(cr, viewer_crs)

    def test_cr_user_cannot_see_other_user_crs(self):
        """Test CR user cannot see other user's change requests."""
        cr = (
            self.env["spp.change.request"]
            .with_user(self.user_viewer2)
            .create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": self.test_registrant.id,
                }
            )
        )
        viewer1_crs = self.env["spp.change.request"].with_user(self.user_viewer).search([("id", "=", cr.id)])
        self.assertNotIn(cr, viewer1_crs)

    def test_validator_sees_all_crs(self):
        """Test CR validator can see all change requests regardless of creator."""
        cr1 = (
            self.env["spp.change.request"]
            .with_user(self.user_viewer)
            .create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": self.test_registrant.id,
                }
            )
        )
        cr2 = (
            self.env["spp.change.request"]
            .with_user(self.user_viewer2)
            .create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": self.test_registrant.id,
                }
            )
        )
        validator_crs = (
            self.env["spp.change.request"].with_user(self.user_validator).search([("id", "in", [cr1.id, cr2.id])])
        )
        self.assertIn(cr1, validator_crs)
        self.assertIn(cr2, validator_crs)

    def test_manager_sees_all_crs(self):
        """Test CR manager can see all change requests."""
        cr1 = (
            self.env["spp.change.request"]
            .with_user(self.user_viewer)
            .create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": self.test_registrant.id,
                }
            )
        )
        cr2 = (
            self.env["spp.change.request"]
            .with_user(self.user_viewer2)
            .create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": self.test_registrant.id,
                }
            )
        )
        manager_crs = (
            self.env["spp.change.request"].with_user(self.user_manager).search([("id", "in", [cr1.id, cr2.id])])
        )
        self.assertIn(cr1, manager_crs)
        self.assertIn(cr2, manager_crs)


# =============================================================================
# MENU VISIBILITY TESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control")
class TestMenuVisibility(TestAccessControlBase):
    """Test menu visibility per role.

    IMPORTANT: These tests validate that XML menu definitions have correct
    group restrictions. If tests fail, FIX THE XML - don't modify these tests
    to programmatically set groups (that would be testing the test setup,
    not the actual system).

    If a menu visibility test fails after module changes, it means the
    XML data needs to be corrected, not that the test should be "fixed".
    """

    def _get_visible_menus(self, user):
        """Helper to get all menus visible to a user."""
        return self.env["ir.ui.menu"].with_user(user).search([])

    # === Registry Menu Visibility ===

    def test_registry_menu_visible_to_viewer(self):
        """Test registry root menu is visible to viewer."""
        visible_menus = self._get_visible_menus(self.user_viewer)
        registry_menu = self.env.ref("spp_registry.spp_main_menu_root")
        self.assertIn(registry_menu, visible_menus)

    def test_registry_menu_visible_to_officer(self):
        """Test registry menu is visible to officer."""
        visible_menus = self._get_visible_menus(self.user_officer)
        registry_menu = self.env.ref("spp_registry.spp_main_menu_root")
        self.assertIn(registry_menu, visible_menus)

    def test_registry_menu_visible_to_manager(self):
        """Test registry menu is visible to manager."""
        visible_menus = self._get_visible_menus(self.user_manager)
        registry_menu = self.env.ref("spp_registry.spp_main_menu_root")
        self.assertIn(registry_menu, visible_menus)

    def test_registry_config_visible_to_manager(self):
        """Test registry config menu visible to manager (manager-only)."""
        visible_menus = self._get_visible_menus(self.user_manager)
        config_menu = self.env.ref("spp_registry.spp_configuration_menu_root")
        self.assertIn(config_menu, visible_menus)

    # === Programs Menu Visibility ===

    def test_programs_menu_visible_to_viewer(self):
        """Test programs menu visible to viewer."""
        visible_menus = self._get_visible_menus(self.user_viewer)
        programs_menu = self.env.ref("spp_programs.spp_program_menu_root")
        self.assertIn(programs_menu, visible_menus)

    def test_programs_list_visible_to_manager(self):
        """Test programs list menu visible to manager."""
        visible_menus = self._get_visible_menus(self.user_manager)
        programs_list = self.env.ref("spp_programs.menu_program_list")
        self.assertIn(programs_list, visible_menus)

    def test_programs_list_visible_to_admin(self):
        """Test programs list menu visible to admin."""
        visible_menus = self._get_visible_menus(self.user_admin)
        programs_list = self.env.ref("spp_programs.menu_program_list")
        self.assertIn(programs_list, visible_menus)

    # === Change Request Menu Visibility ===

    def test_cr_menu_visible_to_user(self):
        """Test CR menu visible to CR user."""
        visible_menus = self._get_visible_menus(self.user_viewer)
        cr_menu = self.env.ref("spp_change_request_v2.menu_change_request_root")
        self.assertIn(cr_menu, visible_menus)

    def test_cr_pending_visible_to_validator(self):
        """Test CR pending menu visible to validator."""
        visible_menus = self._get_visible_menus(self.user_validator)
        pending_menu = self.env.ref("spp_change_request_v2.menu_pending_change_requests")
        self.assertIn(pending_menu, visible_menus)

    def test_cr_config_visible_to_manager(self):
        """Test CR config menu visible to manager."""
        visible_menus = self._get_visible_menus(self.user_manager)
        config_menu = self.env.ref("spp_change_request_v2.menu_change_request_config")
        self.assertIn(config_menu, visible_menus)


# =============================================================================
# BASIC USER DENIED TESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control")
class TestBasicUserDenied(TestAccessControlBase):
    """Test that basic users without domain groups have no access."""

    def test_basic_cannot_read_programs(self):
        """Test basic user cannot read programs."""
        program = self.env["spp.program"].create({"name": "Test"})
        with self.assertRaises(AccessError):
            program.with_user(self.user_basic).read(["name"])

    def test_basic_cannot_create_registrant(self):
        """Test basic user cannot create registrants."""
        with self.assertRaises(AccessError):
            self.env["res.partner"].with_user(self.user_basic).create({"name": "Unauthorized", "is_registrant": True})

    def test_basic_cannot_create_cr(self):
        """Test basic user cannot create change requests."""
        registrant = self.env["res.partner"].create({"name": "Test", "is_registrant": True})
        cr_type = self.env["spp.change.request.type"].search([], limit=1)
        if cr_type:
            with self.assertRaises(AccessError):
                self.env["spp.change.request"].with_user(self.user_basic).create(
                    {"request_type_id": cr_type.id, "registrant_id": registrant.id}
                )


# =============================================================================
# ADMIN ACCESS TESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control")
class TestAdminFullAccess(TestAccessControlBase):
    """Test that admin has full access across all domains."""

    def test_admin_create_delete_registrant(self):
        """Test admin can create and delete registrants."""
        registrant = (
            self.env["res.partner"].with_user(self.user_admin).create({"name": "Admin Test", "is_registrant": True})
        )
        self.assertTrue(registrant.exists())
        registrant.with_user(self.user_admin).unlink()
        self.assertFalse(registrant.exists())

    def test_admin_create_delete_program(self):
        """Test admin can create and delete programs."""
        program = self.env["spp.program"].with_user(self.user_admin).create({"name": "Admin Program"})
        self.assertTrue(program.exists())
        program.with_user(self.user_admin).unlink()
        self.assertFalse(program.exists())

    def test_admin_sees_all_config_menus(self):
        """Test admin sees all configuration menus."""
        visible_menus = self.env["ir.ui.menu"].with_user(self.user_admin).search([])

        # Registry config
        registry_config = self.env.ref("spp_registry.spp_configuration_menu_root")
        self.assertIn(registry_config, visible_menus)

        # CR config
        cr_config = self.env.ref("spp_change_request_v2.menu_change_request_config")
        self.assertIn(cr_config, visible_menus)
