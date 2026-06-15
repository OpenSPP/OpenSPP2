# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Install / view-load sanity tests for spp_indicator_studio.

This is a UI-bridge module — it ships act_window actions and form/list
views for ``spp.indicator`` and ``spp.indicator.category`` but no Python
models or methods of its own. The tests verify the install path and that
the headline view + action records loaded.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSppIndicatorStudio(TransactionCase):
    def test_module_is_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "spp_indicator_studio")], limit=1)
        self.assertTrue(module, "spp_indicator_studio not registered")
        self.assertEqual(
            module.state,
            "installed",
            f"spp_indicator_studio expected 'installed', got {module.state}",
        )

    def test_indicator_views_loaded(self):
        """views/indicator_views.xml declares list/form/kanban/action records."""
        for xml_id in (
            "spp_indicator_studio.spp_statistic_view_list",
            "spp_indicator_studio.spp_statistic_view_form",
            "spp_indicator_studio.spp_statistic_view_kanban",
            "spp_indicator_studio.spp_statistic_action",
        ):
            with self.subTest(record=xml_id):
                self.assertTrue(
                    self.env.ref(xml_id, raise_if_not_found=False),
                    f"{xml_id} missing — indicator_views.xml didn't load",
                )

    def test_indicator_category_views_loaded(self):
        """views/indicator_category_views.xml declares list/form/action records."""
        for xml_id in (
            "spp_indicator_studio.spp_metric_category_view_list",
            "spp_indicator_studio.spp_metric_category_view_form",
            "spp_indicator_studio.spp_metric_category_action",
        ):
            with self.subTest(record=xml_id):
                self.assertTrue(
                    self.env.ref(xml_id, raise_if_not_found=False),
                    f"{xml_id} missing — indicator_category_views.xml didn't load",
                )

    def test_indicator_action_targets_spp_indicator(self):
        """The act_window must point at the spp.indicator model."""
        action = self.env.ref("spp_indicator_studio.spp_statistic_action", raise_if_not_found=False)
        self.assertTrue(action)
        self.assertEqual(action.res_model, "spp.indicator")
