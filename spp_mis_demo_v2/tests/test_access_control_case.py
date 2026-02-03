# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Access control tests for Case Management module.

This file contains all Case Management-specific access control tests including:
- Group hierarchy tests
- Model CRUD access tests
- Record rule tests (worker sees own, supervisor sees team, manager sees all)
- Menu visibility tests
- Basic user denial tests
- Admin access tests
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .test_access_control import TestAccessControlBase


@tagged("post_install", "-at_install", "access_control", "case")
class TestCaseGroupHierarchy(TestAccessControlBase):
    """Test Case Management security group hierarchy."""

    def setUp(self):
        super().setUp()
        if not self.case_installed:
            self.skipTest("spp_case_base module not installed")

    def test_case_manager_has_officer(self):
        """Test Case manager inherits officer permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_case_base.group_case_officer"),
            "Case manager should have officer permissions",
        )

    def test_case_manager_has_supervisor(self):
        """Test Case manager inherits supervisor permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_case_base.group_case_supervisor"),
            "Case manager should have supervisor permissions",
        )

    def test_case_manager_has_viewer(self):
        """Test Case manager inherits viewer permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_case_base.group_case_viewer"),
            "Case manager should have viewer permissions",
        )

    def test_case_supervisor_has_worker(self):
        """Test Case supervisor inherits worker permissions."""
        self.assertTrue(
            self.user_validator.has_group("spp_case_base.group_case_worker"),
            "Case supervisor should have worker permissions",
        )

    def test_case_officer_has_viewer(self):
        """Test Case officer inherits viewer permissions."""
        self.assertTrue(
            self.user_officer.has_group("spp_case_base.group_case_viewer"),
            "Case officer should have viewer permissions",
        )

    def test_case_officer_has_write(self):
        """Test Case officer has write permission."""
        self.assertTrue(
            self.user_officer.has_group("spp_case_base.group_case_write"),
            "Case officer should have write permission",
        )

    def test_admin_has_case_manager(self):
        """Test admin inherits Case manager permissions."""
        self.assertTrue(
            self.user_admin.has_group("spp_case_base.group_case_manager"),
            "Admin should have Case manager permissions",
        )


@tagged("post_install", "-at_install", "access_control", "case")
class TestCaseModelAccess(TestAccessControlBase):
    """Test CRUD access for Case Management models."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for Case access tests."""
        super().setUpClass()
        if not cls.case_installed:
            return

        cls.case_team = cls.env["spp.case.team"].create({"name": "Test Case Team"})
        cls.test_registrant = cls.env["res.partner"].create({"name": "Case Registrant", "is_registrant": True})
        cls.case_type = cls.env["spp.case.type"].create({"name": "Test Case Type"})

    def setUp(self):
        super().setUp()
        if not self.case_installed:
            self.skipTest("spp_case_base module not installed")

    def test_case_read_viewer(self):
        """Test Case viewer can read cases."""
        case = self.env["spp.case"].create(
            {
                "name": "Test Case",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_viewer.id,
            }
        )
        self.assertEqual(case.with_user(self.user_viewer).name, "Test Case")

    def test_case_create_viewer_denied(self):
        """Test Case viewer cannot create cases."""
        with self.assertRaises(AccessError):
            self.env["spp.case"].with_user(self.user_viewer).create(
                {
                    "name": "Unauthorized",
                    "partner_id": self.test_registrant.id,
                    "case_type_id": self.case_type.id,
                }
            )

    def test_case_create_officer(self):
        """Test Case officer can create cases."""
        case = (
            self.env["spp.case"]
            .with_user(self.user_officer)
            .create(
                {
                    "name": "Officer Case",
                    "partner_id": self.test_registrant.id,
                    "case_type_id": self.case_type.id,
                }
            )
        )
        self.assertTrue(case.exists())

    def test_case_write_officer(self):
        """Test Case officer can modify cases."""
        case = self.env["spp.case"].create(
            {
                "name": "Test Case",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_officer.id,
            }
        )
        case.with_user(self.user_officer).write({"name": "Modified"})
        self.assertEqual(case.name, "Modified")

    def test_case_unlink_officer_denied(self):
        """Test Case officer cannot delete cases."""
        case = self.env["spp.case"].create(
            {
                "name": "To Delete",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
            }
        )
        with self.assertRaises(AccessError):
            case.with_user(self.user_officer).unlink()

    def test_case_unlink_manager(self):
        """Test Case manager can delete cases."""
        case = self.env["spp.case"].create(
            {
                "name": "Manager Delete",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
            }
        )
        case.with_user(self.user_manager).unlink()
        self.assertFalse(case.exists())

    def test_case_type_read_viewer(self):
        """Test viewer can read case types."""
        self.assertEqual(self.case_type.with_user(self.user_viewer).name, "Test Case Type")

    def test_case_type_create_officer_denied(self):
        """Test officer cannot create case types (config)."""
        with self.assertRaises(AccessError):
            self.env["spp.case.type"].with_user(self.user_officer).create({"name": "Unauthorized Type"})

    def test_case_type_create_manager(self):
        """Test manager can create case types."""
        case_type = self.env["spp.case.type"].with_user(self.user_manager).create({"name": "Manager Type"})
        self.assertTrue(case_type.exists())

    def test_case_team_read_viewer(self):
        """Test viewer can read case teams."""
        self.assertEqual(self.case_team.with_user(self.user_viewer).name, "Test Case Team")

    def test_case_team_create_officer_denied(self):
        """Test officer cannot create case teams (config)."""
        with self.assertRaises(AccessError):
            self.env["spp.case.team"].with_user(self.user_officer).create({"name": "Unauthorized Team"})

    def test_case_team_create_manager(self):
        """Test manager can create case teams."""
        team = self.env["spp.case.team"].with_user(self.user_manager).create({"name": "Manager Team"})
        self.assertTrue(team.exists())

    def test_case_stage_read_viewer(self):
        """Test viewer can read case stages."""
        stage = self.env["spp.case.stage"].create({"name": "Test Stage"})
        self.assertEqual(stage.with_user(self.user_viewer).name, "Test Stage")

    def test_case_stage_create_officer_denied(self):
        """Test officer cannot create case stages (config)."""
        with self.assertRaises(AccessError):
            self.env["spp.case.stage"].with_user(self.user_officer).create({"name": "Unauthorized Stage"})

    def test_case_stage_create_manager(self):
        """Test manager can create case stages."""
        stage = self.env["spp.case.stage"].with_user(self.user_manager).create({"name": "Manager Stage"})
        self.assertTrue(stage.exists())


