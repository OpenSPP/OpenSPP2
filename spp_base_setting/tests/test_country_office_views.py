# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase


class TestCountryOfficeViews(TransactionCase):
    """Test Country Office views and menu items."""

    def setUp(self):
        super().setUp()
        self.company_model = self.env["res.company"]
        self.menu_model = self.env["ir.ui.menu"]
        self.action_model = self.env["ir.actions.act_window"]

    def test_country_office_action_exists(self):
        """Test that Country Office action is defined."""
        action = self.env.ref("spp_base_setting.action_res_country_office", raise_if_not_found=False)
        self.assertTrue(action, "Country Office action should exist")
        self.assertEqual(action.res_model, "res.company", "Action should target res.company")

    def test_country_office_form_view_exists(self):
        """Test that Country Office form view is defined."""
        view = self.env.ref("spp_base_setting.view_country_office_form", raise_if_not_found=False)
        self.assertTrue(view, "Country Office form view should exist")
        self.assertEqual(view.model, "res.company", "View should target res.company")

    def test_country_office_tree_view_exists(self):
        """Test that Country Office tree view is defined."""
        view = self.env.ref("spp_base_setting.view_country_office_tree", raise_if_not_found=False)
        self.assertTrue(view, "Country Office tree view should exist")
        self.assertEqual(view.model, "res.company", "View should target res.company")
