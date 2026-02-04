# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Access control tests for GRM (Grievance/Helpdesk) module.

This file contains all GRM-specific access control tests including:
- Group hierarchy tests
- Model CRUD access tests
- Menu visibility tests
- Basic user denial tests
- Admin access tests
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .test_access_control import TestAccessControlBase


@tagged("post_install", "-at_install", "access_control", "grm")
class TestGRMGroupHierarchy(TestAccessControlBase):
    """Test GRM security group hierarchy."""

    def setUp(self):
        super().setUp()
        if not self.grm_installed:
            self.skipTest("spp_grm module not installed")

    def test_grm_manager_has_officer(self):
        """Test GRM manager inherits officer permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_grm.group_grm_officer"),
            "GRM manager should have officer permissions",
        )

    def test_grm_manager_has_viewer(self):
        """Test GRM manager inherits viewer permissions."""
        self.assertTrue(
            self.user_manager.has_group("spp_grm.group_grm_viewer"),
            "GRM manager should have viewer permissions",
        )

    def test_grm_supervisor_has_officer(self):
        """Test GRM supervisor inherits officer permissions."""
        self.assertTrue(
            self.user_validator.has_group("spp_grm.group_grm_officer"),
            "GRM supervisor should have officer permissions",
        )

    def test_grm_officer_has_viewer(self):
        """Test GRM officer inherits viewer permissions."""
        self.assertTrue(
            self.user_officer.has_group("spp_grm.group_grm_viewer"),
            "GRM officer should have viewer permissions",
        )

    def test_grm_officer_has_write(self):
        """Test GRM officer has write permission."""
        self.assertTrue(
            self.user_officer.has_group("spp_grm.group_grm_write"),
            "GRM officer should have write permission",
        )

    def test_admin_has_grm_manager(self):
        """Test admin inherits GRM manager permissions."""
        self.assertTrue(
            self.user_admin.has_group("spp_grm.group_grm_manager"),
            "Admin should have GRM manager permissions",
        )


@tagged("post_install", "-at_install", "access_control", "grm")
class TestGRMModelAccess(TestAccessControlBase):
    """Test CRUD access for GRM models."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for GRM access tests."""
        super().setUpClass()
        if not cls.grm_installed:
            return

        cls.grm_team = cls.env["spp.grm.team"].create({"name": "Test GRM Team"})
        cls.test_registrant = cls.env["res.partner"].create({"name": "GRM Registrant", "is_registrant": True})

    def setUp(self):
        super().setUp()
        if not self.grm_installed:
            self.skipTest("spp_grm module not installed")

    def test_ticket_read_viewer(self):
        """Test GRM viewer can read tickets."""
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Test Ticket",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_viewer.id,
            }
        )
        self.assertEqual(ticket.with_user(self.user_viewer).name, "Test Ticket")

    def test_ticket_create_viewer_denied(self):
        """Test GRM viewer cannot create tickets."""
        with self.assertRaises(AccessError):
            self.env["spp.grm.ticket"].with_user(self.user_viewer).create(
                {"name": "Unauthorized", "partner_id": self.test_registrant.id}
            )

    def test_ticket_create_officer(self):
        """Test GRM officer can create tickets."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_user(self.user_officer)
            .create({"name": "Officer Ticket", "partner_id": self.test_registrant.id})
        )
        self.assertTrue(ticket.exists())

    def test_ticket_write_officer(self):
        """Test GRM officer can modify tickets."""
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Test Ticket",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_officer.id,
            }
        )
        ticket.with_user(self.user_officer).write({"name": "Modified"})
        self.assertEqual(ticket.name, "Modified")

    def test_ticket_unlink_officer_denied(self):
        """Test GRM officer cannot delete tickets."""
        ticket = self.env["spp.grm.ticket"].create({"name": "To Delete", "partner_id": self.test_registrant.id})
        with self.assertRaises(AccessError):
            ticket.with_user(self.user_officer).unlink()

    def test_ticket_unlink_manager(self):
        """Test GRM manager can delete tickets."""
        ticket = self.env["spp.grm.ticket"].create({"name": "Manager Delete", "partner_id": self.test_registrant.id})
        ticket.with_user(self.user_manager).unlink()
        self.assertFalse(ticket.exists())

    def test_ticket_stage_read_viewer(self):
        """Test viewer can read ticket stages."""
        stage = self.env["spp.grm.ticket.stage"].create({"name": "Test Stage"})
        self.assertEqual(stage.with_user(self.user_viewer).name, "Test Stage")

    def test_ticket_stage_create_officer_denied(self):
        """Test officer cannot create ticket stages (config)."""
        with self.assertRaises(AccessError):
            self.env["spp.grm.ticket.stage"].with_user(self.user_officer).create({"name": "Unauthorized Stage"})

    def test_ticket_stage_create_manager(self):
        """Test manager can create ticket stages."""
        stage = self.env["spp.grm.ticket.stage"].with_user(self.user_manager).create({"name": "Manager Stage"})
        self.assertTrue(stage.exists())

    def test_team_read_viewer(self):
        """Test viewer can read GRM teams."""
        self.assertEqual(self.grm_team.with_user(self.user_viewer).name, "Test GRM Team")

    def test_team_create_officer_denied(self):
        """Test officer cannot create GRM teams (config)."""
        with self.assertRaises(AccessError):
            self.env["spp.grm.team"].with_user(self.user_officer).create({"name": "Unauthorized Team"})

    def test_team_create_manager(self):
        """Test manager can create GRM teams."""
        team = self.env["spp.grm.team"].with_user(self.user_manager).create({"name": "Manager Team"})
        self.assertTrue(team.exists())

    def test_category_read_viewer(self):
        """Test viewer can read ticket categories."""
        category = self.env["spp.grm.ticket.category"].create({"name": "Test Category"})
        self.assertEqual(category.with_user(self.user_viewer).name, "Test Category")

    def test_category_create_officer_denied(self):
        """Test officer cannot create ticket categories (config)."""
        with self.assertRaises(AccessError):
            self.env["spp.grm.ticket.category"].with_user(self.user_officer).create({"name": "Unauthorized Category"})

    def test_category_create_manager(self):
        """Test manager can create ticket categories."""
        category = self.env["spp.grm.ticket.category"].with_user(self.user_manager).create({"name": "Manager Category"})
        self.assertTrue(category.exists())


@tagged("post_install", "-at_install", "access_control", "grm")
class TestGRMRecordRules(TestAccessControlBase):
    """Test GRM record rules for ticket visibility."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for GRM record rule tests."""
        super().setUpClass()
        if not cls.grm_installed:
            return

        # Create test registrant
        cls.test_registrant = cls.env["res.partner"].create(
            {"name": "GRM Record Rule Test Registrant", "is_registrant": True}
        )

        # Create users for record rule testing
        # Viewer 1 - will be assigned tickets
        cls.user_viewer_1 = cls.env["res.users"].create(
            {
                "name": "Test Viewer 1",
                "login": "test_viewer_1_grm_rr",
                "email": "viewer1_grm_rr@test.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("spp_grm.group_grm_viewer").id),
                ],
            }
        )

        # Viewer 2 - will not be assigned tickets
        cls.user_viewer_2 = cls.env["res.users"].create(
            {
                "name": "Test Viewer 2",
                "login": "test_viewer_2_grm_rr",
                "email": "viewer2_grm_rr@test.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("spp_grm.group_grm_viewer").id),
                ],
            }
        )

        # Officer 1 - member of team A
        cls.user_officer_1 = cls.env["res.users"].create(
            {
                "name": "Test Officer 1",
                "login": "test_officer_1_grm_rr",
                "email": "officer1_grm_rr@test.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("spp_grm.group_grm_officer").id),
                ],
            }
        )

        # Officer 2 - member of team B
        cls.user_officer_2 = cls.env["res.users"].create(
            {
                "name": "Test Officer 2",
                "login": "test_officer_2_grm_rr",
                "email": "officer2_grm_rr@test.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("spp_grm.group_grm_officer").id),
                ],
            }
        )

        # Manager user
        cls.user_manager_rr = cls.env["res.users"].create(
            {
                "name": "Test Manager RR",
                "login": "test_manager_grm_rr",
                "email": "manager_grm_rr@test.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("spp_grm.group_grm_manager").id),
                ],
            }
        )

        # Create teams
        cls.team_a = cls.env["spp.grm.team"].create(
            {
                "name": "Team A",
                "member_ids": [(4, cls.user_officer_1.id)],
            }
        )

        cls.team_b = cls.env["spp.grm.team"].create(
            {
                "name": "Team B",
                "member_ids": [(4, cls.user_officer_2.id)],
            }
        )

    def setUp(self):
        super().setUp()
        if not self.grm_installed:
            self.skipTest("spp_grm module not installed")

    def test_viewer_sees_assigned_tickets(self):
        """Test viewer can see tickets assigned to them."""
        # Create ticket assigned to viewer 1
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Viewer 1 Ticket",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_viewer_1.id,
            }
        )

        # Viewer 1 should see their assigned ticket
        found_tickets = self.env["spp.grm.ticket"].with_user(self.user_viewer_1).search([("id", "=", ticket.id)])
        self.assertEqual(
            len(found_tickets),
            1,
            "Viewer should see tickets assigned to them",
        )
        self.assertEqual(found_tickets.id, ticket.id)

    def test_viewer_cannot_see_unassigned_tickets(self):
        """Test viewer cannot see tickets assigned to others."""
        # Create ticket assigned to viewer 1
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Viewer 1 Ticket",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_viewer_1.id,
            }
        )

        # Viewer 2 should NOT see viewer 1's ticket
        found_tickets = self.env["spp.grm.ticket"].with_user(self.user_viewer_2).search([("id", "=", ticket.id)])
        self.assertEqual(
            len(found_tickets),
            0,
            "Viewer should not see tickets assigned to other users",
        )

    def test_officer_sees_team_tickets(self):
        """Test officer can see tickets from their teams."""
        # Create ticket assigned to team A
        ticket_team_a = self.env["spp.grm.ticket"].create(
            {
                "name": "Team A Ticket",
                "partner_id": self.test_registrant.id,
                "team_id": self.team_a.id,
            }
        )

        # Create ticket assigned to team B
        ticket_team_b = self.env["spp.grm.ticket"].create(
            {
                "name": "Team B Ticket",
                "partner_id": self.test_registrant.id,
                "team_id": self.team_b.id,
            }
        )

        # Officer 1 (member of team A) should see team A ticket
        found_tickets = (
            self.env["spp.grm.ticket"].with_user(self.user_officer_1).search([("id", "=", ticket_team_a.id)])
        )
        self.assertEqual(
            len(found_tickets),
            1,
            "Officer should see tickets from their team",
        )

        # Officer 1 should NOT see team B ticket
        found_tickets = (
            self.env["spp.grm.ticket"].with_user(self.user_officer_1).search([("id", "=", ticket_team_b.id)])
        )
        self.assertEqual(
            len(found_tickets),
            0,
            "Officer should not see tickets from other teams",
        )

        # Officer 1 should also see tickets assigned to them directly
        ticket_assigned = self.env["spp.grm.ticket"].create(
            {
                "name": "Officer 1 Assigned Ticket",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_officer_1.id,
            }
        )
        found_tickets = (
            self.env["spp.grm.ticket"].with_user(self.user_officer_1).search([("id", "=", ticket_assigned.id)])
        )
        self.assertEqual(
            len(found_tickets),
            1,
            "Officer should see tickets assigned to them directly",
        )

    def test_manager_sees_all_tickets(self):
        """Test manager can see all tickets."""
        # Create various tickets
        ticket_viewer = self.env["spp.grm.ticket"].create(
            {
                "name": "Viewer Ticket",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_viewer_1.id,
            }
        )

        ticket_team_a = self.env["spp.grm.ticket"].create(
            {
                "name": "Team A Ticket",
                "partner_id": self.test_registrant.id,
                "team_id": self.team_a.id,
            }
        )

        ticket_unassigned = self.env["spp.grm.ticket"].create(
            {
                "name": "Unassigned Ticket",
                "partner_id": self.test_registrant.id,
            }
        )

        # Manager should see all tickets
        all_test_ticket_ids = [
            ticket_viewer.id,
            ticket_team_a.id,
            ticket_unassigned.id,
        ]
        found_tickets = (
            self.env["spp.grm.ticket"].with_user(self.user_manager_rr).search([("id", "in", all_test_ticket_ids)])
        )
        self.assertEqual(
            len(found_tickets),
            3,
            "Manager should see all tickets regardless of assignment",
        )