@tagged("post_install", "-at_install", "access_control", "case")
class TestCaseRecordRules(TestAccessControlBase):
    """Test Case Management record rules (data visibility)."""

    @classmethod
    def setUpClass(cls):
        """Set up test users with specific case assignments."""
        super().setUpClass()
        if not cls.case_installed:
            return

        cls.test_registrant = cls.env["res.partner"].create({"name": "Record Rule Registrant", "is_registrant": True})
        cls.case_type = cls.env["spp.case.type"].create({"name": "Record Rule Case Type"})
        cls.case_team = cls.env["spp.case.team"].create({"name": "Test Team"})

        # Create a worker user for record rule testing
        cls.user_worker = cls.env["res.users"].create(
            {
                "name": "Test Worker",
                "login": "test_worker_ac",
                "email": "worker_ac@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                ],
            }
        )

        # Create another worker for isolation testing
        cls.user_worker2 = cls.env["res.users"].create(
            {
                "name": "Test Worker 2",
                "login": "test_worker2_ac",
                "email": "worker2_ac@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                ],
            }
        )

    def setUp(self):
        super().setUp()
        if not self.case_installed:
            self.skipTest("spp_case_base module not installed")

    def test_worker_sees_own_cases(self):
        """Test worker can see their own cases."""
        case = self.env["spp.case"].create(
            {
                "name": "Worker's Case",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_worker.id,
            }
        )
        worker_cases = self.env["spp.case"].with_user(self.user_worker).search([("id", "=", case.id)])
        self.assertIn(case, worker_cases)

    def test_worker_cannot_see_other_worker_cases(self):
        """Test worker cannot see other worker's cases."""
        case = self.env["spp.case"].create(
            {
                "name": "Other Worker Case",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_worker2.id,
            }
        )
        worker1_cases = self.env["spp.case"].with_user(self.user_worker).search([("id", "=", case.id)])
        self.assertNotIn(case, worker1_cases)

    def test_manager_sees_all_cases(self):
        """Test manager can see all cases regardless of assignment."""
        case1 = self.env["spp.case"].create(
            {
                "name": "Worker1 Case",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_worker.id,
            }
        )
        case2 = self.env["spp.case"].create(
            {
                "name": "Worker2 Case",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_worker2.id,
            }
        )
        manager_cases = self.env["spp.case"].with_user(self.user_manager).search([("id", "in", [case1.id, case2.id])])
        self.assertIn(case1, manager_cases)
        self.assertIn(case2, manager_cases)

    def test_worker_can_write_own_case(self):
        """Test worker can modify their own cases."""
        case = self.env["spp.case"].create(
            {
                "name": "Modifiable Case",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_worker.id,
            }
        )
        case.with_user(self.user_worker).write({"name": "Modified by Worker"})
        self.assertEqual(case.name, "Modified by Worker")

    def test_worker_cannot_delete_own_case(self):
        """Test worker cannot delete even their own cases."""
        case = self.env["spp.case"].create(
            {
                "name": "Cannot Delete",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_worker.id,
            }
        )
        with self.assertRaises(AccessError):
            case.with_user(self.user_worker).unlink()

    def test_supervisor_sees_team_cases(self):
        """Test supervisor can see cases for teams they supervise."""
        # Assign supervisor to the team
        self.case_team.write({"supervisor_id": self.user_validator.id})

        # Create a case assigned to a worker but in the supervisor's team
        case = self.env["spp.case"].create(
            {
                "name": "Team Case",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_worker.id,
                "team_id": self.case_team.id,
            }
        )

        # Verify supervisor can see it
        supervisor_cases = self.env["spp.case"].with_user(self.user_validator).search([("id", "=", case.id)])
        self.assertIn(case, supervisor_cases)

    def test_supervisor_cannot_see_other_team_cases(self):
        """Test supervisor cannot see cases from teams they don't supervise."""
        # Create another team without the supervisor
        other_team = self.env["spp.case.team"].create({"name": "Other Team", "supervisor_id": self.user_worker2.id})

        # Create a case in the other team
        case = self.env["spp.case"].create(
            {
                "name": "Other Team Case",
                "partner_id": self.test_registrant.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.user_worker2.id,
                "team_id": other_team.id,
            }
        )

        # Verify supervisor cannot see it
        supervisor_cases = self.env["spp.case"].with_user(self.user_validator).search([("id", "=", case.id)])
        self.assertNotIn(case, supervisor_cases)


