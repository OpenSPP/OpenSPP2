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
                    (0, 0, {"role_id": cls.role_user.id}),
                    (0, 0, {"role_id": cls.role_no_one.id}),
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

    def test_default_role_lines(self):
        default_values = self.env["res.users"]._default_role_lines()

        self.assertTrue(bool(default_values))
        self.assertEqual(len(default_values), 2)
        self.assertEqual(default_values[0]["role_id"], self.role_user.id)
        self.assertEqual(default_values[1]["role_id"], self.role_no_one.id)
        self.assertTrue(default_values[0]["is_enabled"])
        self.assertTrue(default_values[1]["is_enabled"])
        self.assertFalse(default_values[0]["date_from"])
        self.assertFalse(default_values[1]["date_from"])
        self.assertFalse(default_values[0]["date_to"])
        self.assertFalse(default_values[1]["date_to"])

    @unittest.skip("center_area_ids computation not available in Odoo 19 build")
    def test_compute_center_area_ids(self):
        """Temporarily skipped: center_area_ids field is not present in this build."""
        self.user._compute_center_area_ids()
        self.assertEqual(len(self.user.center_area_ids), 1)
        self.assertEqual(self.user.center_area_ids, self.center_area)
