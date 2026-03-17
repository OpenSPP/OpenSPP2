# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""
Tests for spp_cel_registry_search module.

Validates:
- Module installation
- Security group hierarchy and implied permissions
- Client action configuration
- Menu item configuration and visibility by role
"""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCelRegistrySearch(TransactionCase):
    """Test security groups, client action, and menu for CEL Registry Search."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Security groups
        cls.group_cel_search_user = cls.env.ref("spp_cel_registry_search.group_cel_search_user")
        cls.group_registry_viewer = cls.env.ref("spp_registry.group_registry_viewer")
        cls.group_registry_officer = cls.env.ref("spp_registry.group_registry_officer")

        # Client action
        cls.action = cls.env.ref("spp_cel_registry_search.action_cel_search_portal")

        # Menu item
        cls.menu = cls.env.ref("spp_cel_registry_search.menu_cel_search_portal")

    # --- Security Group Tests ---

    def test_group_cel_search_user_exists(self):
        """group_cel_search_user should exist after installation."""
        self.assertTrue(self.group_cel_search_user)
        self.assertEqual(self.group_cel_search_user.name, "CEL Search User")

    def test_group_cel_search_user_implies_registry_viewer(self):
        """group_cel_search_user should imply group_registry_viewer."""
        implied_ids = self.group_cel_search_user.implied_ids.ids
        self.assertIn(
            self.group_registry_viewer.id,
            implied_ids,
            "group_cel_search_user should imply group_registry_viewer",
        )

    def test_registry_officer_implies_cel_search_user(self):
        """group_registry_officer should imply group_cel_search_user."""
        implied_ids = self.group_registry_officer.implied_ids.ids
        self.assertIn(
            self.group_cel_search_user.id,
            implied_ids,
            "group_registry_officer should imply group_cel_search_user",
        )

    # --- Client Action Tests ---

    def test_client_action_exists(self):
        """Client action for CEL Search Portal should exist."""
        self.assertTrue(self.action)
        self.assertEqual(self.action.name, "Advanced Search")

    def test_client_action_tag(self):
        """Client action should have the correct tag matching the JS component."""
        self.assertEqual(self.action.tag, "spp_cel_registry_search.cel_search_portal")

    def test_client_action_path(self):
        """Client action should have the correct pretty URL path."""
        self.assertEqual(self.action.path, "registry-cel")

    # --- Menu Item Tests ---

    def test_menu_exists(self):
        """Menu item for CEL Search Portal should exist."""
        self.assertTrue(self.menu)
        self.assertEqual(self.menu.name, "Advanced Search")

    def test_menu_parent(self):
        """Menu should be parented under the registry root menu."""
        registry_root = self.env.ref("spp_registry.spp_main_menu_root")
        self.assertEqual(
            self.menu.parent_id.id,
            registry_root.id,
            "Menu should be under Registry root menu",
        )

    def test_menu_restricted_to_cel_search_group(self):
        """Menu should be restricted to group_cel_search_user."""
        self.assertIn(
            self.group_cel_search_user,
            self.menu.group_ids,
            "Menu should be restricted to group_cel_search_user",
        )

    # --- Menu Visibility by Role ---

    def test_menu_visible_to_cel_search_user(self):
        """A user with group_cel_search_user should see the menu."""
        user = self.env["res.users"].create(
            {
                "name": "Test CEL Search User",
                "login": "test_cel_search_user",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.group_cel_search_user.id),
                ],
            }
        )
        visible_menus = self.env["ir.ui.menu"].with_user(user).search([])
        self.assertIn(
            self.menu,
            visible_menus,
            "Menu should be visible to CEL Search users",
        )

    def test_menu_visible_to_registry_officer(self):
        """A registry officer should see the menu via implied group."""
        user = self.env["res.users"].create(
            {
                "name": "Test Registry Officer",
                "login": "test_registry_officer_cel",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.group_registry_officer.id),
                ],
            }
        )
        # Verify the officer has the CEL search group via implication
        self.assertTrue(
            user.has_group("spp_cel_registry_search.group_cel_search_user"),
            "Registry officer should have CEL Search group via implication",
        )
        visible_menus = self.env["ir.ui.menu"].with_user(user).search([])
        self.assertIn(
            self.menu,
            visible_menus,
            "Menu should be visible to registry officers",
        )

    def test_base_user_does_not_have_cel_search_group(self):
        """A base user without explicit assignment should not have the CEL Search group."""
        user = self.env["res.users"].create(
            {
                "name": "Test Base User",
                "login": "test_base_user_cel",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                ],
            }
        )
        self.assertFalse(
            user.has_group("spp_cel_registry_search.group_cel_search_user"),
            "Base user should not have CEL Search group",
        )

    # --- Access Control Tests ---

    def test_check_search_access_granted(self):
        """check_search_access returns True for CEL Search users."""
        user = self.env["res.users"].create(
            {
                "name": "Test Access User",
                "login": "test_access_cel",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.group_cel_search_user.id),
                ],
            }
        )
        result = self.env["spp.cel.service"].with_user(user).check_search_access()
        self.assertTrue(result)

    def test_check_search_access_denied(self):
        """check_search_access returns False for users without the group."""
        user = self.env["res.users"].create(
            {
                "name": "Test No Access User",
                "login": "test_no_access_cel",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                ],
            }
        )
        result = self.env["spp.cel.service"].with_user(user).check_search_access()
        self.assertFalse(result)

    # --- Compile Expression with Offset Tests ---

    def test_compile_expression_with_offset(self):
        """compile_expression should support offset parameter for pagination."""
        # Create test partners
        for i in range(5):
            self.env["res.partner"].create(
                {"name": f"CelOffsetTest{i}", "is_registrant": True, "is_group": False}
            )
        service = self.env["spp.cel.service"]
        result = service.compile_expression(
            'r.name.startsWith("CelOffsetTest")',
            "registry_individuals",
            limit=2,
            offset=0,
            fields=["id", "name"],
        )
        self.assertTrue(result.get("valid"))
        self.assertEqual(len(result.get("preview_records", [])), 2)
        first_page = result["preview_records"]

        result2 = service.compile_expression(
            'r.name.startsWith("CelOffsetTest")',
            "registry_individuals",
            limit=2,
            offset=2,
            fields=["id", "name"],
        )
        second_page = result2.get("preview_records", [])
        self.assertEqual(len(second_page), 2)
        # Pages should have different records
        first_ids = {r["id"] for r in first_page}
        second_ids = {r["id"] for r in second_page}
        self.assertFalse(first_ids & second_ids, "Pages should not overlap")

    def test_compile_expression_with_phone_numbers(self):
        """compile_expression should enrich preview with phone_number_ids."""
        partner = self.env["res.partner"].create(
            {"name": "CelPhoneTest", "is_registrant": True, "is_group": False}
        )
        # Create phone numbers if spp.phone.number model exists
        if "spp.phone.number" in self.env:
            self.env["spp.phone.number"].create(
                {"partner_id": partner.id, "phone_no": "+1234567890"}
            )
            self.env["spp.phone.number"].create(
                {"partner_id": partner.id, "phone_no": "+0987654321"}
            )

        service = self.env["spp.cel.service"]
        result = service.compile_expression(
            'r.name == "CelPhoneTest"',
            "registry_individuals",
            limit=10,
            fields=["id", "name", "phone_number_ids"],
        )
        self.assertTrue(result.get("valid"))
        records = result.get("preview_records", [])
        self.assertTrue(len(records) > 0)
        rec = records[0]
        if "spp.phone.number" in self.env:
            self.assertIn("phone_numbers", rec)
            self.assertEqual(len(rec["phone_numbers"]), 2)
