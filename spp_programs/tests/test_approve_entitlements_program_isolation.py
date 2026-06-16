# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security scan finding: "Fund balance cached from first entitlement program".

``approve_entitlements`` fetches the fund balance once with
``check_fund_balance(entitlements[0].cycle_id.program_id.id)`` and reuses it
for every record in the batch. Two consequences:

1. If a mixed-program recordset is passed, entitlements belonging to a later
   program are approved against the *first* program's balance instead of their
   own — bypassing the later program's fund limit.
2. ``entitlements[0]`` raises ``IndexError`` on an empty recordset instead of
   returning cleanly.

The previous implementation called ``check_fund_balance(rec.cycle_id.program_id.id)``
inside the loop, so each entitlement was evaluated against its own program.
"""

import uuid
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApproveEntitlementsProgramIsolation(TransactionCase):
    def _make_program_with_cycle(self):
        program = self.env["spp.program"].create({"name": f"Program {uuid.uuid4().hex[:8]}"})
        journal = self.env["account.journal"].create(
            {"name": "J", "type": "bank", "code": f"J{uuid.uuid4().hex[:4].upper()}"}
        )
        program.journal_id = journal.id
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Cycle",
                "program_id": program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        manager = self.env["spp.program.entitlement.manager.default"].create(
            {"name": "Mgr", "program_id": program.id, "amount_per_cycle": 100.0}
        )
        return program, cycle, manager

    def _make_entitlement(self, cycle, partner):
        return self.env["spp.entitlement"].create(
            {
                "partner_id": partner.id,
                "cycle_id": cycle.id,
                "initial_amount": 100.0,
                "state": "pending_validation",
                "is_cash_entitlement": True,
            }
        )

    def test_empty_recordset_does_not_crash(self):
        """approve_entitlements on an empty recordset must not raise IndexError."""
        _program, _cycle, manager = self._make_program_with_cycle()
        empty = self.env["spp.entitlement"]
        # On the buggy code entitlements[0] raises IndexError before the loop.
        manager.approve_entitlements(empty)

    def test_each_entitlement_checked_against_its_own_program(self):
        """A mixed-program batch must evaluate each entitlement's own program fund.

        We record every program_id passed to check_fund_balance. With the
        single-fetch bug only the first program is ever queried, so the second
        program's id is missing from the recorded set.
        """
        _p1, cycle1, manager = self._make_program_with_cycle()
        p2, cycle2, _manager2 = self._make_program_with_cycle()
        partner_a = self.env["res.partner"].create({"name": "A", "is_registrant": True})
        partner_b = self.env["res.partner"].create({"name": "B", "is_registrant": True})

        ent1 = self._make_entitlement(cycle1, partner_a)
        ent2 = self._make_entitlement(cycle2, partner_b)
        mixed = ent1 | ent2

        checked_program_ids = []

        def _record(self_mgr, program_id):
            checked_program_ids.append(program_id)
            return 10000.0  # plenty of funds so the loop runs to completion

        with patch.object(type(manager), "check_fund_balance", _record):
            manager.approve_entitlements(mixed)

        self.assertIn(
            p2.id,
            checked_program_ids,
            "second program's fund balance was never checked — its entitlement was "
            "approved against the first program's funds",
        )