@tagged("post_install", "-at_install", "access_control", "grm")
class TestGRMMenuVisibility(TestAccessControlBase):
    """Test GRM menu visibility per role."""

    def setUp(self):
        super().setUp()
        if not self.grm_installed:
            self.skipTest("spp_grm module not installed")

    def _get_visible_menus(self, user):
        return self.env["ir.ui.menu"].with_user(user).search([])

    def test_grm_menu_visible_to_viewer(self):
        """Test GRM menu visible to viewer."""
        visible_menus = self._get_visible_menus(self.user_viewer)
        grm_menu = self.env.ref("spp_grm.spp_grm_ticket_main_menu")
        self.assertIn(grm_menu, visible_menus)

    def test_grm_menu_visible_to_officer(self):
        """Test GRM menu visible to officer."""
        visible_menus = self._get_visible_menus(self.user_officer)
        grm_menu = self.env.ref("spp_grm.spp_grm_ticket_main_menu")
        self.assertIn(grm_menu, visible_menus)

    def test_grm_menu_visible_to_manager(self):
        """Test GRM menu visible to manager."""
        visible_menus = self._get_visible_menus(self.user_manager)
        grm_menu = self.env.ref("spp_grm.spp_grm_ticket_main_menu")
        self.assertIn(grm_menu, visible_menus)

    def test_grm_menu_hidden_from_basic(self):
        """Test GRM menu hidden from basic user."""
        visible_menus = self._get_visible_menus(self.user_basic)
        grm_menu = self.env.ref("spp_grm.spp_grm_ticket_main_menu")
        self.assertNotIn(grm_menu, visible_menus)

    def test_grm_config_visible_to_manager(self):
        """Test GRM config menu visible to manager."""
        visible_menus = self._get_visible_menus(self.user_manager)
        config_menu = self.env.ref("spp_grm.spp_grm_ticket_config_main_menu")
        self.assertIn(config_menu, visible_menus)

    def test_grm_config_hidden_from_officer(self):
        """Test GRM config menu hidden from officer."""
        visible_menus = self._get_visible_menus(self.user_officer)
        config_menu = self.env.ref("spp_grm.spp_grm_ticket_config_main_menu")
        self.assertNotIn(config_menu, visible_menus)

    def test_grm_config_hidden_from_viewer(self):
        """Test GRM config menu hidden from viewer."""
        visible_menus = self._get_visible_menus(self.user_viewer)
        config_menu = self.env.ref("spp_grm.spp_grm_ticket_config_main_menu")
        self.assertNotIn(config_menu, visible_menus)

    def test_grm_config_visible_to_admin(self):
        """Test GRM config menu visible to admin."""
        visible_menus = self._get_visible_menus(self.user_admin)
        config_menu = self.env.ref("spp_grm.spp_grm_ticket_config_main_menu")
        self.assertIn(config_menu, visible_menus)


