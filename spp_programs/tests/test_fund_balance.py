# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import uuid
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase


class TestFundBalanceOptimization(TransactionCase):
    """Test that fund balance is fetched once per approval batch, not per entitlement.

    The approve_entitlements methods previously called check_fund_balance()
    (2 SQL queries) inside the per-entitlement loop. Now the balance is
    fetched once and tracked via a running total in Python.
    """

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        # Create a journal for the program
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

        self.registrants = self.env["res.partner"]
        for i in range(5):
            self.registrants |= self.env["res.partner"].create({"name": f"Registrant {i}", "is_registrant": True})

    def _create_default_manager(self):
        return self.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Test Default Manager",
                "program_id": self.program.id,
                "amount_per_cycle": 100.0,
            }
        )

    def _create_cash_manager(self):
        manager = self.env["spp.program.entitlement.manager.cash"].create(
            {
                "name": "Test Cash Manager",
                "program_id": self.program.id,
            }
        )
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": manager.id,
                "amount": 100.0,
            }
        )
        return manager

    def _create_entitlements(self, count=5, amount=100.0):
        """Create multiple entitlements in pending_validation state."""
        entitlements = self.env["spp.entitlement"]
        for i in range(count):
            entitlements |= self.env["spp.entitlement"].create(
                {
                    "partner_id": self.registrants[i].id,
                    "cycle_id": self.cycle.id,
                    "initial_amount": amount,
                    "state": "pending_validation",
                    "is_cash_entitlement": True,
                }
            )
        return entitlements

    def test_default_manager_calls_check_fund_balance_once(self):
        """DefaultCashEntitlementManager.approve_entitlements must call
        check_fund_balance at most once per batch."""
        manager = self._create_default_manager()
        entitlements = self._create_entitlements(count=3)

        with patch.object(
            type(manager),
            "check_fund_balance",
            wraps=manager.check_fund_balance,
        ) as mock_check:
            # Set fund balance high enough to approve all
            mock_check.return_value = 10000.0
            manager.approve_entitlements(entitlements)
            self.assertEqual(
                mock_check.call_count,
                1,
                f"check_fund_balance should be called exactly once, was called {mock_check.call_count} times",
            )

    def test_cash_manager_calls_check_fund_balance_once(self):
        """SppCashEntitlementManager.approve_entitlements must call
        check_fund_balance at most once per batch."""
        manager = self._create_cash_manager()
        entitlements = self._create_entitlements(count=3)

        with patch.object(
            type(manager),
            "check_fund_balance",
            wraps=manager.check_fund_balance,
        ) as mock_check:
            mock_check.return_value = 10000.0
            manager.approve_entitlements(entitlements)
            self.assertEqual(
                mock_check.call_count,
                1,
                f"check_fund_balance should be called exactly once, was called {mock_check.call_count} times",
            )

    def test_fund_balance_insufficient_stops_early(self):
        """When fund runs out mid-batch, remaining entitlements are not approved."""
        manager = self._create_default_manager()
        entitlements = self._create_entitlements(count=3, amount=100.0)

        with patch.object(
            type(manager),
            "check_fund_balance",
            return_value=250.0,
        ):
            state_err, message = manager.approve_entitlements(entitlements)
            self.assertEqual(state_err, 1)
            self.assertIn("insufficient", message)

    def test_fund_balance_running_total_correct(self):
        """Running total must correctly track cumulative approved amounts."""
        manager = self._create_default_manager()
        entitlements = self._create_entitlements(count=3, amount=100.0)

        with patch.object(
            type(manager),
            "check_fund_balance",
            return_value=300.0,
        ):
            state_err, _message = manager.approve_entitlements(entitlements)
            self.assertEqual(state_err, 0)
            # All 3 should be approved (300 fund, 3x100 = 300)
            for ent in entitlements:
                ent.invalidate_recordset(["state"])
                self.assertEqual(ent.state, "approved")
