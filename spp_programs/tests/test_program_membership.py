# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestProgramMembership(TransactionCase):
    """Tests for spp.program.membership model.

    Covers membership creation, state transitions, uniqueness constraint,
    computed fields, and action methods.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.registrant_1 = cls.env["res.partner"].create(
            {
                "name": "Registrant Membership A [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.registrant_2 = cls.env["res.partner"].create(
            {
                "name": "Registrant Membership B [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.individual = cls.env["res.partner"].create(
            {
                "name": "Individual Membership [TEST]",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.program = cls.env["spp.program"].create({"name": "Program Membership Test [TEST]"})
        cls.program_2 = cls.env["spp.program"].create({"name": "Program Membership Test 2 [TEST]"})

    def _create_membership(self, partner=None, program=None, state="draft"):
        partner = partner or self.registrant_1
        program = program or self.program
        return self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": program.id,
                "state": state,
            }
        )

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def test_01_create_membership(self):
        """A membership record can be created with required fields."""
        membership = self._create_membership()

        self.assertTrue(membership.id, "Membership should be created with a valid ID.")
        self.assertEqual(membership.partner_id, self.registrant_1)
        self.assertEqual(membership.program_id, self.program)
        self.assertEqual(membership.state, "draft")

    def test_02_create_membership_defaults_to_draft(self):
        """When no state is given, membership defaults to 'draft'."""
        membership = self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant_2.id,
                "program_id": self.program.id,
            }
        )
        self.assertEqual(membership.state, "draft")

    # ------------------------------------------------------------------
    # Uniqueness constraint
    # ------------------------------------------------------------------

    @mute_logger("odoo.sql_db")
    def test_03_unique_partner_per_program_constraint(self):
        """A partner cannot be enrolled in the same program twice."""
        self._create_membership(partner=self.registrant_1, program=self.program)

        with self.assertRaises(ValidationError):
            self._create_membership(partner=self.registrant_1, program=self.program)

    def test_04_same_partner_different_programs_allowed(self):
        """The same partner may have memberships in different programs."""
        membership_a = self._create_membership(partner=self.registrant_2, program=self.program)
        membership_b = self._create_membership(partner=self.registrant_2, program=self.program_2)

        self.assertTrue(membership_a.id)
        self.assertTrue(membership_b.id)

    # ------------------------------------------------------------------
    # enrollment_date computed field
    # ------------------------------------------------------------------

    def test_05_enrollment_date_set_when_state_is_enrolled(self):
        """enrollment_date is populated when the state transitions to 'enrolled'."""
        membership = self._create_membership(state="enrolled")

        self.assertIsNotNone(
            membership.enrollment_date,
            "enrollment_date should be set when state is 'enrolled'.",
        )

    def test_06_enrollment_date_not_set_for_draft(self):
        """enrollment_date is not populated for a draft membership."""
        membership = self._create_membership(state="draft")

        # enrollment_date is a stored computed field that only sets on 'enrolled'
        self.assertFalse(
            membership.enrollment_date,
            "enrollment_date should not be set for a draft membership.",
        )

    # ------------------------------------------------------------------
    # State transitions via action methods
    # ------------------------------------------------------------------

    def test_07_action_pause_from_enrolled(self):
        """action_pause() transitions an enrolled membership to 'paused'."""
        membership = self._create_membership(state="enrolled")
        membership.action_pause()

        self.assertEqual(membership.state, "paused")

    def test_08_action_pause_from_non_enrolled_raises(self):
        """action_pause() raises UserError when membership is not enrolled."""
        membership = self._create_membership(state="draft")

        with self.assertRaisesRegex(UserError, "Only enrolled memberships can be paused"):
            membership.action_pause()

    def test_09_action_resume_from_paused(self):
        """action_resume() transitions a paused membership back to 'enrolled'."""
        membership = self._create_membership(state="paused")
        membership.action_resume()

        self.assertEqual(membership.state, "enrolled")
        self.assertIsNotNone(
            membership.enrollment_date,
            "enrollment_date should be set after resuming.",
        )

    def test_10_action_resume_from_non_paused_raises(self):
        """action_resume() raises UserError when membership is not paused."""
        membership = self._create_membership(state="enrolled")

        with self.assertRaisesRegex(UserError, "Only paused memberships can be resumed"):
            membership.action_resume()

    def test_11_action_exit_from_enrolled(self):
        """action_exit() transitions an enrolled membership to 'exited' and sets exit_date."""
        membership = self._create_membership(state="enrolled")
        membership.action_exit()

        self.assertEqual(membership.state, "exited")
        self.assertEqual(
            membership.exit_date,
            fields.Date.today(),
            "exit_date should be set to today when exiting.",
        )

    def test_12_action_exit_from_paused(self):
        """action_exit() transitions a paused membership to 'exited'."""
        membership = self._create_membership(state="paused")
        membership.action_exit()

        self.assertEqual(membership.state, "exited")
        self.assertIsNotNone(membership.exit_date)

    def test_13_action_exit_from_invalid_state_raises(self):
        """action_exit() raises UserError when membership is in draft state."""
        membership = self._create_membership(state="draft")

        with self.assertRaisesRegex(UserError, "Only enrolled or paused memberships can be exited"):
            membership.action_exit()

    def test_14_back_to_draft_resets_state(self):
        """back_to_draft() resets any membership to 'draft'."""
        membership = self._create_membership(state="enrolled")
        membership.back_to_draft()

        self.assertEqual(membership.state, "draft")

    # ------------------------------------------------------------------
    # Full lifecycle
    # ------------------------------------------------------------------

    def test_15_full_lifecycle_draft_enrolled_paused_exited(self):
        """A membership can follow the complete draft → enrolled → paused → exited lifecycle."""
        program = self.env["spp.program"].create({"name": "Lifecycle Program [TEST]"})
        partner = self.env["res.partner"].create(
            {
                "name": "Lifecycle Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        membership = self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": program.id,
                "state": "draft",
            }
        )

        # draft → enrolled
        membership.write({"state": "enrolled"})
        self.assertEqual(membership.state, "enrolled")

        # enrolled → paused
        membership.action_pause()
        self.assertEqual(membership.state, "paused")

        # paused → enrolled (resume)
        membership.action_resume()
        self.assertEqual(membership.state, "enrolled")

        # enrolled → exited
        membership.action_exit()
        self.assertEqual(membership.state, "exited")
        self.assertIsNotNone(membership.exit_date)

    # ------------------------------------------------------------------
    # registrant_id field
    # ------------------------------------------------------------------

    def test_16_registrant_id_reflects_partner_id(self):
        """registrant_id is a related integer field equal to partner_id.id."""
        membership = self._create_membership()

        self.assertEqual(
            membership.registrant_id,
            self.registrant_1.id,
            "registrant_id should be the integer ID of partner_id.",
        )

    # ------------------------------------------------------------------
    # open_beneficiaries_form action
    # ------------------------------------------------------------------

    def test_17_open_beneficiaries_form_returns_act_window(self):
        """open_beneficiaries_form() returns a valid act_window action."""
        membership = self._create_membership(state="enrolled")
        action = membership.open_beneficiaries_form()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.program.membership")
        self.assertEqual(action["res_id"], membership.id)
        self.assertEqual(action["target"], "new")

    # ------------------------------------------------------------------
    # open_registrant_form action
    # ------------------------------------------------------------------

    def test_18_open_registrant_form_for_group_partner(self):
        """open_registrant_form() returns the group form view for a group partner."""
        membership = self._create_membership(partner=self.registrant_1, state="enrolled")
        action = membership.open_registrant_form()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], self.registrant_1.id)
        self.assertTrue(
            action["context"].get("default_is_group"),
            "Context should have default_is_group=True for a group partner.",
        )

    def test_19_open_registrant_form_for_individual_partner(self):
        """open_registrant_form() returns the individual form view for an individual partner."""
        program = self.env["spp.program"].create({"name": "Individual Membership Program [TEST]"})
        membership = self.env["spp.program.membership"].create(
            {
                "partner_id": self.individual.id,
                "program_id": program.id,
                "state": "enrolled",
            }
        )
        action = membership.open_registrant_form()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.partner")
        self.assertFalse(
            action["context"].get("default_is_group"),
            "Context should have default_is_group=False for an individual partner.",
        )

    # ------------------------------------------------------------------
    # deduplication_status
    # ------------------------------------------------------------------

    def test_23_deduplication_status_defaults_to_new(self):
        """deduplication_status defaults to 'new' on creation."""
        membership = self._create_membership()

        self.assertEqual(
            membership.deduplication_status,
            "new",
            "deduplication_status should default to 'new'.",
        )

    # ------------------------------------------------------------------
    # Cycle membership unlink restriction
    # ------------------------------------------------------------------

    def test_24_cycle_membership_unlink_allowed_for_draft_cycle(self):
        """Cycle memberships can be deleted when the cycle is in draft state."""
        program = self.env["spp.program"].create({"name": "Unlink Program [TEST]"})
        partner = self.env["res.partner"].create(
            {
                "name": "Unlink Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Draft Cycle Unlink [TEST]",
                "program_id": program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
                "state": "draft",
            }
        )
        cycle_membership = self.env["spp.cycle.membership"].create(
            {
                "partner_id": partner.id,
                "cycle_id": cycle.id,
            }
        )

        # Should not raise
        cycle_membership.unlink()

        self.assertFalse(
            cycle_membership.exists(),
            "Cycle membership should have been deleted.",
        )

    def test_25_cycle_membership_unlink_blocked_for_non_draft_cycle(self):
        """Cycle memberships cannot be deleted when the cycle is not in draft state."""
        program = self.env["spp.program"].create({"name": "Unlink Blocked Program [TEST]"})
        partner = self.env["res.partner"].create(
            {
                "name": "Unlink Blocked Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Active Cycle Unlink [TEST]",
                "program_id": program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        # Move cycle to a non-draft state
        cycle.write({"state": "approved"})

        cycle_membership = self.env["spp.cycle.membership"].create(
            {
                "partner_id": partner.id,
                "cycle_id": cycle.id,
            }
        )

        with self.assertRaises(ValidationError):
            cycle_membership.unlink()

    # ------------------------------------------------------------------
    # Cycle membership uniqueness constraint
    # ------------------------------------------------------------------

    def test_26_unique_partner_per_cycle_constraint(self):
        """A partner cannot have duplicate cycle memberships in the same cycle."""
        program = self.env["spp.program"].create({"name": "Cycle Unique Program [TEST]"})
        partner = self.env["res.partner"].create(
            {
                "name": "Cycle Unique Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Cycle Unique [TEST]",
                "program_id": program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

        self.env["spp.cycle.membership"].create({"partner_id": partner.id, "cycle_id": cycle.id})

        with self.assertRaises(ValidationError):
            self.env["spp.cycle.membership"].create({"partner_id": partner.id, "cycle_id": cycle.id})