@tagged("post_install", "-at_install", "access_control", "grm")
class TestGRMBasicUserDenied(TestAccessControlBase):
    """Test basic users have no GRM access."""

    def setUp(self):
        super().setUp()
        if not self.grm_installed:
            self.skipTest("spp_grm module not installed")

    def test_basic_cannot_read_tickets(self):
        """Test basic user cannot read GRM tickets."""
        registrant = self.env["res.partner"].create({"name": "Test", "is_registrant": True})
        ticket = self.env["spp.grm.ticket"].create({"name": "Test", "partner_id": registrant.id})
        with self.assertRaises(AccessError):
            ticket.with_user(self.user_basic).read(["name"])

    def test_basic_cannot_create_tickets(self):
        """Test basic user cannot create GRM tickets."""
        registrant = self.env["res.partner"].create({"name": "Test", "is_registrant": True})
        with self.assertRaises(AccessError):
            self.env["spp.grm.ticket"].with_user(self.user_basic).create(
                {"name": "Unauthorized", "partner_id": registrant.id}
            )


@tagged("post_install", "-at_install", "access_control", "grm")
class TestGRMAdminAccess(TestAccessControlBase):
    """Test admin has full GRM access."""

    def setUp(self):
        super().setUp()
        if not self.grm_installed:
            self.skipTest("spp_grm module not installed")

    def test_admin_create_delete_ticket(self):
        """Test admin can create and delete GRM tickets."""
        registrant = self.env["res.partner"].create({"name": "Admin GRM Test", "is_registrant": True})
        ticket = (
            self.env["spp.grm.ticket"]
            .with_user(self.user_admin)
            .create({"name": "Admin Ticket", "partner_id": registrant.id})
        )
        self.assertTrue(ticket.exists())
        ticket.with_user(self.user_admin).unlink()
        self.assertFalse(ticket.exists())

    def test_admin_create_delete_grm_config(self):
        """Test admin can create and delete GRM config."""
        stage = self.env["spp.grm.ticket.stage"].with_user(self.user_admin).create({"name": "Admin Stage"})
        self.assertTrue(stage.exists())
        stage.with_user(self.user_admin).unlink()
        self.assertFalse(stage.exists())

    def test_admin_create_delete_team(self):
        """Test admin can create and delete GRM teams."""
        team = self.env["spp.grm.team"].with_user(self.user_admin).create({"name": "Admin Team"})
        self.assertTrue(team.exists())
        team.with_user(self.user_admin).unlink()
        self.assertFalse(team.exists())

    def test_admin_create_delete_category(self):
        """Test admin can create and delete categories."""
        category = self.env["spp.grm.ticket.category"].with_user(self.user_admin).create({"name": "Admin Category"})
        self.assertTrue(category.exists())
        category.with_user(self.user_admin).unlink()
        self.assertFalse(category.exists())


