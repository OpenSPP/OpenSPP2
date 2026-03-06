"""Tests for GRMTicketRegistry — the spp_grm_registry extension of spp.grm.ticket."""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestGRMTicketRegistryFields(TransactionCase):
    """Test the registry-specific fields added to spp.grm.ticket."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.stage_open = (
            cls.env["spp.grm.ticket.stage"]
            .with_context(tracking_disable=True)
            .create({"name": "Open", "is_closed": False})
        )

        # An individual registrant
        cls.individual = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Individual",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
        )

        # A household (group) registrant
        cls.household = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Household",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
        )

        # A base ticket with no registrant (to test the no-registrant paths)
        cls.base_ticket = (
            cls.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Base Ticket",
                    "description": "No registrant",
                    "partner_id": cls.individual.id,
                    "stage_id": cls.stage_open.id,
                }
            )
        )

    # ------------------------------------------------------------------ #
    # Field defaults                                                       #
    # ------------------------------------------------------------------ #

    def test_new_ticket_has_no_registrant_by_default(self):
        """registrant_id, household_id and area_id default to False."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Empty Registrant Ticket",
                    "description": "desc",
                    "partner_id": self.individual.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        self.assertFalse(ticket.registrant_id)
        self.assertFalse(ticket.household_id)
        self.assertFalse(ticket.area_id)

    # ------------------------------------------------------------------ #
    # _compute_repeat_count — no registrant branch                        #
    # ------------------------------------------------------------------ #

    def test_repeat_count_zero_when_no_registrant(self):
        """repeat_count and is_repeat are 0/False when registrant_id is empty."""
        self.assertEqual(self.base_ticket.repeat_count, 0)
        self.assertFalse(self.base_ticket.is_repeat)

    # ------------------------------------------------------------------ #
    # _compute_repeat_count — with registrant, no other tickets           #
    # ------------------------------------------------------------------ #

    def test_repeat_count_zero_when_only_one_ticket(self):
        """A registrant with a single ticket has repeat_count = 0."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Solo Ticket",
                    "description": "desc",
                    "partner_id": self.individual.id,
                    "registrant_id": self.individual.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        self.assertEqual(ticket.repeat_count, 0)
        self.assertFalse(ticket.is_repeat)

    # ------------------------------------------------------------------ #
    # _compute_repeat_count — with registrant, multiple tickets           #
    # ------------------------------------------------------------------ #

    def test_repeat_count_increments_for_same_registrant(self):
        """Two tickets for the same registrant: each sees the other as a repeat."""
        # Use a fresh individual to avoid cross-test interference
        registrant = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Repeat Individual", "is_registrant": True, "is_group": False})
        )
        t1 = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Ticket A",
                    "description": "desc",
                    "partner_id": registrant.id,
                    "registrant_id": registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        t2 = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Ticket B",
                    "description": "desc",
                    "partner_id": registrant.id,
                    "registrant_id": registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        # Force recompute so the stored field reflects the new sibling
        (t1 | t2)._compute_repeat_count()

        self.assertEqual(t1.repeat_count, 1)
        self.assertTrue(t1.is_repeat)
        self.assertEqual(t2.repeat_count, 1)
        self.assertTrue(t2.is_repeat)

    def test_is_repeat_true_when_repeat_count_positive(self):
        """is_repeat mirrors whether repeat_count > 0."""
        registrant = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Repeat Check Individual", "is_registrant": True, "is_group": False})
        )
        first = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "First",
                    "description": "desc",
                    "partner_id": registrant.id,
                    "registrant_id": registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        second = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Second",
                    "description": "desc",
                    "partner_id": registrant.id,
                    "registrant_id": registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        (first | second)._compute_repeat_count()
        self.assertTrue(second.is_repeat)

    # ------------------------------------------------------------------ #
    # _compute_previous_tickets — no registrant branch                    #
    # ------------------------------------------------------------------ #

    def test_previous_tickets_empty_when_no_registrant(self):
        """previous_ticket_ids is empty when there is no registrant."""
        self.base_ticket._compute_previous_tickets()
        self.assertFalse(self.base_ticket.previous_ticket_ids)

    # ------------------------------------------------------------------ #
    # _compute_previous_tickets — with registrant                         #
    # ------------------------------------------------------------------ #

    def test_previous_tickets_populated_for_same_registrant(self):
        """previous_ticket_ids contains sibling tickets for the same registrant."""
        registrant = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Prev Ticket Individual", "is_registrant": True, "is_group": False})
        )
        t1 = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Earlier Ticket",
                    "description": "desc",
                    "partner_id": registrant.id,
                    "registrant_id": registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        t2 = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Later Ticket",
                    "description": "desc",
                    "partner_id": registrant.id,
                    "registrant_id": registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        (t1 | t2)._compute_previous_tickets()
        self.assertIn(t1, t2.previous_ticket_ids)
        self.assertIn(t2, t1.previous_ticket_ids)

    def test_previous_tickets_excludes_different_registrant(self):
        """previous_ticket_ids does not include tickets from a different registrant."""
        reg_a = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Registrant A", "is_registrant": True, "is_group": False})
        )
        reg_b = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Registrant B", "is_registrant": True, "is_group": False})
        )
        ticket_a = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Ticket for A",
                    "description": "desc",
                    "partner_id": reg_a.id,
                    "registrant_id": reg_a.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        ticket_b = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Ticket for B",
                    "description": "desc",
                    "partner_id": reg_b.id,
                    "registrant_id": reg_b.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        ticket_a._compute_previous_tickets()
        self.assertNotIn(ticket_b, ticket_a.previous_ticket_ids)

    # ------------------------------------------------------------------ #
    # _onchange_registrant_id                                             #
    # ------------------------------------------------------------------ #

    def test_onchange_registrant_sets_partner_id(self):
        """Changing registrant_id auto-fills partner_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Onchange Ticket",
                "description": "desc",
                "partner_id": False,
                "stage_id": self.stage_open.id,
                "registrant_id": self.individual.id,
            }
        )
        ticket._onchange_registrant_id()
        self.assertEqual(ticket.partner_id, self.individual)

    def test_onchange_registrant_no_op_when_no_registrant(self):
        """_onchange_registrant_id with no registrant leaves partner_id untouched."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "No Reg Ticket",
                "description": "desc",
                "partner_id": self.individual.id,
                "stage_id": self.stage_open.id,
                "registrant_id": False,
            }
        )
        ticket._onchange_registrant_id()
        # partner_id should be unchanged since registrant_id is False
        self.assertEqual(ticket.partner_id, self.individual)

    def test_onchange_registrant_fills_area_when_available(self):
        """When registrant has area_id, _onchange_registrant_id copies it."""
        # Only run this test if spp_area is installed (area_id field exists)
        if not hasattr(self.individual, "area_id"):
            self.skipTest("spp_area not installed — area_id not available")

        area = self.env["spp.area"].create({"draft_name": "Test Area"})
        self.individual.area_id = area

        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Area Ticket",
                "description": "desc",
                "partner_id": False,
                "stage_id": self.stage_open.id,
                "registrant_id": self.individual.id,
            }
        )
        ticket._onchange_registrant_id()
        self.assertEqual(ticket.area_id, area)

    # ------------------------------------------------------------------ #
    # _onchange_household_id                                              #
    # ------------------------------------------------------------------ #

    def test_onchange_household_clears_registrant(self):
        """Changing household_id clears registrant_id."""
        ticket = self.env["spp.grm.ticket"].new(
            {
                "name": "Household Onchange",
                "description": "desc",
                "partner_id": self.individual.id,
                "stage_id": self.stage_open.id,
                "registrant_id": self.individual.id,
                "household_id": self.household.id,
            }
        )
        ticket._onchange_household_id()
        self.assertFalse(ticket.registrant_id)

    # ------------------------------------------------------------------ #
    # action_view_previous_tickets                                        #
    # ------------------------------------------------------------------ #

    def test_action_view_previous_tickets_returns_act_window(self):
        """action_view_previous_tickets returns a valid act_window action."""
        registrant = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Action View Individual", "is_registrant": True, "is_group": False})
        )
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Action Ticket",
                    "description": "desc",
                    "partner_id": registrant.id,
                    "registrant_id": registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        action = ticket.action_view_previous_tickets()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.grm.ticket")
        self.assertIn("list", action["view_mode"])
        self.assertIn("form", action["view_mode"])

    def test_action_view_previous_tickets_domain_uses_previous_ids(self):
        """The domain in the action matches previous_ticket_ids."""
        registrant = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Domain Check Individual", "is_registrant": True, "is_group": False})
        )
        t1 = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Domain T1",
                    "description": "desc",
                    "partner_id": registrant.id,
                    "registrant_id": registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        t2 = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Domain T2",
                    "description": "desc",
                    "partner_id": registrant.id,
                    "registrant_id": registrant.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        (t1 | t2)._compute_previous_tickets()
        action = t2.action_view_previous_tickets()
        domain = action["domain"]
        # domain is [("id", "in", [...])]
        self.assertEqual(domain[0][0], "id")
        self.assertEqual(domain[0][1], "in")
        self.assertIn(t1.id, domain[0][2])

    # ------------------------------------------------------------------ #
    # household_id field storage                                          #
    # ------------------------------------------------------------------ #

    def test_ticket_stores_household_id(self):
        """A ticket can be linked to a household registrant."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Household Ticket",
                    "description": "desc",
                    "partner_id": self.individual.id,
                    "household_id": self.household.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        self.assertEqual(ticket.household_id, self.household)

    def test_ticket_stores_registrant_id(self):
        """A ticket can be linked to an individual registrant."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Registrant Ticket",
                    "description": "desc",
                    "partner_id": self.individual.id,
                    "registrant_id": self.individual.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        self.assertEqual(ticket.registrant_id, self.individual)
