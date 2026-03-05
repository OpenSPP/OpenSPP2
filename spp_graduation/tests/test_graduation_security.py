"""Security tests for graduation module."""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGraduationSecurity(TransactionCase):
    """Test access control for graduation records."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create(
            {
                "name": "Graduation User",
                "login": "test_graduation_user",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_graduation.group_spp_graduation_user").id),
                ],
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Graduation Manager",
                "login": "test_graduation_manager",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_graduation.group_spp_graduation_manager").id),
                ],
            }
        )
        # Create test beneficiary for assessments
        cls.beneficiary = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary",
            }
        )

    def test_group_hierarchy_manager_has_user(self):
        """Test manager inherits user permissions."""
        self.assertTrue(
            self.manager.has_group("spp_graduation.group_spp_graduation_user"), "Manager should have user permissions"
        )

    def test_admin_has_manager(self):
        """Test OpenSPP admin has graduation manager access."""
        admin = self.env["res.users"].create(
            {
                "name": "Admin Test",
                "login": "test_admin_graduation",
                "group_ids": [
                    Command.link(self.env.ref("spp_security.group_spp_admin").id),
                ],
            }
        )
        self.assertTrue(
            admin.has_group("spp_graduation.group_spp_graduation_manager"),
            "Admin should have graduation manager access",
        )

    def test_user_sees_own_assessments(self):
        """Test user sees own assessments."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        assessment = self.env["spp.graduation.assessment"].create(
            {
                "name": "Test Assessment",
                "pathway_id": pathway.id,
                "partner_id": self.beneficiary.id,
                "assessor_id": self.user.id,
            }
        )
        assessments_as_user = self.env["spp.graduation.assessment"].with_user(self.user).search([])
        self.assertIn(assessment, assessments_as_user, "User should see own assessments")

    def test_manager_sees_all_assessments(self):
        """Test manager sees all assessments."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        assessment1 = self.env["spp.graduation.assessment"].create(
            {
                "name": "Assessment 1",
                "pathway_id": pathway.id,
                "partner_id": self.beneficiary.id,
                "assessor_id": self.user.id,
            }
        )
        assessment2 = self.env["spp.graduation.assessment"].create(
            {
                "name": "Assessment 2",
                "pathway_id": pathway.id,
                "partner_id": self.beneficiary.id,
                "assessor_id": self.manager.id,
            }
        )
        assessments_as_manager = self.env["spp.graduation.assessment"].with_user(self.manager).search([])
        self.assertIn(assessment1, assessments_as_manager, "Manager should see all assessments")
        self.assertIn(assessment2, assessments_as_manager, "Manager should see all assessments")

    def test_user_can_read_pathways(self):
        """Test user can read pathways."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        pathway_as_user = pathway.with_user(self.user)
        self.assertEqual(pathway_as_user.name, "Test Pathway")

    def test_user_cannot_write_pathways(self):
        """Test user cannot write pathways."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        with self.assertRaises(AccessError):
            pathway.with_user(self.user).write({"name": "Modified"})

    def test_manager_can_write_pathways(self):
        """Test manager can write pathways."""
        pathway = self.env["spp.graduation.pathway"].create(
            {
                "name": "Test Pathway",
            }
        )
        pathway.with_user(self.manager).write({"name": "Modified by Manager"})
        self.assertEqual(pathway.name, "Modified by Manager")
