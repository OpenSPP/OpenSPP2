import logging
from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import Common

_logger = logging.getLogger(__name__)


class TestCycle(Common):
    def test_check_dates_constrains(self):
        with self.assertRaisesRegex(ValidationError, 'The "End Date" cannot be earlier than the "Start Date".'):
            self.cycle.write(
                {
                    "end_date": "2024-07-18",
                }
            )

        with self.assertRaisesRegex(ValidationError, 'The "Start Date" cannot be earlier than today.'):
            self.cycle.write(
                {
                    "start_date": "2024-07-18",
                }
            )

    def test_get_previous_and_next_cycle(self):
        # The `cycle` from `Common` is created first.
        # To test previous/next, we need to control creation order.
        # Cycles are sorted by `create_date`.

        # Create a new program for this test to avoid interference from other tests
        self.program = self.env["spp.program"].create(
            {
                "name": "Test Program for Cycle Navigation",
            }
        )

        # This will be the first cycle chronologically by create_date
        first_cycle = self.env["spp.cycle"].create(
            {
                "name": "First Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

        # This is the middle cycle, created after first_cycle
        middle_cycle = self.env["spp.cycle"].create(
            {
                "name": "Middle Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

        # The `self.cycle` from `setUp` is now the last one created.
        # Let's rename it for clarity in this test.
        last_cycle = self.env["spp.cycle"].create(
            {
                "name": "Last Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

        self.assertIsNone(
            first_cycle.get_previous_cycle(),
            "First cycle should have no previous cycle.",
        )
        self.assertEqual(
            first_cycle.get_next_cycle(),
            middle_cycle,
            "Next cycle for first_cycle should be middle_cycle.",
        )
        self.assertEqual(
            middle_cycle.get_previous_cycle(),
            first_cycle,
            "Previous cycle for middle_cycle should be first_cycle.",
        )
        self.assertEqual(
            middle_cycle.get_next_cycle(),
            last_cycle,
            "Next cycle for middle_cycle should be last_cycle.",
        )
        self.assertEqual(
            last_cycle.get_previous_cycle(),
            middle_cycle,
            "Previous cycle for last_cycle should be middle_cycle.",
        )
        self.assertIsNone(last_cycle.get_next_cycle(), "Last cycle should have no next cycle.")


@tagged("post_install", "-at_install")
class TestCycleWorkflow(TransactionCase):
    """Tests for spp.cycle state transitions, computed fields, and workflow methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        # Create test company and currency
        cls.company = cls.env.company
        cls.currency = cls.env.ref("base.USD")

        # Create a bank journal for the program
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Disbursement Journal [CYCLE TEST]",
                "code": "TCYJ",
                "type": "bank",
                "currency_id": cls.currency.id,
                "company_id": cls.company.id,
                "is_beneficiary_disb": True,
            }
        )

        # Create the program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program [CYCLE TEST]",
                "journal_id": cls.journal.id,
            }
        )

        # Create entitlement manager (two-record pattern)
        # Create approval definition for entitlements
        entitlement_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement")], limit=1)
        cls.entitlement_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Entitlement Approval [CYCLE TEST]",
                "model_id": entitlement_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

        cls.entitlement_manager_default = cls.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Test Entitlement Manager [CYCLE TEST]",
                "program_id": cls.program.id,
                "amount_per_cycle": 100.0,
                "amount_per_individual_in_group": 0.0,
                "approval_definition_id": cls.entitlement_approval_definition.id,
            }
        )
        cls.entitlement_manager = cls.env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.program.entitlement.manager.default,{cls.entitlement_manager_default.id}"),
            }
        )

        # Create approval definition for cycles
        cycle_model = cls.env["ir.model"].search([("model", "=", "spp.cycle")], limit=1)
        cls.cycle_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Cycle Approval Definition [CYCLE TEST]",
                "model_id": cycle_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

        # Create cycle manager (two-record pattern)
        cls.cycle_manager_default = cls.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager [CYCLE TEST]",
                "program_id": cls.program.id,
                "auto_approve_entitlements": False,
                "approval_definition_id": cls.cycle_approval_definition.id,
            }
        )
        cls.cycle_manager = cls.env["spp.cycle.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"spp.cycle.manager.default,{cls.cycle_manager_default.id}",
            }
        )

        # Link managers to the program
        cls.program.write(
            {
                "cycle_manager_ids": [(4, cls.cycle_manager.id)],
                "entitlement_manager_ids": [(4, cls.entitlement_manager.id)],
            }
        )

        # Create test beneficiaries (groups/households)
        cls.beneficiary1 = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary 1 [CYCLE TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.beneficiary2 = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary 2 [CYCLE TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Enroll beneficiaries in the program
        cls.env["spp.program.membership"].create(
            [
                {
                    "partner_id": cls.beneficiary1.id,
                    "program_id": cls.program.id,
                    "state": "enrolled",
                },
                {
                    "partner_id": cls.beneficiary2.id,
                    "program_id": cls.program.id,
                    "state": "enrolled",
                },
            ]
        )

    def _make_cycle(self, name="Test Cycle [CYCLE TEST]", state="draft"):
        """Helper: create a fresh cycle attached to cls.program."""
        today = fields.Date.today()
        cycle = self.env["spp.cycle"].create(
            {
                "name": name,
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": state,
            }
        )
        return cycle

    def _add_members(self, cycle):
        """Helper: add the two class-level beneficiaries as enrolled cycle members."""
        self.env["spp.cycle.membership"].create(
            [
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary1.id,
                    "state": "enrolled",
                },
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary2.id,
                    "state": "enrolled",
                },
            ]
        )

    # ------------------------------------------------------------------
    # Unique-name constraint
    # ------------------------------------------------------------------

    def test_unique_name_per_program_constraint(self):
        """Two cycles with the same name under the same program must be rejected."""
        self._make_cycle(name="Unique Name Cycle [CYCLE TEST]")
        with self.assertRaisesRegex(
            ValidationError,
            "Cycle with this name already exists",
        ):
            self._make_cycle(name="Unique Name Cycle [CYCLE TEST]")

    def test_unique_name_allowed_across_programs(self):
        """The same cycle name is allowed under different programs."""
        program2 = self.env["spp.program"].create({"name": "Program B [CYCLE TEST]"})
        self._make_cycle(name="Shared Name Cycle [CYCLE TEST]")
        # Should not raise
        cycle2 = self.env["spp.cycle"].create(
            {
                "name": "Shared Name Cycle [CYCLE TEST]",
                "program_id": program2.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.assertTrue(cycle2.id)

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    def test_members_count_enrolled_only(self):
        """_compute_members_count counts only 'enrolled' cycle memberships."""
        cycle = self._make_cycle(name="Members Count Cycle [CYCLE TEST]")
        self.assertEqual(cycle.members_count, 0, "No members yet.")

        self._add_members(cycle)
        cycle._compute_members_count()
        self.assertEqual(cycle.members_count, 2, "Two enrolled members expected.")

        # A non-enrolled member should not be counted
        self.env["spp.cycle.membership"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.env["res.partner"]
                .create({"name": "Non-enrolled [CYCLE TEST]", "is_registrant": True})
                .id,
                "state": "paused",
            }
        )
        cycle._compute_members_count()
        self.assertEqual(
            cycle.members_count,
            2,
            "Paused member should not be included in enrolled count.",
        )

    def test_all_members_count(self):
        """_compute_all_members_count counts all cycle memberships regardless of state."""
        cycle = self._make_cycle(name="All Members Count Cycle [CYCLE TEST]")
        self._add_members(cycle)
        # Add a paused member
        self.env["spp.cycle.membership"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.env["res.partner"]
                .create({"name": "Paused Member [CYCLE TEST]", "is_registrant": True})
                .id,
                "state": "paused",
            }
        )
        cycle._compute_all_members_count()
        self.assertEqual(cycle.all_members_count, 3, "All three members (regardless of state) should be counted.")

    @patch("odoo.fields.Date.today")
    def test_entitlements_count(self, mock_today):
        """_compute_entitlements_count reflects cash entitlements on the cycle."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Entitlements Count Cycle [CYCLE TEST]")
        self.assertEqual(cycle.entitlements_count, 0)

        self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "initial_amount": 100.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
            }
        )
        cycle._compute_entitlements_count()
        self.assertEqual(cycle.entitlements_count, 1)

    @patch("odoo.fields.Date.today")
    def test_total_entitlements_count_includes_inkind(self, mock_today):
        """_compute_total_entitlements_count sums both cash and in-kind entitlements."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Total Entitlements Count Cycle [CYCLE TEST]")

        self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "initial_amount": 100.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
            }
        )
        self.env["spp.entitlement.inkind"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary2.id,
            }
        )

        cycle._compute_total_entitlements_count()
        self.assertEqual(cycle.total_entitlements_count, 2)

    @patch("odoo.fields.Date.today")
    def test_total_amount_computed_from_entitlements(self, mock_today):
        """total_amount sums the initial_amount of all cash entitlements."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Total Amount Cycle [CYCLE TEST]")
        self.env["spp.entitlement"].create(
            [
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary1.id,
                    "initial_amount": 150.0,
                    "valid_from": fields.Date.today(),
                    "currency_id": self.currency.id,
                },
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary2.id,
                    "initial_amount": 250.0,
                    "valid_from": fields.Date.today(),
                    "currency_id": self.currency.id,
                },
            ]
        )
        cycle._compute_total_amount()
        self.assertAlmostEqual(cycle.total_amount, 400.0)

    @patch("odoo.fields.Date.today")
    def test_total_amount_in_words(self, mock_today):
        """total_amount_in_words is populated when amount and currency are set."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Amount In Words Cycle [CYCLE TEST]")
        self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "initial_amount": 500.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
            }
        )
        cycle._compute_total_amount()
        cycle._compute_total_amount_in_words()
        self.assertIn("Five Hundred", cycle.total_amount_in_words)

        cycle_fr = cycle.with_context(lang="fr_FR")
        cycle_fr._compute_total_amount_in_words()
        self.assertIn("cinq cents", cycle_fr.total_amount_in_words.lower())

    def test_approval_state_mapping(self):
        """_compute_approval_state maps cycle state to the approval mixin state correctly."""
        cycle = self._make_cycle(name="Approval State Mapping Cycle [CYCLE TEST]")
        state_map = {
            "draft": "draft",
            "to_approve": "pending",
            "approved": "approved",
            "distributed": "approved",
            "cancelled": "rejected",
            "ended": "approved",
        }
        for cycle_state, expected_approval_state in state_map.items():
            cycle.write({"state": cycle_state})
            cycle._compute_approval_state()
            self.assertEqual(
                cycle.approval_state,
                expected_approval_state,
                f"cycle.state='{cycle_state}' should map to approval_state='{expected_approval_state}'",
            )

    def test_is_locked_field_default(self):
        """Newly created cycles are not locked."""
        cycle = self._make_cycle(name="Lock Default Cycle [CYCLE TEST]")
        self.assertFalse(cycle.is_locked)

    def test_is_locked_can_be_set(self):
        """is_locked and locked_reason can be written directly."""
        cycle = self._make_cycle(name="Lock Set Cycle [CYCLE TEST]")
        cycle.write({"is_locked": True, "locked_reason": "Background import in progress"})
        self.assertTrue(cycle.is_locked)
        self.assertEqual(cycle.locked_reason, "Background import in progress")

    def test_action_force_unlock_clears_lock_and_audits(self):
        """action_force_unlock clears the lock and records who did it in chatter."""
        cycle = self._make_cycle(name="Force Unlock Cycle [CYCLE TEST]")
        cycle.write({"is_locked": True, "locked_reason": "Import running"})
        message_count_before = len(cycle.message_ids)

        cycle.action_force_unlock()

        self.assertFalse(cycle.is_locked)
        self.assertFalse(cycle.locked_reason)
        # An audit message was posted
        self.assertGreater(len(cycle.message_ids), message_count_before)
        latest = cycle.message_ids[0]
        self.assertIn("manually cleared", latest.body)
        self.assertIn("Import running", latest.body)

    def test_action_force_unlock_noop_when_not_locked(self):
        """action_force_unlock is a no-op when the cycle is not locked."""
        cycle = self._make_cycle(name="Already Unlocked Cycle [CYCLE TEST]")
        message_count_before = len(cycle.message_ids)

        cycle.action_force_unlock()

        self.assertFalse(cycle.is_locked)
        # No audit message — nothing to unlock
        self.assertEqual(len(cycle.message_ids), message_count_before)

    # ------------------------------------------------------------------
    # get_entitlements
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_get_entitlements_by_state(self, mock_today):
        """get_entitlements returns only entitlements matching the requested states."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Get Entitlements Cycle [CYCLE TEST]")
        draft_ent = self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "initial_amount": 100.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
                "state": "draft",
            }
        )
        approved_ent = self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary2.id,
                "initial_amount": 200.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
                "state": "approved",
            }
        )

        draft_results = cycle.get_entitlements(["draft"])
        self.assertIn(draft_ent.id, draft_results.ids)
        self.assertNotIn(approved_ent.id, draft_results.ids)

        approved_results = cycle.get_entitlements(["approved"])
        self.assertIn(approved_ent.id, approved_results.ids)
        self.assertNotIn(draft_ent.id, approved_results.ids)

        all_results = cycle.get_entitlements(["draft", "approved"])
        self.assertIn(draft_ent.id, all_results.ids)
        self.assertIn(approved_ent.id, all_results.ids)

    @patch("odoo.fields.Date.today")
    def test_get_entitlements_count_flag(self, mock_today):
        """get_entitlements with count=True returns an integer, not a recordset."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Get Entitlements Count Cycle [CYCLE TEST]")
        self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "initial_amount": 100.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
                "state": "draft",
            }
        )
        count = cycle.get_entitlements(["draft"], count=True)
        self.assertIsInstance(count, int)
        self.assertEqual(count, 1)

    @patch("odoo.fields.Date.today")
    def test_get_entitlements_empty_state_returns_all(self, mock_today):
        """get_entitlements with an empty state list returns all entitlements for the cycle."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Get All Entitlements Cycle [CYCLE TEST]")
        for partner, amount in [(self.beneficiary1, 100.0), (self.beneficiary2, 200.0)]:
            self.env["spp.entitlement"].create(
                {
                    "cycle_id": cycle.id,
                    "partner_id": partner.id,
                    "initial_amount": amount,
                    "valid_from": fields.Date.today(),
                    "currency_id": self.currency.id,
                }
            )
        results = cycle.get_entitlements([])
        self.assertEqual(len(results), 2)

    # ------------------------------------------------------------------
    # prepare_entitlement
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_prepare_entitlement_creates_entitlements(self, mock_today):
        """prepare_entitlement() delegates to cycle manager and creates entitlements."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Prepare Entitlement Cycle [CYCLE TEST]")
        self._add_members(cycle)

        before = self.env["spp.entitlement"].search_count([("cycle_id", "=", cycle.id)])
        self.assertEqual(before, 0)

        cycle.prepare_entitlement()

        after = self.env["spp.entitlement"].search_count([("cycle_id", "=", cycle.id)])
        self.assertEqual(after, 2, "An entitlement should be created for each enrolled beneficiary.")

    def test_prepare_entitlement_raises_without_cycle_manager(self):
        """prepare_entitlement() raises UserError when no cycle manager is configured."""
        program_no_mgr = self.env["spp.program"].create({"name": "No Manager Program [CYCLE TEST]"})
        cycle = self.env["spp.cycle"].create(
            {
                "name": "No Manager Cycle [CYCLE TEST]",
                "program_id": program_no_mgr.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        with self.assertRaisesRegex(UserError, "No Cycle Manager defined"):
            cycle.prepare_entitlement()

    # ------------------------------------------------------------------
    # action_submit_for_approval (to_approve)
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_action_submit_for_approval_transitions_to_to_approve(self, mock_today):
        """action_submit_for_approval moves a draft cycle with entitlements to 'to_approve'."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Submit For Approval Cycle [CYCLE TEST]")
        self._add_members(cycle)
        cycle.prepare_entitlement()

        self.assertEqual(cycle.state, "draft")
        cycle.action_submit_for_approval()
        self.assertEqual(cycle.state, "to_approve")

    def test_action_submit_for_approval_raises_for_non_draft(self):
        """action_submit_for_approval raises UserError when cycle is not in draft."""
        cycle = self._make_cycle(name="Non-Draft Submit Cycle [CYCLE TEST]")
        cycle.write({"state": "to_approve"})
        with self.assertRaisesRegex(UserError, "Only draft cycles can be submitted"):
            cycle.action_submit_for_approval()

    def test_action_submit_for_approval_raises_when_locked(self):
        """action_submit_for_approval raises UserError when cycle is locked."""
        cycle = self._make_cycle(name="Locked Submit Cycle [CYCLE TEST]")
        cycle.write({"is_locked": True, "locked_reason": "Import running"})
        with self.assertRaisesRegex(UserError, "Cycle is locked"):
            cycle.action_submit_for_approval()

    @patch("odoo.fields.Date.today")
    def test_action_submit_for_approval_raises_without_entitlements(self, mock_today):
        """action_submit_for_approval raises UserError when there are no entitlements."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="No Entitlements Submit Cycle [CYCLE TEST]")
        with self.assertRaisesRegex(UserError, "Cannot submit cycle without entitlements"):
            cycle.action_submit_for_approval()

    # ------------------------------------------------------------------
    # action_approve
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_action_approve_transitions_to_approved(self, mock_today):
        """action_approve moves a 'to_approve' cycle to 'approved'."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Approve Cycle [CYCLE TEST]")
        self._add_members(cycle)
        cycle.prepare_entitlement()
        cycle.action_submit_for_approval()
        self.assertEqual(cycle.state, "to_approve")

        cycle.action_approve()
        self.assertEqual(cycle.state, "approved")

    @patch("odoo.fields.Date.today")
    def test_action_approve_raises_for_non_to_approve(self, mock_today):
        """action_approve raises UserError when cycle is not in 'to_approve' state."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Non-To-Approve Approval Cycle [CYCLE TEST]")
        with self.assertRaisesRegex(UserError, "Only cycles pending approval can be approved"):
            cycle.action_approve()

    # ------------------------------------------------------------------
    # action_reset_to_draft
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_action_reset_to_draft_from_to_approve(self, mock_today):
        """action_reset_to_draft returns a 'to_approve' cycle back to 'draft'."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Reset To Draft Cycle [CYCLE TEST]")
        self._add_members(cycle)
        cycle.prepare_entitlement()
        cycle.action_submit_for_approval()
        self.assertEqual(cycle.state, "to_approve")

        cycle.action_reset_to_draft()
        self.assertEqual(cycle.state, "draft")

    def test_action_reset_to_draft_raises_from_approved(self):
        """action_reset_to_draft raises UserError when cycle is already approved."""
        cycle = self._make_cycle(name="Approved Reset Cycle [CYCLE TEST]")
        cycle.write({"state": "approved"})
        with self.assertRaisesRegex(UserError, "Only cycles pending approval or cancelled"):
            cycle.action_reset_to_draft()

    # ------------------------------------------------------------------
    # mark_ended / mark_distributed / mark_cancelled
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_mark_ended_transitions_state(self, mock_today):
        """mark_ended() transitions an approved cycle to 'ended' via the cycle manager."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Mark Ended Cycle [CYCLE TEST]")
        self._add_members(cycle)
        cycle.prepare_entitlement()
        cycle.action_submit_for_approval()
        cycle.action_approve()
        self.assertEqual(cycle.state, "approved")

        cycle.mark_ended()
        self.assertEqual(cycle.state, "ended")

    # ------------------------------------------------------------------
    # unlink
    # ------------------------------------------------------------------

    def test_unlink_draft_cycle_without_members_or_entitlements(self):
        """A draft cycle with no members and no entitlements can be deleted."""
        cycle = self._make_cycle(name="Unlink Draft Cycle [CYCLE TEST]")
        cycle_id = cycle.id
        cycle.unlink()
        self.assertFalse(self.env["spp.cycle"].browse(cycle_id).exists())

    def test_unlink_draft_cycle_with_members_raises(self):
        """A draft cycle with enrolled members cannot be deleted."""
        cycle = self._make_cycle(name="Unlink With Members Cycle [CYCLE TEST]")
        self._add_members(cycle)
        with self.assertRaisesRegex(ValidationError, "beneficiaries are present"):
            cycle.unlink()

    @patch("odoo.fields.Date.today")
    def test_unlink_draft_cycle_with_draft_entitlements_raises(self, mock_today):
        """A draft cycle that already has draft entitlements cannot be deleted."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Unlink With Entitlements Cycle [CYCLE TEST]")
        self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "initial_amount": 100.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
                "state": "draft",
            }
        )
        with self.assertRaisesRegex(ValidationError, "Entitlements have been added"):
            cycle.unlink()

    def test_unlink_approved_cycle_raises(self):
        """An approved cycle cannot be deleted."""
        cycle = self._make_cycle(name="Unlink Approved Cycle [CYCLE TEST]")
        cycle.write({"state": "approved"})
        with self.assertRaisesRegex(ValidationError, "Once a cycle has been approved"):
            cycle.unlink()

    # ------------------------------------------------------------------
    # show_approve_entitlements_button
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_show_approve_entitlements_button_with_pending_validation(self, mock_today):
        """show_approve_entitlements_button is True when there are pending_validation entitlements."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Show Approve Button Cycle [CYCLE TEST]")
        self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "initial_amount": 100.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
                "state": "pending_validation",
            }
        )
        cycle._compute_show_approve_entitlement()
        self.assertTrue(cycle.show_approve_entitlements_button)

    @patch("odoo.fields.Date.today")
    def test_show_approve_entitlements_button_false_when_no_pending(self, mock_today):
        """show_approve_entitlements_button is False when there are no pending_validation entitlements."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="No Pending Approve Button Cycle [CYCLE TEST]")
        self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "initial_amount": 100.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
                "state": "approved",
            }
        )
        cycle._compute_show_approve_entitlement()
        self.assertFalse(cycle.show_approve_entitlements_button)

    # ------------------------------------------------------------------
    # all_entitlements_approved
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_all_entitlements_approved_true_when_all_approved(self, mock_today):
        """all_entitlements_approved is True only when every entitlement is approved."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="All Approved Cycle [CYCLE TEST]")
        self.env["spp.entitlement"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "initial_amount": 100.0,
                "valid_from": fields.Date.today(),
                "currency_id": self.currency.id,
                "state": "approved",
            }
        )
        cycle._compute_all_entitlements_approved()
        self.assertTrue(cycle.all_entitlements_approved)

    @patch("odoo.fields.Date.today")
    def test_all_entitlements_approved_false_when_mixed(self, mock_today):
        """all_entitlements_approved is False when at least one entitlement is not approved."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Mixed Approved Cycle [CYCLE TEST]")
        self.env["spp.entitlement"].create(
            [
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary1.id,
                    "initial_amount": 100.0,
                    "valid_from": fields.Date.today(),
                    "currency_id": self.currency.id,
                    "state": "approved",
                },
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary2.id,
                    "initial_amount": 200.0,
                    "valid_from": fields.Date.today(),
                    "currency_id": self.currency.id,
                    "state": "draft",
                },
            ]
        )
        cycle._compute_all_entitlements_approved()
        self.assertFalse(cycle.all_entitlements_approved)

    @patch("odoo.fields.Date.today")
    def test_all_entitlements_approved_false_when_no_entitlements(self, mock_today):
        """all_entitlements_approved is False when there are no entitlements at all."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="No Entitlements Approved Cycle [CYCLE TEST]")
        cycle._compute_all_entitlements_approved()
        self.assertFalse(cycle.all_entitlements_approved)

    # ------------------------------------------------------------------
    # inkind_entitlements_count
    # ------------------------------------------------------------------

    def test_inkind_entitlements_count(self):
        """_compute_inkind_entitlements_count counts in-kind entitlements correctly."""
        cycle = self._make_cycle(name="Inkind Count Cycle [CYCLE TEST]")
        self.env["spp.entitlement.inkind"].create({"cycle_id": cycle.id, "partner_id": self.beneficiary1.id})
        self.env["spp.entitlement.inkind"].create({"cycle_id": cycle.id, "partner_id": self.beneficiary2.id})
        cycle._compute_inkind_entitlements_count()
        self.assertEqual(cycle.inkind_entitlements_count, 2)

    # ------------------------------------------------------------------
    # _get_beneficiaries_domain
    # ------------------------------------------------------------------

    def test_get_beneficiaries_domain_with_state(self):
        """_get_beneficiaries_domain restricts to the given states."""
        cycle = self._make_cycle(name="Beneficiaries Domain Cycle [CYCLE TEST]")
        domain = cycle._get_beneficiaries_domain(["enrolled"])
        self.assertIn(("cycle_id", "=", cycle.id), domain)
        self.assertIn(("state", "in", ["enrolled"]), domain)

    def test_get_beneficiaries_domain_without_state(self):
        """_get_beneficiaries_domain without states does not add a state filter."""
        cycle = self._make_cycle(name="Beneficiaries No State Domain Cycle [CYCLE TEST]")
        domain = cycle._get_beneficiaries_domain()
        self.assertIn(("cycle_id", "=", cycle.id), domain)
        # No state filter should be present
        state_clauses = [clause for clause in domain if isinstance(clause, tuple) and clause[0] == "state"]
        self.assertEqual(len(state_clauses), 0)

    # ------------------------------------------------------------------
    # Legacy alias methods
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_to_approve_alias_calls_submit(self, mock_today):
        """to_approve() is a legacy alias for action_submit_for_approval()."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Legacy To Approve Alias Cycle [CYCLE TEST]")
        self._add_members(cycle)
        cycle.prepare_entitlement()
        cycle.to_approve()
        self.assertEqual(cycle.state, "to_approve")

    @patch("odoo.fields.Date.today")
    def test_approve_alias_calls_action_approve(self, mock_today):
        """approve() is a legacy alias for action_approve()."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Legacy Approve Alias Cycle [CYCLE TEST]")
        self._add_members(cycle)
        cycle.prepare_entitlement()
        cycle.to_approve()
        cycle.approve()
        self.assertEqual(cycle.state, "approved")

    @patch("odoo.fields.Date.today")
    def test_reset_draft_alias_calls_action_reset_to_draft(self, mock_today):
        """reset_draft() is a legacy alias for action_reset_to_draft()."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Legacy Reset Draft Alias Cycle [CYCLE TEST]")
        self._add_members(cycle)
        cycle.prepare_entitlement()
        cycle.to_approve()
        cycle.reset_draft()
        self.assertEqual(cycle.state, "draft")

    # ------------------------------------------------------------------
    # cycle_approval_definition_id computed field
    # ------------------------------------------------------------------

    def test_cycle_approval_definition_id_from_manager(self):
        """cycle_approval_definition_id is derived from the cycle manager's definition."""
        cycle = self._make_cycle(name="Approval Def Cycle [CYCLE TEST]")
        cycle._compute_cycle_approval_definition()
        self.assertEqual(cycle.cycle_approval_definition_id, self.cycle_approval_definition)

    def test_cycle_approval_definition_id_empty_without_manager(self):
        """cycle_approval_definition_id is empty when the program has no cycle manager."""
        program_no_mgr = self.env["spp.program"].create({"name": "No Manager Prog Def [CYCLE TEST]"})
        cycle = self.env["spp.cycle"].create(
            {
                "name": "No Def Cycle [CYCLE TEST]",
                "program_id": program_no_mgr.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        cycle._compute_cycle_approval_definition()
        self.assertFalse(cycle.cycle_approval_definition_id)

    # ------------------------------------------------------------------
    # open_entitlements_form / open_cycle_form / open_members_form
    # ------------------------------------------------------------------

    def test_open_entitlements_form_raises_without_manager(self):
        """open_entitlements_form raises UserError when no entitlement manager is defined."""
        program_no_mgr = self.env["spp.program"].create({"name": "No Ent Mgr Prog [CYCLE TEST]"})
        cycle = self.env["spp.cycle"].create(
            {
                "name": "No Ent Mgr Cycle [CYCLE TEST]",
                "program_id": program_no_mgr.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        with self.assertRaisesRegex(UserError, "No Entitlement Manager defined"):
            cycle.open_entitlements_form()

    def test_open_members_form_returns_action(self):
        """open_members_form returns a valid window action dict."""
        cycle = self._make_cycle(name="Open Members Form Cycle [CYCLE TEST]")
        action = cycle.open_members_form()
        self.assertEqual(action.get("type"), "ir.actions.act_window")
        self.assertIn(("cycle_id", "=", cycle.id), action.get("domain", []))

    def test_open_all_members_form_returns_action(self):
        """open_all_members_form returns a valid window action dict."""
        cycle = self._make_cycle(name="Open All Members Form Cycle [CYCLE TEST]")
        action = cycle.open_all_members_form()
        self.assertEqual(action.get("type"), "ir.actions.act_window")
        self.assertIn(("cycle_id", "=", cycle.id), action.get("domain", []))

    # ------------------------------------------------------------------
    # reject flow
    # ------------------------------------------------------------------

    @patch("odoo.fields.Date.today")
    def test_do_reject_transitions_to_cancelled(self, mock_today):
        """_do_reject() transitions a 'to_approve' cycle to 'cancelled'."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Reject Cycle [CYCLE TEST]")
        self._add_members(cycle)
        cycle.prepare_entitlement()
        cycle.action_submit_for_approval()
        self.assertEqual(cycle.state, "to_approve")

        cycle._do_reject(reason="Test rejection reason")
        self.assertEqual(cycle.state, "cancelled")

    @patch("odoo.fields.Date.today")
    def test_do_reject_cancels_pending_entitlements(self, mock_today):
        """_do_reject() also cancels entitlements that were in pending_validation."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle(name="Reject Cancels Entitlements Cycle [CYCLE TEST]")
        self._add_members(cycle)
        cycle.prepare_entitlement()
        cycle.action_submit_for_approval()

        # After submit, entitlements should be pending_validation
        pending = cycle.entitlement_ids.filtered(lambda e: e.state == "pending_validation")
        self.assertTrue(pending, "There should be pending entitlements after submission.")

        cycle._do_reject(reason="Budget cut")

        for ent in cycle.entitlement_ids:
            self.assertEqual(ent.state, "cancelled", "All pending entitlements must be cancelled on rejection.")

    def test_action_reject_raises_from_non_to_approve(self):
        """action_reject raises UserError when cycle is not in 'to_approve' state."""
        cycle = self._make_cycle(name="Reject Non-Pending Cycle [CYCLE TEST]")
        self.assertEqual(cycle.state, "draft")
        with self.assertRaisesRegex(UserError, "Only cycles pending approval can be rejected"):
            cycle.action_reject()
