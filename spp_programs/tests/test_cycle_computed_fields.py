# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import uuid

from odoo import fields
from odoo.tests import TransactionCase


class TestCycleComputedFields(TransactionCase):
    """Test that SQL-optimized cycle computed fields return correct results.

    These fields were migrated from Python iteration over recordsets to
    SQL aggregation for O(1) instead of O(N) per cycle.
    """

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.registrant1 = self.env["res.partner"].create({"name": "Registrant 1", "is_registrant": True})
        self.registrant2 = self.env["res.partner"].create({"name": "Registrant 2", "is_registrant": True})
        self.registrant3 = self.env["res.partner"].create({"name": "Registrant 3", "is_registrant": True})

    def _create_entitlement(self, partner, amount, state="draft"):
        ent = self.env["spp.entitlement"].create(
            {
                "partner_id": partner.id,
                "cycle_id": self.cycle.id,
                "initial_amount": amount,
            }
        )
        if state != "draft":
            ent.state = state
        ent.flush_recordset()
        return ent

    # -- total_amount --

    def test_total_amount_empty(self):
        """Cycle with no entitlements has total_amount = 0."""
        self.cycle.invalidate_recordset(["total_amount"])
        self.assertEqual(self.cycle.total_amount, 0)

    def test_total_amount_sums_initial_amounts(self):
        """total_amount must equal sum of all entitlement initial_amounts."""
        self._create_entitlement(self.registrant1, 100.0)
        self._create_entitlement(self.registrant2, 250.50)
        self._create_entitlement(self.registrant3, 49.50)
        self.cycle.invalidate_recordset(["total_amount"])
        self.assertAlmostEqual(self.cycle.total_amount, 400.0)

    # -- total_entitlements_count --

    def test_total_entitlements_count_empty(self):
        """Cycle with no entitlements has count = 0."""
        self.cycle.invalidate_recordset(["total_entitlements_count"])
        self.assertEqual(self.cycle.total_entitlements_count, 0)

    def test_total_entitlements_count_correct(self):
        """Count must include all cash entitlements."""
        self._create_entitlement(self.registrant1, 100.0)
        self._create_entitlement(self.registrant2, 200.0)
        self.cycle.invalidate_recordset(["total_entitlements_count"])
        self.assertEqual(self.cycle.total_entitlements_count, 2)

    # -- show_approve_entitlements_button --

    def test_show_approve_no_entitlements(self):
        """Button hidden when no entitlements exist."""
        self.cycle.invalidate_recordset(["show_approve_entitlements_button"])
        self.assertFalse(self.cycle.show_approve_entitlements_button)

    def test_show_approve_with_pending(self):
        """Button shown when pending_validation entitlements exist."""
        self._create_entitlement(self.registrant1, 100.0, state="pending_validation")
        self.cycle.invalidate_recordset(["show_approve_entitlements_button"])
        self.assertTrue(self.cycle.show_approve_entitlements_button)

    def test_show_approve_only_draft(self):
        """Button hidden when all entitlements are draft."""
        self._create_entitlement(self.registrant1, 100.0, state="draft")
        self.cycle.invalidate_recordset(["show_approve_entitlements_button"])
        self.assertFalse(self.cycle.show_approve_entitlements_button)

    def test_show_approve_only_approved(self):
        """Button hidden when all entitlements are approved."""
        self._create_entitlement(self.registrant1, 100.0, state="approved")
        self.cycle.invalidate_recordset(["show_approve_entitlements_button"])
        self.assertFalse(self.cycle.show_approve_entitlements_button)

    # -- all_entitlements_approved --

    def test_all_approved_empty(self):
        """No entitlements => not all approved (nothing to approve)."""
        self.cycle.invalidate_recordset(["all_entitlements_approved"])
        self.assertFalse(self.cycle.all_entitlements_approved)

    def test_all_approved_when_all_approved(self):
        """True when every entitlement has state=approved."""
        self._create_entitlement(self.registrant1, 100.0, state="approved")
        self._create_entitlement(self.registrant2, 200.0, state="approved")
        self.cycle.invalidate_recordset(["all_entitlements_approved"])
        self.assertTrue(self.cycle.all_entitlements_approved)

    def test_all_approved_mixed_states(self):
        """False when some entitlements are not approved."""
        self._create_entitlement(self.registrant1, 100.0, state="approved")
        self._create_entitlement(self.registrant2, 200.0, state="draft")
        self.cycle.invalidate_recordset(["all_entitlements_approved"])
        self.assertFalse(self.cycle.all_entitlements_approved)

    # -- multi-cycle batching --

    def test_computed_fields_multi_cycle(self):
        """SQL queries must handle multiple cycles in a single batch."""
        cycle2 = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle 2",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self._create_entitlement(self.registrant1, 100.0)
        self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant2.id,
                "cycle_id": cycle2.id,
                "initial_amount": 300.0,
            }
        )

        cycles = self.cycle | cycle2
        cycles.invalidate_recordset(["total_amount", "total_entitlements_count"])

        self.assertAlmostEqual(self.cycle.total_amount, 100.0)
        self.assertAlmostEqual(cycle2.total_amount, 300.0)
        self.assertEqual(self.cycle.total_entitlements_count, 1)
        self.assertEqual(cycle2.total_entitlements_count, 1)
