# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import base64
import uuid
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProgramFlow(TransactionCase):
    """End-to-end: enrollment -> schedule -> cycle entitlements -> payments -> bank CSV."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Vocab = env["spp.vocabulary.code"]
        cls.type_family = Vocab.get_code("urn:openspp:vocab:group-type", "family")
        cls.role_head = Vocab.get_code("urn:openspp:vocab:group-membership-type", "head")
        cls.role_child = env.ref("spp_child_benefit.code_membership_type_child")
        cls.role_mother = env.ref("spp_child_benefit.code_membership_type_mother")

        # Family: mother (payee, has a bank account) and one eligible child
        # born on the 3rd two months ago -> current month is a full month.
        today = fields.Date.today()
        cls.birthdate = date(today.year, today.month, 3) - relativedelta(months=2)
        cls.mother = env["res.partner"].create(
            {"name": "Flow Mother", "is_registrant": True, "is_group": False, "birthdate": date(1994, 1, 20)}
        )
        cls.child = env["res.partner"].create(
            {"name": "Flow Child", "is_registrant": True, "is_group": False, "birthdate": cls.birthdate}
        )
        cls.bank = env["res.bank"].create({"name": "Demo National Bank"})
        env["res.partner.bank"].create(
            {"partner_id": cls.mother.id, "acc_number": "000123456789", "bank_id": cls.bank.id}
        )
        cls.family = env["res.partner"].create(
            {
                "name": "Flow Family",
                "is_registrant": True,
                "is_group": True,
                "group_type_id": cls.type_family.id,
            }
        )
        env["spp.group.membership"].create(
            {
                "group": cls.family.id,
                "individual": cls.mother.id,
                "membership_type_ids": [Command.set([cls.role_head.id, cls.role_mother.id])],
            }
        )
        env["spp.group.membership"].create(
            {
                "group": cls.family.id,
                "individual": cls.child.id,
                "membership_type_ids": [Command.set([cls.role_child.id])],
            }
        )

        # Program with scheduled entitlement + CSV payment managers
        cls.program = env["spp.program"].create(
            {"name": f"Flow Program {uuid.uuid4().hex[:8]}", "target_type": "individual"}
        )
        cls.journal = env["account.journal"].create(
            {"name": "Flow Journal", "type": "bank", "code": f"FJ{uuid.uuid4().hex[:4].upper()}"}
        )
        cls.program.journal_id = cls.journal.id

        cls.ent_manager = env["spp.program.entitlement.manager.schedule"].create(
            {
                "name": "Scheduled Cash Entitlement",
                "program_id": cls.program.id,
                "monthly_amount": 10000.0,
                "age_limit_months": 36,
                "cutoff_day": 15,
            }
        )
        ent_container = env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"spp.program.entitlement.manager.schedule,{cls.ent_manager.id}",
            }
        )
        cls.program.entitlement_manager_ids = [Command.link(ent_container.id)]
        cls.pay_manager = env["spp.program.payment.manager.csv"].create(
            {
                "name": "Bank File (CSV)",
                "program_id": cls.program.id,
                "create_batch": True,
            }
        )
        pay_container = env["spp.program.payment.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"spp.program.payment.manager.csv,{cls.pay_manager.id}",
            }
        )
        cls.program.payment_manager_ids = [Command.link(pay_container.id)]

        # Current-month cycle
        month_start = date(today.year, today.month, 1)
        month_end = month_start + relativedelta(months=1, days=-1)
        cls.cycle = env["spp.cycle"].create(
            {
                "name": "Flow Cycle",
                "program_id": cls.program.id,
                "start_date": month_start,
                "end_date": month_end,
            }
        )

    def _enroll(self):
        membership = self.env["spp.program.membership"].create(
            {"partner_id": self.child.id, "program_id": self.program.id, "state": "enrolled"}
        )
        cycle_membership = self.env["spp.cycle.membership"].create(
            {"partner_id": self.child.id, "cycle_id": self.cycle.id, "state": "enrolled"}
        )
        return membership, cycle_membership

    def test_enrollment_generates_schedule(self):
        self._enroll()
        schedule = self.env["spp.entitlement.schedule"].search(
            [("partner_id", "=", self.child.id), ("program_id", "=", self.program.id)]
        )
        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule.state, "active")
        self.assertEqual(schedule.line_count, 37)
        self.assertEqual(schedule.date_of_birth, self.birthdate)

    def test_cycle_materializes_schedule_lines(self):
        _, cycle_membership = self._enroll()
        self.ent_manager.prepare_entitlements(self.cycle, cycle_membership)
        entitlements = self.env["spp.entitlement"].search([("cycle_id", "=", self.cycle.id)])
        self.assertEqual(len(entitlements), 1)
        self.assertEqual(entitlements.initial_amount, 10000.0)
        line = self.env["spp.entitlement.schedule.line"].search([("entitlement_id", "=", entitlements.id)])
        self.assertEqual(line.benefit_month, self.cycle.start_date)
        # Idempotent: preparing again creates nothing new
        self.ent_manager.prepare_entitlements(self.cycle, cycle_membership)
        self.assertEqual(
            self.env["spp.entitlement"].search_count([("cycle_id", "=", self.cycle.id)]),
            1,
        )

    def test_payments_and_bank_csv(self):
        _, cycle_membership = self._enroll()
        self.ent_manager.prepare_entitlements(self.cycle, cycle_membership)
        entitlements = self.env["spp.entitlement"].search([("cycle_id", "=", self.cycle.id)])
        entitlements.write({"state": "approved"})

        payments, batches = self.pay_manager._prepare_payments(self.cycle, entitlements)
        self.assertEqual(len(payments), 1)
        payment = payments[0]
        # Sequenced reference, payee account resolved from the mother
        self.assertTrue(payment.name.startswith("CBP-"))
        self.assertEqual(payment.account_number, "000123456789")
        self.assertTrue(batches)

        self.pay_manager._send_payments(batches)
        self.assertEqual(payment.state, "sent")
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", "spp.payment.batch"), ("res_id", "=", batches[0].id)]
        )
        self.assertEqual(len(attachment), 1)
        content = base64.b64decode(attachment.datas).decode("utf-8")
        self.assertIn("Flow Child", content)
        self.assertIn("Flow Mother", content)
        self.assertIn("Demo National Bank", content)
        self.assertIn("10000.00", content)
        self.assertIn("total_transactions", content)
