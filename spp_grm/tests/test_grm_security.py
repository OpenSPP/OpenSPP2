"""Security tests for GRM module."""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGRMSecurity(TransactionCase):
    """Test access control for GRM ticket records."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer = cls.env["res.users"].create(
            {
                "name": "GRM Viewer",
                "login": "test_grm_viewer",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_grm.group_grm_viewer").id),
                ],
            }
        )
        cls.officer = cls.env["res.users"].create(
            {
                "name": "GRM Officer",
                "login": "test_grm_officer",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_grm.group_grm_officer").id),
                ],
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "GRM Manager",
                "login": "test_grm_manager",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_grm.group_grm_manager").id),
                ],
            }
        )
        # Create test registrants for tickets
        cls.test_partner1 = cls.env["res.partner"].create(
            {
                "name": "Test Registrant 1",
                "is_registrant": True,
            }
        )
        cls.test_partner2 = cls.env["res.partner"].create(
            {
                "name": "Test Registrant 2",
                "is_registrant": True,
            }
        )

    def test_group_hierarchy_manager_has_officer(self):
        """Test manager inherits officer permissions."""
        self.assertTrue(
            self.manager.has_group("spp_grm.group_grm_officer"),
            "Manager should have officer permissions",
        )

    def test_group_hierarchy_manager_has_viewer(self):
        """Test manager inherits viewer permissions."""
        self.assertTrue(
            self.manager.has_group("spp_grm.group_grm_viewer"),
            "Manager should have viewer permissions",
        )

    def test_group_hierarchy_officer_has_viewer(self):
        """Test officer inherits viewer permissions."""
        self.assertTrue(
            self.officer.has_group("spp_grm.group_grm_viewer"),
            "Officer should have viewer permissions",
        )

    def test_admin_has_manager(self):
        """Test OpenSPP admin has GRM manager access."""
        admin = self.env["res.users"].create(
            {
                "name": "Admin Test",
                "login": "test_admin_grm",
                "group_ids": [
                    Command.link(self.env.ref("spp_security.group_spp_admin").id),
                ],
            }
        )
        self.assertTrue(
            admin.has_group("spp_grm.group_grm_manager"),
            "Admin should have GRM manager access",
        )

    def test_user_sees_own_tickets(self):
        """Test user sees own tickets."""
        ticket = self.env["spp.grm.ticket"].create(
            {
                "name": "Test Ticket",
                "description": "Test Description",
                "user_id": self.officer.id,
                "partner_id": self.test_partner1.id,
            }
        )
        tickets_as_officer = self.env["spp.grm.ticket"].with_user(self.officer).search([])
        self.assertIn(ticket, tickets_as_officer, "Officer should see own tickets")

    def test_manager_sees_all_tickets(self):
        """Test manager sees all tickets."""
        ticket1 = self.env["spp.grm.ticket"].create(
            {
                "name": "Ticket 1",
                "description": "Ticket 1 Description",
                "user_id": self.officer.id,
                "partner_id": self.test_partner1.id,
            }
        )
        ticket2 = self.env["spp.grm.ticket"].create(
            {
                "name": "Ticket 2",
                "description": "Ticket 2 Description",
                "user_id": self.viewer.id,
                "partner_id": self.test_partner2.id,
            }
        )
        tickets_as_manager = self.env["spp.grm.ticket"].with_user(self.manager).search([])
        self.assertIn(ticket1, tickets_as_manager, "Manager should see all tickets")
        self.assertIn(ticket2, tickets_as_manager, "Manager should see all tickets")