@tagged("post_install", "-at_install", "access_control", "case")
class TestCaseMenuVisibility(TestAccessControlBase):
    """Test Case Management menu visibility per role."""

    def setUp(self):
        super().setUp()
        if not self.case_installed:
            self.skipTest("spp_case_base module not installed")

    def _get_visible_menus(self, user):
        return self.env["ir.ui.menu"].with_user(user).search([])

    def test_case_menu_visible_to_viewer(self):
        """Test Case menu visible to viewer."""
        visible_menus = self._get_visible_menus(self.user_viewer)
        case_menu = self.env.ref("spp_case_base.menu_case_management_root")
        self.assertIn(case_menu, visible_menus)

    def test_case_menu_visible_to_officer(self):
        """Test Case menu visible to officer."""
        visible_menus = self._get_visible_menus(self.user_officer)
        case_menu = self.env.ref("spp_case_base.menu_case_management_root")
        self.assertIn(case_menu, visible_menus)

    def test_case_menu_visible_to_manager(self):
        """Test Case menu visible to manager."""
        visible_menus = self._get_visible_menus(self.user_manager)
        case_menu = self.env.ref("spp_case_base.menu_case_management_root")
        self.assertIn(case_menu, visible_menus)

    def test_case_menu_hidden_from_basic(self):
        """Test Case menu hidden from basic user."""
        visible_menus = self._get_visible_menus(self.user_basic)
        case_menu = self.env.ref("spp_case_base.menu_case_management_root")
        self.assertNotIn(case_menu, visible_menus)

    def test_case_config_visible_to_manager(self):
        """Test Case config menu visible to manager."""
        visible_menus = self._get_visible_menus(self.user_manager)
        config_menu = self.env.ref("spp_case_base.menu_case_management_config")
        self.assertIn(config_menu, visible_menus)

    def test_case_config_hidden_from_officer(self):
        """Test Case config menu hidden from officer."""
        visible_menus = self._get_visible_menus(self.user_officer)
        config_menu = self.env.ref("spp_case_base.menu_case_management_config")
        self.assertNotIn(config_menu, visible_menus)

    def test_case_config_hidden_from_viewer(self):
        """Test Case config menu hidden from viewer."""
        visible_menus = self._get_visible_menus(self.user_viewer)
        config_menu = self.env.ref("spp_case_base.menu_case_management_config")
        self.assertNotIn(config_menu, visible_menus)

    def test_case_config_visible_to_admin(self):
        """Test Case config menu visible to admin."""
        visible_menus = self._get_visible_menus(self.user_admin)
        config_menu = self.env.ref("spp_case_base.menu_case_management_config")
        self.assertIn(config_menu, visible_menus)

    def test_unassigned_cases_visible_to_supervisor(self):
        """Test unassigned cases menu visible to supervisor."""
        visible_menus = self._get_visible_menus(self.user_validator)
        unassigned_menu = self.env.ref("spp_case_base.menu_case_unassigned")
        self.assertIn(unassigned_menu, visible_menus)

    def test_unassigned_cases_visible_to_manager(self):
        """Test unassigned cases menu visible to manager."""
        visible_menus = self._get_visible_menus(self.user_manager)
        unassigned_menu = self.env.ref("spp_case_base.menu_case_unassigned")
        self.assertIn(unassigned_menu, visible_menus)