# =============================================================================
# PORTAL USER SECURITY TESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control", "grm")
class TestGRMPortalUserSecurity(TestAccessControlBase):
    """Test portal user security for GRM.

    Portal users have special access to create/write tickets (for beneficiaries
    submitting grievances). These tests verify proper isolation.
    """

    @classmethod
    def setUpClass(cls):
        """Set up portal users for testing."""
        super().setUpClass()
        if not cls.grm_installed:
            return

        from odoo import Command

        # Create portal user
        cls.user_portal = cls.env["res.users"].create(
            {
                "name": "Test Portal User",
                "login": "test_portal_grm",
                "email": "portal_grm@test.com",
                "group_ids": [Command.link(cls.env.ref("base.group_portal").id)],
            }
        )

        # Create another portal user to test isolation
        cls.user_portal_2 = cls.env["res.users"].create(
            {
                "name": "Test Portal User 2",
                "login": "test_portal_grm_2",
                "email": "portal_grm_2@test.com",
                "group_ids": [Command.link(cls.env.ref("base.group_portal").id)],
            }
        )

        cls.test_registrant = cls.env["res.partner"].create(
            {"name": "Portal GRM Test Registrant", "is_registrant": True}
        )

    def setUp(self):
        super().setUp()
        if not self.grm_installed:
            self.skipTest("spp_grm module not installed")

    def test_portal_can_create_ticket(self):
        """Test portal user can create a GRM ticket.

        This is expected behavior - beneficiaries submit grievances via portal.
        """
        ticket = (
            self.env["spp.grm.ticket"]
            .with_user(self.user_portal)
            .create(
                {
                    "name": "Portal User Grievance",
                    "partner_id": self.test_registrant.id,
                }
            )
        )
        self.assertTrue(ticket.exists())

    def test_portal_cannot_see_other_portal_tickets(self):
        """Test portal users cannot see each other's tickets.

        CRITICAL: Without proper record rules, portal users could see
        all tickets, violating privacy.
        """
        # Portal user 1 creates a ticket
        ticket_portal_1 = (
            self.env["spp.grm.ticket"]
            .with_user(self.user_portal)
            .create(
                {
                    "name": "Portal 1 Ticket",
                    "partner_id": self.test_registrant.id,
                }
            )
        )

        # Portal user 2 should NOT see portal user 1's ticket
        found = self.env["spp.grm.ticket"].with_user(self.user_portal_2).search([("id", "=", ticket_portal_1.id)])
        self.assertEqual(len(found), 0, "Portal user should not see other portal user's tickets")

    def test_portal_cannot_write_other_portal_tickets(self):
        """Test portal user cannot modify tickets created by others."""
        # Create ticket as admin (not by portal user)
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Admin Created Ticket",
                "partner_id": self.test_registrant.id,
            }
        )

        # Portal user should not be able to modify it
        with self.assertRaises(AccessError):
            ticket.with_user(self.user_portal).write({"name": "Modified by Portal"})

    def test_portal_cannot_delete_tickets(self):
        """Test portal user cannot delete tickets."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_user(self.user_portal)
            .create(
                {
                    "name": "Portal Ticket to Delete",
                    "partner_id": self.test_registrant.id,
                }
            )
        )

        with self.assertRaises(AccessError):
            ticket.with_user(self.user_portal).unlink()


# =============================================================================
# CROSS-USER WRITE ATTEMPT TESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control", "grm")
class TestGRMCrossUserWrites(TestAccessControlBase):
    """Test that users cannot modify records they can see but shouldn't write.

    CRITICAL: Record rules control visibility, model access controls CRUD.
    These tests ensure both work together correctly.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        if not cls.grm_installed:
            return

        cls.test_registrant = cls.env["res.partner"].create(
            {"name": "Cross Write Test Registrant", "is_registrant": True}
        )

    def setUp(self):
        super().setUp()
        if not self.grm_installed:
            self.skipTest("spp_grm module not installed")

    def test_viewer_cannot_write_visible_ticket(self):
        """Test viewer cannot modify tickets even if they can see them.

        Viewer has perm_read=1, perm_write=0. Even if a ticket is assigned
        to them (making it visible), they should not be able to modify it.
        """
        # Create ticket assigned to viewer (viewer can see it via record rule)
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Viewer's Ticket",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_viewer.id,
            }
        )

        # Verify viewer can see it
        found = self.env["spp.grm.ticket"].with_user(self.user_viewer).search([("id", "=", ticket.id)])
        self.assertEqual(len(found), 1, "Viewer should see their assigned ticket")

        # But viewer should NOT be able to write to it
        with self.assertRaises(
            AccessError,
            msg="Viewer should not have write access even to visible tickets",
        ):
            ticket.with_user(self.user_viewer).write({"name": "Modified by Viewer"})

    def test_viewer_cannot_unlink_visible_ticket(self):
        """Test viewer cannot delete tickets even if they can see them."""
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Viewer's Ticket to Delete",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_viewer.id,
            }
        )

        with self.assertRaises(
            AccessError,
            msg="Viewer should not have delete access even to visible tickets",
        ):
            ticket.with_user(self.user_viewer).unlink()

    def test_officer_can_write_assigned_ticket(self):
        """Test officer CAN modify tickets assigned to them."""
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Officer's Ticket",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_officer.id,
            }
        )

        # Officer should be able to write
        ticket.with_user(self.user_officer).write({"name": "Modified by Officer"})
        self.assertEqual(ticket.name, "Modified by Officer")

    def test_officer_cannot_delete_ticket(self):
        """Test officer cannot delete tickets (only manager/admin can)."""
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Officer's Ticket",
                "partner_id": self.test_registrant.id,
                "user_id": self.user_officer.id,
            }
        )

        with self.assertRaises(AccessError):
            ticket.with_user(self.user_officer).unlink()


