# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
import unittest

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


def skip_if_no_programs(method):
    """Decorator to skip tests if spp_programs module is not installed."""

    def wrapper(self, *args, **kwargs):
        if "spp.program" not in self.env:
            raise unittest.SkipTest("spp_programs module not installed")
        return method(self, *args, **kwargs)

    return wrapper


@tagged("post_install", "-at_install")
class TestGISReportWizard(TransactionCase):
    """Test the GIS report creation wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set context to avoid job queue delay for faster tests
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        # Create test category
        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "Test Category",
                "code": "test",
            }
        )

        # Get res.partner model reference
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        # Create test template
        cls.template = cls.env["spp.gis.report.template"].create(
            {
                "name": "Test Template",
                "code": "test_template",
                "category_id": cls.category.id,
                "description": "Test template description",
                "config": {
                    "source_model": "res.partner",
                    "area_field_path": "area_id",
                    "aggregation_method": "count",
                    "filter_mode": "domain",
                    "filter_domain": "[('is_registrant', '=', True)]",
                    "base_area_level": 2,
                    "normalization_method": "raw",
                    "color_scheme": "viridis",  # Color scheme code (wizard looks up by code)
                    "threshold_mode": "auto_quartile",
                    "enable_rollup": True,
                    "rollup_method": "sum",
                    "rollup_weight_source": "count",
                },
            }
        )

        # Create test template that requires program
        cls.template_program = cls.env["spp.gis.report.template"].create(
            {
                "name": "Program Template",
                "code": "program_template",
                "category_id": cls.category.id,
                "requires_program": True,
                "config": {
                    "source_model": "res.partner",
                    "area_field_path": "area_id",
                    "aggregation_method": "count",
                },
            }
        )

    def test_01_wizard_default_step(self):
        """Test wizard defaults to template selection step."""
        wizard = self.env["spp.gis.report.wizard"].create({})
        self.assertEqual(wizard.step, "template")
        self.assertTrue(wizard.show_step_1)
        self.assertFalse(wizard.show_step_2)
        self.assertFalse(wizard.show_step_3)

    def test_02_wizard_apply_template_defaults(self):
        """Test wizard applies template defaults on create."""
        wizard = self.env["spp.gis.report.wizard"].with_context(default_template_id=self.template.id).create({})

        self.assertEqual(wizard.template_id, self.template)
        self.assertEqual(wizard.name, self.template.name)
        self.assertEqual(wizard.description, self.template.description)
        self.assertEqual(wizard.base_area_level, 2)
        self.assertEqual(wizard.normalization_method, "raw")
        # color_scheme_id should be set from template config (looked up by code)
        self.assertTrue(wizard.color_scheme_id, "Color scheme should be set from template")

    def test_03_wizard_onchange_template(self):
        """Test wizard applies defaults when template changes."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
            }
        )

        # Trigger onchange
        wizard._onchange_template_id()

        self.assertEqual(wizard.name, self.template.name)
        self.assertEqual(wizard.base_area_level, 2)
        self.assertEqual(wizard.normalization_method, "raw")

    def test_04_wizard_step_navigation_forward(self):
        """Test wizard step progression forward."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "name": "Test Report",
            }
        )

        # Start at template step
        self.assertEqual(wizard.step, "template")

        # Move to config step
        result = wizard.action_next()
        self.assertEqual(wizard.step, "config")
        self.assertEqual(result["type"], "ir.actions.act_window")

        # Move to thresholds step
        result = wizard.action_next()
        self.assertEqual(wizard.step, "thresholds")
        self.assertEqual(result["type"], "ir.actions.act_window")

    def test_05_wizard_step_navigation_backward(self):
        """Test wizard step progression backward."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "name": "Test Report",
                "step": "thresholds",
            }
        )

        # Start at thresholds step
        self.assertEqual(wizard.step, "thresholds")

        # Move back to config step
        result = wizard.action_back()
        self.assertEqual(wizard.step, "config")
        self.assertEqual(result["type"], "ir.actions.act_window")

        # Move back to template step
        result = wizard.action_back()
        self.assertEqual(wizard.step, "template")
        self.assertEqual(result["type"], "ir.actions.act_window")

    def test_06_wizard_validation_template_required(self):
        """Test validation requires template selection."""
        wizard = self.env["spp.gis.report.wizard"].create({})

        with self.assertRaises(ValidationError) as cm:
            wizard.action_next()

        self.assertIn("template", str(cm.exception).lower())

    def test_07_wizard_validation_name_required(self):
        """Test validation requires report name."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "step": "config",
                "name": "",
            }
        )

        with self.assertRaises(ValidationError) as cm:
            wizard.action_next()

        self.assertIn("name", str(cm.exception).lower())

    @skip_if_no_programs
    def test_08_wizard_validation_program_required(self):
        """Test validation requires program when template requires it.

        Note: This test only runs when spp_programs is installed because
        the program_id field is added by the spp_gis_report_programs glue module.
        """
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template_program.id,
                "step": "config",
                "name": "Test Report",
            }
        )

        with self.assertRaises(ValidationError) as cm:
            wizard.action_next()

        self.assertIn("program", str(cm.exception).lower())

    def test_09_wizard_validation_base_area_level(self):
        """Test validation requires valid base area level."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "step": "config",
                "name": "Test Report",
                "base_area_level": -1,
            }
        )

        with self.assertRaises(ValidationError) as cm:
            wizard.action_next()

        self.assertIn("level", str(cm.exception).lower())

    def test_10_wizard_create_report_basic(self):
        """Test creating a report from wizard."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "name": "Wizard Created Report",
                "description": "Created via wizard",
                "base_area_level": 2,
                "normalization_method": "raw",
                "enable_rollup": True,
                "threshold_mode": "auto_quartile",
                "refresh_mode": "scheduled",
                "refresh_interval": "daily",
            }
        )

        result = wizard.action_create_report()

        # Check result is an action
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.gis.report")

        # Check report was created
        report = self.env["spp.gis.report"].browse(result["res_id"])
        self.assertTrue(report.exists())
        self.assertEqual(report.name, "Wizard Created Report")
        self.assertEqual(report.template_id, self.template)
        self.assertEqual(report.base_area_level, 2)

    @skip_if_no_programs
    def test_11_wizard_create_report_with_program(self):
        """Test creating a report with program context."""
        # Create a test program
        program = self.env["spp.program"].create(
            {
                "name": "Test Program",
            }
        )

        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template_program.id,
                "name": "Program Report",
                "program_id": program.id,
                "base_area_level": 2,
            }
        )

        result = wizard.action_create_report()

        # Check report was created with program
        report = self.env["spp.gis.report"].browse(result["res_id"])
        self.assertEqual(report.program_id, program)

    def test_12_wizard_code_generation(self):
        """Test unique code generation."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "name": "Code Test Report",
                "base_area_level": 2,
            }
        )

        code = wizard._generate_report_code()

        # Code should be based on template code
        self.assertTrue(code.startswith(self.template.code))

        # Code should be unique
        existing = self.env["spp.gis.report"].search([("code", "=", code)])
        self.assertEqual(len(existing), 0)

    @skip_if_no_programs
    def test_13_wizard_code_generation_with_program(self):
        """Test code generation includes program suffix."""
        program = self.env["spp.program"].create(
            {
                "name": "Test Program",
            }
        )

        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "name": "Program Code Test",
                "program_id": program.id,
                "base_area_level": 2,
            }
        )

        code = wizard._generate_report_code()

        # Code should include program ID suffix
        self.assertIn(str(program.id), code)

    def test_14_wizard_code_uniqueness(self):
        """Test code generation ensures uniqueness."""
        # Create first report
        wizard1 = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "name": "First Report",
                "base_area_level": 2,
            }
        )
        result1 = wizard1.action_create_report()
        report1 = self.env["spp.gis.report"].browse(result1["res_id"])

        # Create second report with same template
        wizard2 = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "name": "Second Report",
                "base_area_level": 2,
            }
        )
        code2 = wizard2._generate_report_code()

        # Codes should be different
        self.assertNotEqual(report1.code, code2)

    def test_15_wizard_prepare_report_vals(self):
        """Test preparation of report values from wizard."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "name": "Vals Test",
                "description": "Test description",
                "base_area_level": 2,
                "normalization_method": "per_area_sqkm",
                "enable_rollup": True,
                "disaggregate_by_gender": True,
                "threshold_mode": "auto_quartile",
                "refresh_mode": "scheduled",
                "refresh_interval": "hourly",
            }
        )

        vals = wizard._prepare_report_vals()

        # Check basic fields
        self.assertEqual(vals["name"], "Vals Test")
        self.assertEqual(vals["description"], "Test description")
        self.assertEqual(vals["category_id"], self.category.id)
        self.assertEqual(vals["template_id"], self.template.id)

        # Check configuration fields
        self.assertEqual(vals["base_area_level"], 2)
        self.assertEqual(vals["normalization_method"], "per_area_sqkm")
        self.assertTrue(vals["enable_rollup"])
        self.assertTrue(vals["disaggregate_by_gender"])

        # Check threshold fields
        self.assertEqual(vals["threshold_mode"], "auto_quartile")
        # Color scheme is now a Many2one ID
        self.assertIn("color_scheme_id", vals)

        # Check refresh fields
        self.assertEqual(vals["refresh_mode"], "scheduled")
        self.assertEqual(vals["refresh_interval"], "hourly")

        # Check template config extraction
        self.assertEqual(vals["source_model_id"], self.partner_model.id)
        self.assertEqual(vals["area_field_path"], "area_id")
        self.assertEqual(vals["aggregation_method"], "count")
        self.assertEqual(vals["filter_mode"], "domain")

    def test_16_wizard_template_action(self):
        """Test template action to open wizard."""
        result = self.template.action_create_report()

        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.gis.report.wizard")
        self.assertEqual(result["view_mode"], "form")
        self.assertEqual(result["target"], "new")
        self.assertEqual(result["context"]["default_template_id"], self.template.id)

    def test_17_wizard_no_template_error(self):
        """Test creating report without template raises error."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "name": "No Template Report",
                "base_area_level": 2,
            }
        )

        with self.assertRaises(UserError) as cm:
            wizard.action_create_report()

        self.assertIn("template", str(cm.exception).lower())

    def test_18_wizard_disaggregation_options(self):
        """Test disaggregation options are properly set."""
        wizard = self.env["spp.gis.report.wizard"].create(
            {
                "template_id": self.template.id,
                "name": "Disaggregation Test",
                "base_area_level": 2,
                "disaggregate_by_gender": True,
                "disaggregate_by_age": True,
            }
        )

        result = wizard.action_create_report()
        report = self.env["spp.gis.report"].browse(result["res_id"])

        self.assertTrue(report.disaggregate_by_gender)
        self.assertTrue(report.disaggregate_by_age)

    def test_19_wizard_color_schemes(self):
        """Test different color scheme options."""
        # Get available color schemes
        color_schemes = self.env["spp.gis.color.scheme"].search([], limit=3)
        self.assertTrue(len(color_schemes) > 0, "Color schemes should be available")

        for scheme in color_schemes:
            wizard = self.env["spp.gis.report.wizard"].create(
                {
                    "template_id": self.template.id,
                    "name": f"Color Scheme {scheme.code}",
                    "base_area_level": 2,
                    "color_scheme_id": scheme.id,
                }
            )

            result = wizard.action_create_report()
            report = self.env["spp.gis.report"].browse(result["res_id"])

            self.assertEqual(report.color_scheme_id, scheme)

    def test_20_wizard_threshold_modes(self):
        """Test different threshold mode options."""
        for mode in ["auto_quartile", "auto_equal", "manual"]:
            wizard = self.env["spp.gis.report.wizard"].create(
                {
                    "template_id": self.template.id,
                    "name": f"Threshold {mode}",
                    "base_area_level": 2,
                    "threshold_mode": mode,
                }
            )

            result = wizard.action_create_report()
            report = self.env["spp.gis.report"].browse(result["res_id"])

            self.assertEqual(report.threshold_mode, mode)
