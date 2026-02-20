# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestSimulationScenarioTemplate(SimulationTestCommon):
    """Tests for spp.simulation.scenario.template model."""

    def test_create_template(self):
        """Test basic template creation."""
        template = self.env["spp.simulation.scenario.template"].create(
            {
                "name": "Age Template",
                "category": "age",
                "target_type": "individual",
                "targeting_expression": "age_years(r.birthdate) >= 60",
                "default_amount": 1000.0,
            }
        )
        self.assertEqual(template.category, "age")
        self.assertEqual(template.target_type, "individual")
        self.assertTrue(template.active)

    def test_template_categories(self):
        """Test all template categories can be created."""
        categories = ["age", "geographic", "vulnerability", "economic", "categorical"]
        for category in categories:
            template = self.env["spp.simulation.scenario.template"].create(
                {
                    "name": f"Template {category}",
                    "category": category,
                    "target_type": "group",
                    "targeting_expression": "true",
                }
            )
            self.assertEqual(template.category, category)

    def test_template_archive(self):
        """Test template can be archived."""
        self.template.active = False
        self.assertFalse(self.template.active)

    def test_template_default_icon(self):
        """Test that template has a default icon."""
        template = self.env["spp.simulation.scenario.template"].create(
            {
                "name": "Default Icon Test",
                "category": "age",
                "target_type": "group",
                "targeting_expression": "true",
            }
        )
        self.assertEqual(template.icon, "fa-users")

    def test_builtin_templates_loaded(self):
        """Test that built-in templates are loaded from data."""
        templates = self.env["spp.simulation.scenario.template"].search([])
        # We create one in common.py and there are 6 in scenario_templates.xml
        self.assertGreaterEqual(len(templates), 7)
