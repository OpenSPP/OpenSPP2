"""Tests for GRM Programs integration - spp_grm_programs module."""

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGRMTicketPrograms(TransactionCase):
    """Test GRM ticket program-related fields and methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a ticket stage to satisfy required stage_id default
        cls.stage_open = (
            cls.env["spp.grm.ticket.stage"]
            .with_context(tracking_disable=True)
            .create({"name": "Open", "is_closed": False})
        )

        # Create a registrant partner
        cls.registrant = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Registrant",
                    "is_registrant": True,
                }
            )
        )

        # Create a second registrant for onchange tests
        cls.registrant2 = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Registrant 2",
                    "is_registrant": True,
                }
            )
        )

        # Create a program
        cls.program = cls.env["spp.program"].with_context(tracking_disable=True).create({"name": "Test Program"})

        # Create a cycle for the program
        cls.cycle = (
            cls.env["spp.cycle"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Cycle",
                    "program_id": cls.program.id,
                    "start_date": fields.Date.today(),
                    "end_date": fields.Date.today(),
                }
            )
        )

        # Create a program membership
        cls.membership = (
            cls.env["spp.program.membership"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": cls.registrant.id,
                    "program_id": cls.program.id,
                    "state": "enrolled",
                }
            )
        )

        # Find a usable journal for entitlement creation
        cls.journal = cls.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "=", cls.env.company.id)],
            limit=1,
        )

        # Create an entitlement
        cls.entitlement = (
            cls.env["spp.entitlement"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": cls.registrant.id,
                    "cycle_id": cls.cycle.id,
                    "initial_amount": 500.0,
                    "is_cash_entitlement": True,
                }
            )
        )

        # Create a payment linked to the entitlement
        cls.payment = (
            cls.env["spp.payment"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "entitlement_id": cls.entitlement.id,
                    "cycle_id": cls.cycle.id,
                    "amount_issued": 500.0,
                    "state": "issued",
                }
            )
        )

        # Create a base ticket (no program fields)
        cls.ticket = (
            cls.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test GRM Ticket",
                    "description": "Test ticket for program integration",
                    "partner_id": cls.registrant.id,
                    "stage_id": cls.stage_open.id,
                }
            )
        )

    # -------------------------------------------------------------------------
    # Tests for _compute_program_info
    # -------------------------------------------------------------------------

    def test_compute_program_info_no_links(self):
        """Computed fields are empty/zero when no program records are linked."""
        self.assertEqual(self.ticket.enrollment_status, "")
        self.assertEqual(self.ticket.entitlement_amount, 0.0)
        self.assertEqual(self.ticket.payment_amount, 0.0)

    def test_compute_program_info_with_membership_enrolled(self):
        """enrollment_status reflects the human-readable label of membership state."""
        self.ticket.with_context(tracking_disable=True).write({"program_membership_id": self.membership.id})
        # "enrolled" state should produce the label "Enrolled"
        self.assertEqual(self.ticket.enrollment_status, "Enrolled")

    def test_compute_program_info_membership_state_draft(self):
        """enrollment_status shows 'Draft' when membership is in draft state."""
        draft_membership = (
            self.env["spp.program.membership"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.registrant2.id,
                    "program_id": self.program.id,
                    "state": "draft",
                }
            )
        )
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Draft Membership Ticket",
                    "description": "Testing draft membership state",
                    "partner_id": self.registrant2.id,
                    "stage_id": self.stage_open.id,
                    "program_membership_id": draft_membership.id,
                }
            )
        )
        self.assertEqual(ticket.enrollment_status, "Draft")

    def test_compute_program_info_with_entitlement(self):
        """entitlement_amount is taken from entitlement initial_amount."""
        self.ticket.with_context(tracking_disable=True).write({"entitlement_id": self.entitlement.id})
        self.assertEqual(self.ticket.entitlement_amount, 500.0)

    def test_compute_program_info_with_payment(self):
        """payment_amount is taken from payment amount_issued."""
        self.ticket.with_context(tracking_disable=True).write({"payment_id": self.payment.id})
        self.assertEqual(self.ticket.payment_amount, 500.0)

    def test_compute_program_info_all_linked(self):
        """All computed fields populated when all program records are linked."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Full Program Ticket",
                    "description": "Ticket with all program records linked",
                    "partner_id": self.registrant.id,
                    "stage_id": self.stage_open.id,
                    "program_id": self.program.id,
                    "program_membership_id": self.membership.id,
                    "cycle_id": self.cycle.id,
                    "entitlement_id": self.entitlement.id,
                    "payment_id": self.payment.id,
                }
            )
        )
        self.assertEqual(ticket.enrollment_status, "Enrolled")
        self.assertEqual(ticket.entitlement_amount, 500.0)
        self.assertEqual(ticket.payment_amount, 500.0)

    def test_compute_program_info_clears_on_unlink(self):
        """Computed fields reset to defaults when linked records are removed."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Unlink Test Ticket",
                    "description": "Ticket for unlink test",
                    "partner_id": self.registrant.id,
                    "stage_id": self.stage_open.id,
                    "program_membership_id": self.membership.id,
                    "entitlement_id": self.entitlement.id,
                    "payment_id": self.payment.id,
                }
            )
        )
        # Confirm values are set
        self.assertEqual(ticket.enrollment_status, "Enrolled")
        self.assertEqual(ticket.entitlement_amount, 500.0)
        self.assertEqual(ticket.payment_amount, 500.0)

        # Remove all links
        ticket.with_context(tracking_disable=True).write(
            {
                "program_membership_id": False,
                "entitlement_id": False,
                "payment_id": False,
            }
        )
        self.assertEqual(ticket.enrollment_status, "")
        self.assertEqual(ticket.entitlement_amount, 0.0)
        self.assertEqual(ticket.payment_amount, 0.0)

    # -------------------------------------------------------------------------
    # Tests for _onchange_program_membership
    # -------------------------------------------------------------------------

    def test_onchange_program_membership_fills_membership(self):
        """Setting registrant and program auto-fills program_membership_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Onchange Test",
                "description": "Testing onchange",
                "partner_id": self.registrant.id,
                "stage_id": self.stage_open.id,
                "registrant_id": self.registrant.id,
                "program_id": self.program.id,
            }
        )
        ticket._onchange_program_membership()
        self.assertEqual(ticket.program_membership_id, self.membership)

    def test_onchange_program_membership_no_match(self):
        """No membership set when registrant is not enrolled in the program."""
        other_program = self.env["spp.program"].with_context(tracking_disable=True).create({"name": "Other Program"})

        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "No Match Ticket",
                "description": "Testing no match",
                "partner_id": self.registrant.id,
                "registrant_id": self.registrant.id,
                "program_id": other_program.id,
            }
        )
        ticket._onchange_program_membership()
        self.assertFalse(ticket.program_membership_id)

    def test_onchange_program_membership_missing_registrant(self):
        """No membership lookup when registrant is not set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Missing Registrant",
                "description": "Testing missing registrant",
                "partner_id": self.registrant.id,
                "program_id": self.program.id,
            }
        )
        # registrant_id not set
        ticket.registrant_id = False
        ticket._onchange_program_membership()
        self.assertFalse(ticket.program_membership_id)

    def test_onchange_program_membership_missing_program(self):
        """No membership lookup when program is not set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Missing Program",
                "description": "Testing missing program",
                "partner_id": self.registrant.id,
                "registrant_id": self.registrant.id,
            }
        )
        # program_id not set
        ticket.program_id = False
        ticket._onchange_program_membership()
        self.assertFalse(ticket.program_membership_id)

    # -------------------------------------------------------------------------
    # Tests for _onchange_membership
    # -------------------------------------------------------------------------

    def test_onchange_membership_fills_program(self):
        """Setting program_membership_id auto-fills program_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Membership Onchange",
                "description": "Testing membership onchange",
                "partner_id": self.registrant.id,
                "program_membership_id": self.membership.id,
            }
        )
        ticket._onchange_membership()
        self.assertEqual(ticket.program_id, self.program)

    def test_onchange_membership_fills_registrant_when_empty(self):
        """Setting program_membership_id fills registrant_id when not already set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Membership Fills Registrant",
                "description": "Testing registrant fill",
                "partner_id": self.registrant.id,
                "program_membership_id": self.membership.id,
            }
        )
        # Clear registrant so the onchange can fill it
        ticket.registrant_id = False
        ticket._onchange_membership()
        self.assertEqual(ticket.registrant_id, self.registrant)

    def test_onchange_membership_does_not_overwrite_registrant(self):
        """Setting program_membership_id does not overwrite an existing registrant_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "No Overwrite Test",
                "description": "Testing no overwrite",
                "partner_id": self.registrant2.id,
                "registrant_id": self.registrant2.id,
                "program_membership_id": self.membership.id,
            }
        )
        ticket._onchange_membership()
        # registrant_id should remain as registrant2, not get replaced by membership.partner_id
        self.assertEqual(ticket.registrant_id, self.registrant2)

    def test_onchange_membership_no_membership(self):
        """No change when program_membership_id is not set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "No Membership",
                "description": "Testing no membership",
                "partner_id": self.registrant.id,
            }
        )
        ticket.program_membership_id = False
        ticket._onchange_membership()
        # program_id should remain empty
        self.assertFalse(ticket.program_id)

    # -------------------------------------------------------------------------
    # Tests for _onchange_cycle
    # -------------------------------------------------------------------------

    def test_onchange_cycle_clears_entitlement_and_payment(self):
        """Changing cycle clears entitlement_id and payment_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Cycle Onchange",
                "description": "Testing cycle onchange",
                "partner_id": self.registrant.id,
                "cycle_id": self.cycle.id,
                "entitlement_id": self.entitlement.id,
                "payment_id": self.payment.id,
            }
        )
        ticket._onchange_cycle()
        self.assertFalse(ticket.entitlement_id)
        self.assertFalse(ticket.payment_id)

    def test_onchange_cycle_fills_program_when_empty(self):
        """Changing cycle fills program_id when not already set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Cycle Fills Program",
                "description": "Testing cycle fills program",
                "partner_id": self.registrant.id,
                "cycle_id": self.cycle.id,
            }
        )
        # Ensure program_id is not set
        ticket.program_id = False
        ticket._onchange_cycle()
        self.assertEqual(ticket.program_id, self.program)

    def test_onchange_cycle_does_not_overwrite_program(self):
        """Changing cycle does not overwrite an already-set program_id."""
        other_program = self.env["spp.program"].with_context(tracking_disable=True).create({"name": "Pre-set Program"})

        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "No Overwrite Program",
                "description": "Testing no overwrite program",
                "partner_id": self.registrant.id,
                "program_id": other_program.id,
                "cycle_id": self.cycle.id,
            }
        )
        ticket._onchange_cycle()
        # program_id should remain as other_program
        self.assertEqual(ticket.program_id, other_program)

    def test_onchange_cycle_no_cycle(self):
        """No program fill when cycle is not set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "No Cycle",
                "description": "Testing no cycle",
                "partner_id": self.registrant.id,
            }
        )
        ticket.cycle_id = False
        ticket._onchange_cycle()
        self.assertFalse(ticket.program_id)

    # -------------------------------------------------------------------------
    # Tests for _onchange_entitlement
    # -------------------------------------------------------------------------

    def test_onchange_entitlement_clears_payment(self):
        """Changing entitlement clears payment_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Entitlement Onchange",
                "description": "Testing entitlement onchange",
                "partner_id": self.registrant.id,
                "entitlement_id": self.entitlement.id,
                "payment_id": self.payment.id,
            }
        )
        ticket._onchange_entitlement()
        self.assertFalse(ticket.payment_id)

    def test_onchange_entitlement_fills_cycle_and_program(self):
        """Setting entitlement fills cycle and program when not already set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Entitlement Fills Cycle",
                "description": "Testing entitlement fills cycle",
                "partner_id": self.registrant.id,
                "entitlement_id": self.entitlement.id,
            }
        )
        ticket.cycle_id = False
        ticket.program_id = False
        ticket._onchange_entitlement()
        self.assertEqual(ticket.cycle_id, self.cycle)
        self.assertEqual(ticket.program_id, self.program)

    def test_onchange_entitlement_fills_registrant_when_empty(self):
        """Setting entitlement fills registrant_id when not already set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Entitlement Fills Registrant",
                "description": "Testing registrant fill from entitlement",
                "partner_id": self.registrant.id,
                "entitlement_id": self.entitlement.id,
            }
        )
        ticket.registrant_id = False
        ticket._onchange_entitlement()
        self.assertEqual(ticket.registrant_id, self.registrant)

    def test_onchange_entitlement_does_not_overwrite_registrant(self):
        """Setting entitlement does not overwrite an existing registrant_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Entitlement No Overwrite",
                "description": "Testing no overwrite registrant",
                "partner_id": self.registrant2.id,
                "registrant_id": self.registrant2.id,
                "entitlement_id": self.entitlement.id,
            }
        )
        ticket._onchange_entitlement()
        self.assertEqual(ticket.registrant_id, self.registrant2)

    def test_onchange_entitlement_no_entitlement(self):
        """No error or fill when entitlement is not set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "No Entitlement",
                "description": "Testing no entitlement",
                "partner_id": self.registrant.id,
            }
        )
        ticket.entitlement_id = False
        ticket._onchange_entitlement()
        self.assertFalse(ticket.cycle_id)

    # -------------------------------------------------------------------------
    # Tests for _onchange_payment
    # -------------------------------------------------------------------------

    def test_onchange_payment_fills_entitlement_when_empty(self):
        """Setting payment fills entitlement_id when not already set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Payment Fills Entitlement",
                "description": "Testing payment fills entitlement",
                "partner_id": self.registrant.id,
                "payment_id": self.payment.id,
            }
        )
        ticket.entitlement_id = False
        ticket._onchange_payment()
        self.assertEqual(ticket.entitlement_id, self.entitlement)

    def test_onchange_payment_does_not_overwrite_entitlement(self):
        """Setting payment does not overwrite an existing entitlement_id."""
        other_entitlement = (
            self.env["spp.entitlement"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.registrant.id,
                    "cycle_id": self.cycle.id,
                    "initial_amount": 100.0,
                    "is_cash_entitlement": True,
                }
            )
        )
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Payment No Overwrite Entitlement",
                "description": "Testing no overwrite entitlement",
                "partner_id": self.registrant.id,
                "entitlement_id": other_entitlement.id,
                "payment_id": self.payment.id,
            }
        )
        ticket._onchange_payment()
        self.assertEqual(ticket.entitlement_id, other_entitlement)

    def test_onchange_payment_fills_cycle(self):
        """Setting payment fills cycle_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Payment Fills Cycle",
                "description": "Testing payment fills cycle",
                "partner_id": self.registrant.id,
                "payment_id": self.payment.id,
            }
        )
        ticket.cycle_id = False
        ticket._onchange_payment()
        self.assertEqual(ticket.cycle_id, self.cycle)

    def test_onchange_payment_fills_registrant_when_empty(self):
        """Setting payment fills registrant_id when not already set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Payment Fills Registrant",
                "description": "Testing payment fills registrant",
                "partner_id": self.registrant.id,
                "payment_id": self.payment.id,
            }
        )
        ticket.registrant_id = False
        ticket._onchange_payment()
        self.assertEqual(ticket.registrant_id, self.registrant)

    def test_onchange_payment_does_not_overwrite_registrant(self):
        """Setting payment does not overwrite an existing registrant_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Payment No Overwrite Registrant",
                "description": "Testing no overwrite registrant from payment",
                "partner_id": self.registrant2.id,
                "registrant_id": self.registrant2.id,
                "payment_id": self.payment.id,
            }
        )
        ticket._onchange_payment()
        self.assertEqual(ticket.registrant_id, self.registrant2)

    def test_onchange_payment_no_payment(self):
        """No error or fill when payment is not set."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "No Payment",
                "description": "Testing no payment",
                "partner_id": self.registrant.id,
            }
        )
        ticket.payment_id = False
        ticket._onchange_payment()
        self.assertFalse(ticket.entitlement_id)

    # -------------------------------------------------------------------------
    # Tests for action_view_program
    # -------------------------------------------------------------------------

    def test_action_view_program_with_program(self):
        """action_view_program returns an act_window action for the linked program."""
        self.ticket.with_context(tracking_disable=True).write({"program_id": self.program.id})
        action = self.ticket.action_view_program()
        self.assertIsInstance(action, dict)
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.program")
        self.assertEqual(action["res_id"], self.program.id)
        self.assertEqual(action["view_mode"], "form")

    def test_action_view_program_without_program(self):
        """action_view_program returns False when no program is linked."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "No Program Ticket",
                    "description": "Ticket with no program",
                    "partner_id": self.registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        result = ticket.action_view_program()
        self.assertFalse(result)

    # -------------------------------------------------------------------------
    # Tests for action_view_entitlement
    # -------------------------------------------------------------------------

    def test_action_view_entitlement_with_entitlement(self):
        """action_view_entitlement returns an act_window action for the linked entitlement."""
        self.ticket.with_context(tracking_disable=True).write({"entitlement_id": self.entitlement.id})
        action = self.ticket.action_view_entitlement()
        self.assertIsInstance(action, dict)
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.entitlement")
        self.assertEqual(action["res_id"], self.entitlement.id)
        self.assertEqual(action["view_mode"], "form")

    def test_action_view_entitlement_without_entitlement(self):
        """action_view_entitlement returns False when no entitlement is linked."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "No Entitlement Ticket",
                    "description": "Ticket with no entitlement",
                    "partner_id": self.registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        result = ticket.action_view_entitlement()
        self.assertFalse(result)

    # -------------------------------------------------------------------------
    # Tests for action_view_payment
    # -------------------------------------------------------------------------

    def test_action_view_payment_with_payment(self):
        """action_view_payment returns an act_window action for the linked payment."""
        self.ticket.with_context(tracking_disable=True).write({"payment_id": self.payment.id})
        action = self.ticket.action_view_payment()
        self.assertIsInstance(action, dict)
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.payment")
        self.assertEqual(action["res_id"], self.payment.id)
        self.assertEqual(action["view_mode"], "form")

    def test_action_view_payment_without_payment(self):
        """action_view_payment returns False when no payment is linked."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "No Payment Ticket",
                    "description": "Ticket with no payment",
                    "partner_id": self.registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        result = ticket.action_view_payment()
        self.assertFalse(result)

    # -------------------------------------------------------------------------
    # Tests for field presence (structural / smoke tests)
    # -------------------------------------------------------------------------

    def test_program_fields_exist_on_ticket(self):
        """Confirm program-related fields are present on the GRM ticket model."""
        ticket_fields = self.env["spp.grm.ticket"]._fields
        for field_name in (
            "program_id",
            "program_membership_id",
            "cycle_id",
            "entitlement_id",
            "payment_id",
            "enrollment_status",
            "entitlement_amount",
            "payment_amount",
        ):
            self.assertIn(
                field_name,
                ticket_fields,
                f"Field '{field_name}' should exist on spp.grm.ticket",
            )

    def test_ticket_creation_with_program_fields(self):
        """A ticket with program fields can be created without error."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Full Linked Ticket",
                    "description": "Ticket with all program links",
                    "partner_id": self.registrant.id,
                    "stage_id": self.stage_open.id,
                    "program_id": self.program.id,
                    "program_membership_id": self.membership.id,
                    "cycle_id": self.cycle.id,
                    "entitlement_id": self.entitlement.id,
                    "payment_id": self.payment.id,
                }
            )
        )
        self.assertTrue(ticket.id)
        self.assertEqual(ticket.program_id, self.program)
        self.assertEqual(ticket.program_membership_id, self.membership)
        self.assertEqual(ticket.cycle_id, self.cycle)
        self.assertEqual(ticket.entitlement_id, self.entitlement)
        self.assertEqual(ticket.payment_id, self.payment)

    # -------------------------------------------------------------------------
    # Tests for membership state labels (ensure all states resolve correctly)
    # -------------------------------------------------------------------------

    def _create_ticket_with_membership_state(self, registrant, state):
        """Helper to create a ticket with a membership in the given state."""
        # Create a fresh program to avoid unique-per-program constraint
        program = self.env["spp.program"].with_context(tracking_disable=True).create({"name": f"State Program {state}"})
        membership = (
            self.env["spp.program.membership"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": registrant.id,
                    "program_id": program.id,
                    "state": state,
                }
            )
        )
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": f"Ticket {state}",
                    "description": f"Ticket with membership state {state}",
                    "partner_id": registrant.id,
                    "stage_id": self.stage_open.id,
                    "program_membership_id": membership.id,
                }
            )
        )
        return ticket

    def test_enrollment_status_paused(self):
        """enrollment_status shows 'Paused' for paused membership."""
        ticket = self._create_ticket_with_membership_state(self.registrant2, "paused")
        self.assertEqual(ticket.enrollment_status, "Paused")

    def test_enrollment_status_exited(self):
        """enrollment_status shows 'Exited' for exited membership."""
        # Create a unique registrant to avoid membership uniqueness constraint
        registrant = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Exited Registrant", "is_registrant": True})
        )
        ticket = self._create_ticket_with_membership_state(registrant, "exited")
        self.assertEqual(ticket.enrollment_status, "Exited")

    def test_enrollment_status_not_eligible(self):
        """enrollment_status shows 'Not Eligible' for not_eligible membership."""
        registrant = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Not Eligible Registrant", "is_registrant": True})
        )
        ticket = self._create_ticket_with_membership_state(registrant, "not_eligible")
        self.assertEqual(ticket.enrollment_status, "Not Eligible")

    def test_enrollment_status_duplicated(self):
        """enrollment_status shows 'Duplicated' for duplicated membership."""
        registrant = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Duplicated Registrant", "is_registrant": True})
        )
        ticket = self._create_ticket_with_membership_state(registrant, "duplicated")
        self.assertEqual(ticket.enrollment_status, "Duplicated")
