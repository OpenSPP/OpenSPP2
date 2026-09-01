# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import uuid

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_programs.models import constants


@tagged("post_install", "-at_install")
class TestProgramCreationWizard(TransactionCase):
    """A user builds a child-benefit programme entirely through the standard
    program-creation wizard and the standard manager-setup dialog — no direct
    program construction — and the result is runnable to payment."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency = cls.env.company.currency_id

    def _make_program_via_wizard(self):
        wizard = self.env["spp.program.create.wizard"].create(
            {
                "name": f"Wizard Child Benefit {uuid.uuid4().hex[:6]}",
                "currency_id": self.currency.id,
                "target_type": "individual",
                "rrule_type": "monthly",
                "entitlement_type": "schedule",
                "schedule_monthly_amount": 10000.0,
                "schedule_age_limit_months": 36,
                "schedule_cutoff_day": 15,
                "eligibility_cel_expression": "r.birth_order >= 3 && age_years(r.birthdate) < 3",
            }
        )
        result = wizard.create_program()
        program_id = (result.get("params") or {}).get("program_id")
        return self.env["spp.program"].browse(program_id)

    def test_wizard_creates_schedule_program(self):
        program = self._make_program_via_wizard()
        self.assertTrue(program)
        # Journal came from the wizard's standard create_journal.
        self.assertTrue(program.journal_id)
        self.assertTrue(program.journal_id.currency_id)
        # Scheduled Cash entitlement manager is configured with our inputs.
        ent = program.get_manager(constants.MANAGER_ENTITLEMENT)
        self.assertEqual(ent._name, "spp.program.entitlement.manager.schedule")
        self.assertEqual(ent.monthly_amount, 10000.0)
        self.assertEqual(ent.age_limit_months, 36)
        self.assertEqual(ent.cutoff_day, 15)
        # CEL eligibility rule is set from the wizard.
        elig = program.eligibility_manager_ids.mapped("manager_ref_id")
        self.assertTrue(elig and "birth_order" in (elig[0].cel_expression or ""))

    def test_payment_method_added_via_manager_setup(self):
        program = self._make_program_via_wizard()
        self.assertFalse(program.payment_manager_ids)
        # Add the Bank File (CSV) payment method the standard way.
        setup = self.env["spp.manager.setup.wizard"].create(
            {
                "program_id": program.id,
                "category": "payment",
                "method": "spp.program.payment.manager.csv",
                "name": "Bank File (CSV)",
            }
        )
        setup.action_create_manager()
        pay = program.get_manager(constants.MANAGER_PAYMENT)
        self.assertEqual(pay._name, "spp.program.payment.manager.csv")

    def test_schedule_method_offered_by_manager_setup(self):
        # Both custom methods must be selectable through the standard dialog.
        setup = self.env["spp.manager.setup.wizard"]
        ent_methods = dict(setup._methods_for_category("entitlement"))
        pay_methods = dict(setup._methods_for_category("payment"))
        self.assertIn("spp.program.entitlement.manager.schedule", ent_methods)
        self.assertIn("spp.program.payment.manager.csv", pay_methods)
