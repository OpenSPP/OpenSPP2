# Part of OpenSPP. See LICENSE file for full copyright and licensing details.


from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestGISReportProgramsModel(TransactionCase):
    """Test GIS Report extension for program context filtering."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Report = cls.env["spp.gis.report"]
        cls.Program = cls.env["spp.program"]

        cls.program = cls.Program.create(
            {
                "name": "Test Program for GIS",
                "target_type": "group",
            }
        )

        # Get source model for res.partner
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def _make_report_vals(self, **overrides):
        """Build minimal vals dict for a spp.gis.report record."""
        vals = {
            "name": "Test Report",
            "code": "TEST_RPT_001",
            "source_model_id": self.partner_model.id,
            "area_field_path": "area_id",
            "filter_mode": "domain",
            "aggregation_method": "count",
            "base_area_level": 2,
            "normalization_method": "raw",
            "threshold_mode": "auto_quartile",
            "refresh_mode": "manual",
            "geometry_type": "polygon",
        }
        vals.update(overrides)
        return vals

    def test_program_id_field_exists(self):
        """Test that program_id field is added to spp.gis.report."""
        field_info = self.Report.fields_get(["program_id"])
        self.assertIn("program_id", field_info)
        self.assertEqual(field_info["program_id"]["relation"], "spp.program")

    def test_report_create_with_program(self):
        """Test creating a report with program_id set."""
        report = self.Report.create(self._make_report_vals(program_id=self.program.id))
        self.assertEqual(report.program_id, self.program)

    def test_report_create_without_program(self):
        """Test creating a report without program_id."""
        report = self.Report.create(self._make_report_vals())
        self.assertFalse(report.program_id)

    def test_apply_context_filters_with_program(self):
        """Test _apply_context_filters adds program enrollment domain."""
        report = self.Report.new(
            {
                "program_id": self.program.id,
                "source_model": "res.partner",
            }
        )
        domain = [("is_registrant", "=", True)]
        result = report._apply_context_filters(domain)

        # Should contain the original domain + program membership filter
        flat = str(result)
        self.assertIn("program_membership_ids.program_id", flat)

    def test_apply_context_filters_without_program(self):
        """Test _apply_context_filters is a no-op without program_id."""
        report = self.Report.new(
            {
                "source_model": "res.partner",
            }
        )
        domain = [("is_registrant", "=", True)]
        result = report._apply_context_filters(domain)
        self.assertEqual(result, domain)

    def test_apply_context_filters_non_partner_model(self):
        """Test _apply_context_filters skips filter for non-partner models."""
        report = self.Report.new(
            {
                "program_id": self.program.id,
                "source_model": "spp.area",
            }
        )
        domain = [("active", "=", True)]
        result = report._apply_context_filters(domain)
        # Should NOT add program filter since source_model is not res.partner
        self.assertEqual(result, domain)


@tagged("post_install", "-at_install")
class TestGISReportWizardPrograms(TransactionCase):
    """Test GIS Report Wizard extension for program context."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["spp.gis.report.wizard"]
        cls.Program = cls.env["spp.program"]

        cls.program = cls.Program.create(
            {
                "name": "Wizard Test Program",
                "target_type": "group",
            }
        )

    def test_wizard_program_id_field(self):
        """Test that program_id field exists on the wizard."""
        field_info = self.Wizard.fields_get(["program_id"])
        self.assertIn("program_id", field_info)
        self.assertEqual(field_info["program_id"]["relation"], "spp.program")

    def test_validate_context_requirements_program_required(self):
        """Test validation when template requires program but none set."""
        wizard = self.Wizard.new(
            {
                "template_requires_program": True,
                "program_id": False,
            }
        )
        with self.assertRaises(ValidationError):
            wizard._validate_context_requirements()

    def test_validate_context_requirements_program_provided(self):
        """Test validation passes when required program is provided."""
        wizard = self.Wizard.new(
            {
                "template_requires_program": True,
                "program_id": self.program.id,
            }
        )
        # Should not raise
        wizard._validate_context_requirements()

    def test_validate_context_requirements_not_required(self):
        """Test validation passes when program is not required."""
        wizard = self.Wizard.new(
            {
                "template_requires_program": False,
                "program_id": False,
            }
        )
        # Should not raise
        wizard._validate_context_requirements()

    def test_get_context_filter_vals_with_program(self):
        """Test _get_context_filter_vals includes program_id."""
        wizard = self.Wizard.new(
            {
                "program_id": self.program.id,
            }
        )
        vals = wizard._get_context_filter_vals()
        self.assertEqual(vals.get("program_id"), self.program.id)

    def test_get_context_filter_vals_without_program(self):
        """Test _get_context_filter_vals without program."""
        wizard = self.Wizard.new(
            {
                "program_id": False,
            }
        )
        vals = wizard._get_context_filter_vals()
        self.assertNotIn("program_id", vals)

    def test_get_context_code_suffix_with_program(self):
        """Test _get_context_code_suffix includes program ID."""
        wizard = self.Wizard.new(
            {
                "program_id": self.program.id,
            }
        )
        suffix = wizard._get_context_code_suffix()
        self.assertIn(str(self.program.id), suffix)

    def test_get_context_code_suffix_without_program(self):
        """Test _get_context_code_suffix returns empty without program."""
        wizard = self.Wizard.new(
            {
                "program_id": False,
            }
        )
        suffix = wizard._get_context_code_suffix()
        self.assertEqual(suffix, "")