# =============================================================================
# EDGE CASE AND NULL FIELD TESTS
# =============================================================================


@tagged("post_install", "-at_install", "access_control", "grm")
class TestGRMEdgeCases(TestAccessControlBase):
    """Test edge cases and null field handling in record rules.

    These tests verify behavior when team_id, user_id, etc. are empty.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        if not cls.grm_installed:
            return

        cls.test_registrant = cls.env["res.partner"].create(
            {"name": "Edge Case Test Registrant", "is_registrant": True}
        )

    def setUp(self):
        super().setUp()
        if not self.grm_installed:
            self.skipTest("spp_grm module not installed")

    def test_officer_cannot_see_unassigned_tickets(self):
        """Test officer cannot see tickets with no team and no user.

        Officer record rule requires team_id.member_ids or user_id match.
        Unassigned tickets should not be visible.
        """
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Unassigned Ticket",
                "partner_id": self.test_registrant.id,
                # No user_id, no team_id
            }
        )

        found = self.env["spp.grm.ticket"].with_user(self.user_officer).search([("id", "=", ticket.id)])
        self.assertEqual(len(found), 0, "Officer should not see unassigned tickets")

    def test_manager_sees_unassigned_tickets(self):
        """Test manager CAN see unassigned tickets."""
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Unassigned Ticket",
                "partner_id": self.test_registrant.id,
            }
        )

        found = self.env["spp.grm.ticket"].with_user(self.user_manager).search([("id", "=", ticket.id)])
        self.assertEqual(len(found), 1, "Manager should see all tickets including unassigned")
