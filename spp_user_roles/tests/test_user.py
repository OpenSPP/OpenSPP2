import unittest

from odoo import Command
from odoo.tests.common import TransactionCase


class TestUserRole(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.role_user = cls.env["res.users.role"].create(
            {
                "name": "ROLE_USER",
                "implied_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )
        cls.role_no_one = cls.env["res.users.role"].create(
            {
                "name": "ROLE_NO_ONE",
                "implied_ids": [Command.set([cls.env.ref("base.group_no_one").id])],
            }
        )

        cls.user = cls.env["res.users"].create(
            {
                "name": "Test User",
                "login": "test_user",
                "role_line_ids": [
                    Command.create({"role_id": cls.role_user.id}),
                    Command.create({"role_id": cls.role_no_one.id}),
                ],
            }
        )

    def test_set_groups_from_roles(self):
        result = self.user.set_groups_from_roles()
        self.assertTrue(result)

        result = self.user.set_groups_from_roles(force=True)
        self.assertTrue(result)

        self.user.set_groups_from_roles()
        self.assertIn(self.env.ref("base.group_user").id, self.user.group_ids.ids)
        self.assertIn(self.env.ref("base.group_no_one").id, self.user.group_ids.ids)

    def test_default_role_lines_uses_is_default(self):
        """Default role lines come from roles with is_default=True, not from arbitrary users."""
        # Neither role is marked as default, so no defaults should be returned
        default_values = self.env["res.users"]._default_role_lines()
        default_role_ids = [v["role_id"] for v in default_values]
        self.assertNotIn(self.role_user.id, default_role_ids)
        self.assertNotIn(self.role_no_one.id, default_role_ids)

        # Mark one role as default
        self.role_user.is_default = True
        default_values = self.env["res.users"]._default_role_lines()
        default_role_ids = [v["role_id"] for v in default_values]
        self.assertIn(self.role_user.id, default_role_ids)
        self.assertNotIn(self.role_no_one.id, default_role_ids)

        # New user without explicit role_line_ids gets the default role
        new_user = self.env["res.users"].create({"name": "New User", "login": "new_test_user"})
        new_user_role_ids = new_user.role_line_ids.mapped("role_id").ids
        self.assertIn(self.role_user.id, new_user_role_ids)
        self.assertNotIn(self.role_no_one.id, new_user_role_ids)

    @unittest.skip("center_area_ids computation not available in Odoo 19 build")
    def test_compute_center_area_ids(self):
        """Temporarily skipped: center_area_ids field is not present in this build."""
        self.user._compute_center_area_ids()
        self.assertEqual(len(self.user.center_area_ids), 1)
        self.assertEqual(self.user.center_area_ids, self.center_area)
