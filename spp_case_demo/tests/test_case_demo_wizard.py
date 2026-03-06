# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for spp.case.demo.wizard model."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseDemoWizard(TransactionCase):
    """Tests for the spp.case.demo.wizard transient model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Stage = cls.env["spp.case.stage"]
        stage_data = [
            ("Intake", "intake", 10, False),
            ("Closed", "closure", 60, True),
        ]
        for name, phase, sequence, is_closed in stage_data:
            if not Stage.search([("phase", "=", phase)], limit=1):
                Stage.create({"name": name, "phase": phase, "sequence": sequence, "is_closed": is_closed})

        CaseType = cls.env["spp.case.type"]
        if not CaseType.search([("name", "=", "General Support")], limit=1):
            CaseType.create({"name": "General Support", "code": "GNWZ"})

        # partner_id is required on spp.case; always provide a registrant
        cls.beneficiary = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Wizard Test Beneficiary", "is_registrant": True})
        )

    def _make_wizard(self, **kwargs):
        defaults = {
            "name": "Wizard Test",
            "number_of_cases": 2,
            "include_stories": False,
            "cases_days_back": 30,
            "link_to_beneficiaries": True,
            "percentage_with_plans": 0.0,
            "percentage_with_visits": 0.0,
            "percentage_with_notes": 0.0,
            "percentage_closed": 0.0,
        }
        defaults.update(kwargs)
        return self.env["spp.case.demo.wizard"].create(defaults)

    def test_wizard_inherits_generator(self):
        """spp.case.demo.wizard should inherit spp.case.demo.generator."""
        wizard = self._make_wizard()
        # Verify the wizard can access all generator fields
        self.assertEqual(wizard.number_of_cases, 2)
        self.assertFalse(wizard.include_stories)

    def test_wizard_generate_cases_returns_action(self):
        """generate_cases called from wizard should return a valid window action."""
        wizard = self._make_wizard(number_of_cases=2)
        result = wizard.generate_cases()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.case")

    def test_wizard_create_and_read(self):
        """Wizard records should be creatable and readable."""
        wizard = self._make_wizard()
        self.assertTrue(wizard.id)
        self.assertEqual(wizard.name, "Wizard Test")

    def test_wizard_model_name(self):
        """The wizard model name should be spp.case.demo.wizard."""
        wizard = self._make_wizard()
        self.assertEqual(wizard._name, "spp.case.demo.wizard")

    def test_wizard_description(self):
        """The wizard model description should be set."""
        wizard = self._make_wizard()
        self.assertTrue(wizard._description)

    def test_wizard_shares_generator_methods(self):
        """Wizard should have access to all generator methods via inheritance."""
        wizard = self._make_wizard()
        # Check that inherited helper methods are accessible
        self.assertTrue(hasattr(wizard, "generate_cases"))
        self.assertTrue(hasattr(wizard, "_get_available_beneficiaries"))
        self.assertTrue(hasattr(wizard, "_get_or_create_case_type"))
        self.assertTrue(hasattr(wizard, "_get_random_case_type"))
        self.assertTrue(hasattr(wizard, "_get_random_stage"))
        self.assertTrue(hasattr(wizard, "_determine_stage_from_journey"))
        self.assertTrue(hasattr(wizard, "_find_or_create_client"))
        self.assertTrue(hasattr(wizard, "_get_or_create_service"))
        self.assertTrue(hasattr(wizard, "_create_random_case"))
        self.assertTrue(hasattr(wizard, "_add_random_plan"))
        self.assertTrue(hasattr(wizard, "_add_random_visits"))
        self.assertTrue(hasattr(wizard, "_add_random_notes"))
        self.assertTrue(hasattr(wizard, "_close_random_case"))
        self.assertTrue(hasattr(wizard, "_generate_demo_stories"))
        self.assertTrue(hasattr(wizard, "_create_case_from_story"))
        self.assertTrue(hasattr(wizard, "_process_case_journey"))

    def test_wizard_generates_cases_with_stories(self):
        """Wizard can generate cases including demo stories."""
        wizard = self._make_wizard(
            number_of_cases=2,
            include_stories=True,
        )
        result = wizard.generate_cases()
        self.assertEqual(result["type"], "ir.actions.act_window")
        case_ids = result["domain"][0][2]
        self.assertTrue(len(case_ids) >= 1)

    def test_wizard_percentage_fields_accessible(self):
        """All percentage distribution fields should be accessible on the wizard."""
        wizard = self._make_wizard(
            percentage_with_plans=50.0,
            percentage_with_visits=60.0,
            percentage_with_notes=70.0,
            percentage_closed=30.0,
        )
        self.assertAlmostEqual(wizard.percentage_with_plans, 50.0)
        self.assertAlmostEqual(wizard.percentage_with_visits, 60.0)
        self.assertAlmostEqual(wizard.percentage_with_notes, 70.0)
        self.assertAlmostEqual(wizard.percentage_closed, 30.0)