@tagged("post_install", "-at_install", "access_control", "case")
class TestCaseBasicUserDenied(TestAccessControlBase):
    """Test basic users have no Case Management access."""

    def setUp(self):
        super().setUp()
        if not self.case_installed:
            self.skipTest("spp_case_base module not installed")

    def test_basic_cannot_read_cases(self):
        """Test basic user cannot read cases."""
        registrant = self.env["res.partner"].create({"name": "Test", "is_registrant": True})
        case_type = self.env["spp.case.type"].create({"name": "Test Type"})
        case = self.env["spp.case"].create(
            {
                "name": "Test",
                "partner_id": registrant.id,
                "case_type_id": case_type.id,
            }
        )
        with self.assertRaises(AccessError):
            case.with_user(self.user_basic).read(["name"])

    def test_basic_cannot_create_cases(self):
        """Test basic user cannot create cases."""
        registrant = self.env["res.partner"].create({"name": "Test", "is_registrant": True})
        case_type = self.env["spp.case.type"].create({"name": "Test Type 2"})
        with self.assertRaises(AccessError):
            self.env["spp.case"].with_user(self.user_basic).create(
                {
                    "name": "Unauthorized",
                    "partner_id": registrant.id,
                    "case_type_id": case_type.id,
                }
            )


@tagged("post_install", "-at_install", "access_control", "case")
class TestCaseAdminAccess(TestAccessControlBase):
    """Test admin has full Case Management access."""

    def setUp(self):
        super().setUp()
        if not self.case_installed:
            self.skipTest("spp_case_base module not installed")

    def test_admin_create_delete_case(self):
        """Test admin can create and delete cases."""
        registrant = self.env["res.partner"].create({"name": "Admin Case Test", "is_registrant": True})
        case_type = self.env["spp.case.type"].create({"name": "Admin Test Type"})
        case = (
            self.env["spp.case"]
            .with_user(self.user_admin)
            .create(
                {
                    "name": "Admin Case",
                    "partner_id": registrant.id,
                    "case_type_id": case_type.id,
                }
            )
        )
        self.assertTrue(case.exists())
        case.with_user(self.user_admin).unlink()
        self.assertFalse(case.exists())

    def test_admin_create_delete_case_config(self):
        """Test admin can create and delete case config."""
        case_type = self.env["spp.case.type"].with_user(self.user_admin).create({"name": "Admin Case Type"})
        self.assertTrue(case_type.exists())
        case_type.with_user(self.user_admin).unlink()
        self.assertFalse(case_type.exists())

    def test_admin_create_delete_team(self):
        """Test admin can create and delete case teams."""
        team = self.env["spp.case.team"].with_user(self.user_admin).create({"name": "Admin Team"})
        self.assertTrue(team.exists())
        team.with_user(self.user_admin).unlink()
        self.assertFalse(team.exists())

    def test_admin_create_delete_stage(self):
        """Test admin can create and delete case stages."""
        stage = self.env["spp.case.stage"].with_user(self.user_admin).create({"name": "Admin Stage"})
        self.assertTrue(stage.exists())
        stage.with_user(self.user_admin).unlink()
        self.assertFalse(stage.exists())
