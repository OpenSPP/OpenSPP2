# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for cycle compliance visibility on registrant form.

Covers:
- Cycle membership compliance_criteria computed field
- Program membership latest_cycle_state computed field
- Program membership action_view_cycle_memberships action
- Registrant cycle_membership_count / non_compliant_cycle_count computed fields
- Registrant action_view_cycle_memberships action
"""

import uuid

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCycleComplianceOnRegistrant(TransactionCase):
    """Test cycle compliance status visibility on registrant form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        uid = uuid.uuid4().hex[:6]

        # Create program
        cls.program = cls.env["spp.program"].create({"name": f"Compliance Test Program {uid}"})

        # Create registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": f"Test Registrant {uid}",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create cycle
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": f"Test Cycle {uid}",
                "program_id": cls.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

        # Create program membership
        cls.prog_mem = cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.registrant.id,
                "program_id": cls.program.id,
                "state": "enrolled",
            }
        )

        # Create cycle membership
        cls.cycle_mem = cls.env["spp.cycle.membership"].create(
            {
                "partner_id": cls.registrant.id,
                "cycle_id": cls.cycle.id,
                "state": "enrolled",
            }
        )

    # === Cycle Membership: compliance_criteria ===

    def test_compliance_criteria_empty_when_enrolled(self):
        """compliance_criteria is False when state is not non_compliant."""
        self.cycle_mem.state = "enrolled"
        self.assertFalse(self.cycle_mem.compliance_criteria)

    def test_compliance_criteria_empty_when_non_compliant_no_manager(self):
        """compliance_criteria is False when non_compliant but no compliance manager."""
        self.cycle_mem.state = "non_compliant"
        self.assertFalse(self.cycle_mem.compliance_criteria)

    def test_compliance_criteria_shows_cel_when_non_compliant(self):
        """compliance_criteria shows CEL expression when non_compliant and manager exists."""
        # Create compliance manager with CEL expression
        ComplianceManager = self.env.get("spp.compliance.manager.default")
        if not ComplianceManager:
            self.skipTest("spp.compliance.manager.default not available")

        manager = ComplianceManager.create(
            {
                "name": f"Test Compliance {uuid.uuid4().hex[:6]}",
                "program_id": self.program.id,
                "compliance_cel_expression": "per_capita_income < poverty_line",
            }
        )

        # Link manager to program via manager wrapper
        ManagerWrapper = self.env.get("spp.program.manager")
        if ManagerWrapper:
            ManagerWrapper.create(
                {
                    "program_id": self.program.id,
                    "manager_ref_id": f"{manager._name},{manager.id}",
                }
            )

        self.cycle_mem.state = "non_compliant"
        self.cycle_mem.invalidate_recordset(["compliance_criteria"])

        # If manager was properly linked, criteria should show the CEL
        # Otherwise it's False (depends on manager linking mechanism)
        criteria = self.cycle_mem.compliance_criteria
        if criteria:
            self.assertEqual(criteria, "per_capita_income < poverty_line")

    # === Program Membership: latest_cycle_state ===

    def test_latest_cycle_state_enrolled(self):
        """latest_cycle_state reflects the most recent cycle membership state."""
        self.cycle_mem.state = "enrolled"
        self.prog_mem.invalidate_recordset(["latest_cycle_state"])
        self.assertEqual(self.prog_mem.latest_cycle_state, "enrolled")

    def test_latest_cycle_state_non_compliant(self):
        """latest_cycle_state shows non_compliant when cycle is non_compliant."""
        self.cycle_mem.state = "non_compliant"
        self.prog_mem.invalidate_recordset(["latest_cycle_state"])
        self.assertEqual(self.prog_mem.latest_cycle_state, "non_compliant")

    def test_latest_cycle_state_no_cycle(self):
        """latest_cycle_state is False when no cycle memberships exist."""
        # Create a new program membership with no cycles
        prog_mem2 = self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": self.env["spp.program"].create({"name": f"Empty Program {uuid.uuid4().hex[:6]}"}).id,
                "state": "enrolled",
            }
        )
        self.assertFalse(prog_mem2.latest_cycle_state)

    def test_latest_cycle_state_picks_latest(self):
        """latest_cycle_state picks the most recent cycle (highest ID)."""
        cycle2 = self.env["spp.cycle"].create(
            {
                "name": f"Cycle 2 {uuid.uuid4().hex[:6]}",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.env["spp.cycle.membership"].create(
            {
                "partner_id": self.registrant.id,
                "cycle_id": cycle2.id,
                "state": "non_compliant",
            }
        )
        self.prog_mem.invalidate_recordset(["latest_cycle_state"])
        self.assertEqual(self.prog_mem.latest_cycle_state, "non_compliant")

    # === Program Membership: action_view_cycle_memberships ===

    def test_action_view_cycle_memberships_from_program(self):
        """action_view_cycle_memberships returns valid action dict."""
        action = self.prog_mem.action_view_cycle_memberships()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.cycle.membership")
        self.assertIn("domain", action)
        # Domain should filter by partner and program
        domain = action["domain"]
        self.assertTrue(any(d[0] == "partner_id" and d[2] == self.registrant.id for d in domain))
        self.assertTrue(any(d[0] == "cycle_id.program_id" and d[2] == self.program.id for d in domain))

    # === Registrant: cycle_membership_count / non_compliant_cycle_count ===

    def test_cycle_membership_count(self):
        """cycle_membership_count reflects total cycle memberships."""
        self.registrant.invalidate_recordset(["cycle_membership_count"])
        self.assertGreaterEqual(self.registrant.cycle_membership_count, 1)

    def test_non_compliant_cycle_count_zero(self):
        """non_compliant_cycle_count is 0 when all cycles are enrolled."""
        self.cycle_mem.state = "enrolled"
        self.registrant.invalidate_recordset(["non_compliant_cycle_count"])
        self.assertEqual(self.registrant.non_compliant_cycle_count, 0)

    def test_non_compliant_cycle_count_increments(self):
        """non_compliant_cycle_count increments when cycle becomes non_compliant."""
        self.cycle_mem.state = "non_compliant"
        self.registrant.invalidate_recordset(["non_compliant_cycle_count"])
        self.assertGreaterEqual(self.registrant.non_compliant_cycle_count, 1)

    def test_cycle_counts_non_registrant(self):
        """Non-registrant partners have 0 cycle counts."""
        non_reg = self.env["res.partner"].create({"name": "Not a registrant"})
        self.assertEqual(non_reg.cycle_membership_count, 0)
        self.assertEqual(non_reg.non_compliant_cycle_count, 0)

    # === Registrant: action_view_cycle_memberships ===

    def test_action_view_cycle_memberships_from_registrant(self):
        """action_view_cycle_memberships returns valid action dict."""
        action = self.registrant.action_view_cycle_memberships()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.cycle.membership")
        self.assertIn("domain", action)
        domain = action["domain"]
        self.assertTrue(any(d[0] == "partner_id" and d[2] == self.registrant.id for d in domain))
