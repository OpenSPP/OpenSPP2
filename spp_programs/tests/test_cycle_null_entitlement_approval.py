# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security scan finding: "NULL entitlement states can pass approval check".

``_compute_all_entitlements_approved`` finds unapproved cycles with the SQL
predicate ``state != 'approved'``. In SQL ``NULL != 'approved'`` evaluates to
UNKNOWN (not TRUE), so an entitlement whose ``state`` is NULL is excluded from
``cycles_with_unapproved``. A cycle containing only approved entitlements plus
one NULL-state entitlement therefore computes ``all_entitlements_approved =
True`` — re-introducing the unapproved entitlement into a "fully approved"
cycle. The previous ``all(ent.state == "approved" ...)`` logic treated
NULL/False as "not approved" and was safe.

The entitlement ``state`` field has a default of "draft" but is not required,
so NULL rows are reachable via raw SQL / imports / RPC writes.
"""

import uuid

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCycleNullEntitlementApproval(TransactionCase):
    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.journal = self.env["account.journal"].create(
            {"name": "Test Journal", "type": "bank", "code": f"TJ{uuid.uuid4().hex[:4].upper()}"}
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
        self.partners = self.env["res.partner"].create(
            [{"name": f"Registrant {i}", "is_registrant": True} for i in range(2)]
        )

    def _make_entitlement(self, partner, state):
        return self.env["spp.entitlement"].create(
            {
                "partner_id": partner.id,
                "cycle_id": self.cycle.id,
                "initial_amount": 100.0,
                "state": state,
                "is_cash_entitlement": True,
            }
        )

    def test_null_state_entitlement_is_not_treated_as_approved(self):
        """A cycle with an approved + a NULL-state entitlement is NOT fully approved."""
        approved = self._make_entitlement(self.partners[0], "approved")
        other = self._make_entitlement(self.partners[1], "draft")

        # Force the second entitlement's state to NULL, the way a raw import /
        # RPC write that omits the default could. (ORM create would apply the
        # 'draft' default, so we go through SQL to reproduce the NULL row.)
        self.env.cr.execute("UPDATE spp_entitlement SET state = NULL WHERE id = %s", (other.id,))
        self.cycle.invalidate_recordset(["all_entitlements_approved"])

        # Sanity: there really is a NULL-state entitlement in this cycle.
        self.env.cr.execute(
            "SELECT COUNT(*) FROM spp_entitlement WHERE cycle_id = %s AND state IS NULL",
            (self.cycle.id,),
        )
        self.assertEqual(self.env.cr.fetchone()[0], 1, "precondition: one NULL-state entitlement must exist")
        self.assertEqual(approved.state, "approved")

        self.assertFalse(
            self.cycle.all_entitlements_approved,
            "Cycle has a NULL-state (unapproved) entitlement; all_entitlements_approved must be False",
        )

    def test_all_approved_is_true_when_truly_all_approved(self):
        """Control: when every entitlement is approved, the flag is True."""
        self._make_entitlement(self.partners[0], "approved")
        self._make_entitlement(self.partners[1], "approved")
        self.cycle.invalidate_recordset(["all_entitlements_approved"])
        self.assertTrue(self.cycle.all_entitlements_approved)
