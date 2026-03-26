# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import uuid
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase


class TestBatchEntitlementCreation(TransactionCase):
    """Test that cash entitlement manager creates entitlements in a single
    batch call instead of one-by-one."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.journal = self.env["account.journal"].create(
            {
                "name": "Test Journal",
                "type": "bank",
                "code": f"TJ{uuid.uuid4().hex[:4].upper()}",
            }
        )
        self.program.journal_id = self.journal.id

        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.manager = self.env["spp.program.entitlement.manager.cash"].create(
            {
                "name": "Test Cash Manager",
                "program_id": self.program.id,
            }
        )
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.manager.id,
                "amount": 100.0,
            }
        )

        # Create beneficiaries with cycle memberships
        self.registrants = self.env["res.partner"]
        self.memberships = self.env["spp.cycle.membership"]
        for i in range(5):
            reg = self.env["res.partner"].create({"name": f"Registrant {i}", "is_registrant": True})
            self.registrants |= reg
            self.memberships |= self.env["spp.cycle.membership"].create(
                {
                    "partner_id": reg.id,
                    "cycle_id": self.cycle.id,
                    "state": "enrolled",
                }
            )

    def test_cash_manager_batch_creates_entitlements(self):
        """Cash entitlement manager must create entitlements for all beneficiaries
        using a single batch vals_list passed to create()."""
        self.manager.prepare_entitlements(self.cycle, self.memberships)

        entitlements = self.env["spp.entitlement"].search(
            [("cycle_id", "=", self.cycle.id)]
        )
        self.assertEqual(
            len(entitlements),
            5,
            f"Expected 5 entitlements, got {len(entitlements)}",
        )
        # Verify each registrant got an entitlement
        entitled_partners = entitlements.mapped("partner_id")
        for reg in self.registrants:
            self.assertIn(reg, entitled_partners)


class TestBatchPaymentCreation(TransactionCase):
    """Test that payment manager creates payments in a single batch call
    instead of one-by-one."""

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.journal = self.env["account.journal"].create(
            {
                "name": "Test Journal",
                "type": "bank",
                "code": f"TJ{uuid.uuid4().hex[:4].upper()}",
            }
        )
        self.program.journal_id = self.journal.id

        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.payment_manager = self.env["spp.program.payment.manager.default"].create(
            {
                "name": "Test Payment Manager",
                "program_id": self.program.id,
                "create_batch": False,
            }
        )

        # Create approved entitlements
        self.entitlements = self.env["spp.entitlement"]
        for i in range(5):
            reg = self.env["res.partner"].create({"name": f"Registrant {i}", "is_registrant": True})
            self.entitlements |= self.env["spp.entitlement"].create(
                {
                    "partner_id": reg.id,
                    "cycle_id": self.cycle.id,
                    "initial_amount": 100.0,
                    "state": "approved",
                    "is_cash_entitlement": True,
                }
            )

    def test_payment_manager_batch_creates_payments(self):
        """Payment manager must call create() at most once per batch tag
        (batch), not once per entitlement."""
        original_create = type(self.env["spp.payment"]).create

        call_count = 0

        def counting_create(self_model, vals_list):
            nonlocal call_count
            call_count += 1
            return original_create(self_model, vals_list)

        # Add a batch tag so we enter the loop
        batch_tag = self.env["spp.payment.batch.tag"].create(
            {
                "name": "Test Tag",
                "order": 1,
                "domain": "[]",
                "max_batch_size": 500,
            }
        )
        self.payment_manager.batch_tag_ids = [(4, batch_tag.id)]

        with patch.object(
            type(self.env["spp.payment"]),
            "create",
            counting_create,
        ):
            self.payment_manager._prepare_payments(self.cycle, self.entitlements)

        self.assertEqual(
            call_count,
            1,
            f"create() should be called once (batch), was called {call_count} times",
        )
