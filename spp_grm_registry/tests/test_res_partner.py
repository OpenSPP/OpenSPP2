"""Tests for ResPartnerGRM — the spp_grm_registry extension of res.partner."""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestResPartnerGRMFields(TransactionCase):
    """Test computed counts and action methods added to res.partner by spp_grm_registry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.stage_open = (
            cls.env["spp.grm.ticket.stage"]
            .with_context(tracking_disable=True)
            .create({"name": "Open", "is_closed": False})
        )
        cls.stage_closed = (
            cls.env["spp.grm.ticket.stage"]
            .with_context(tracking_disable=True)
            .create({"name": "Closed", "is_closed": True})
        )

        # Individual registrant that will file tickets
        cls.registrant = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Registrant Partner",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
        )

        # Household (group) registrant
        cls.household = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Household Partner",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
        )

        # Create an open ticket where registrant is the filer
        cls.open_ticket = (
            cls.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Open Registrant Ticket",
                    "description": "desc",
                    "partner_id": cls.registrant.id,
                    "registrant_id": cls.registrant.id,
                    "stage_id": cls.stage_open.id,
                }
            )
        )

        # Create a closed ticket where registrant is the filer
        cls.closed_ticket = (
            cls.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Closed Registrant Ticket",
                    "description": "desc",
                    "partner_id": cls.registrant.id,
                    "registrant_id": cls.registrant.id,
                    "stage_id": cls.stage_closed.id,
                }
            )
        )

        # Create a ticket linked to the household
        cls.household_ticket = (
            cls.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Household Ticket",
                    "description": "desc",
                    "partner_id": cls.registrant.id,
                    "household_id": cls.household.id,
                    "stage_id": cls.stage_open.id,
                }
            )
        )

    # ------------------------------------------------------------------ #
    # _compute_grm_registrant_tickets                                     #
    # ------------------------------------------------------------------ #

    def test_registrant_ticket_count_total(self):
        """grm_registrant_ticket_count equals total tickets filed by the registrant."""
        self.assertEqual(self.registrant.grm_registrant_ticket_count, 2)

    def test_registrant_open_count(self):
        """grm_registrant_open_count counts only non-closed tickets."""
        self.assertEqual(self.registrant.grm_registrant_open_count, 1)

    def test_registrant_ticket_count_zero_when_no_tickets(self):
        """A registrant with no tickets has counts at zero."""
        new_reg = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "No-Ticket Registrant", "is_registrant": True, "is_group": False})
        )
        self.assertEqual(new_reg.grm_registrant_ticket_count, 0)
        self.assertEqual(new_reg.grm_registrant_open_count, 0)

    def test_registrant_open_count_updates_when_ticket_closed(self):
        """grm_registrant_open_count decreases when a ticket is moved to a closed stage."""
        # Create an isolated registrant and ticket for this test
        reg = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Close Test Registrant", "is_registrant": True, "is_group": False})
        )
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Close Me Ticket",
                    "description": "desc",
                    "partner_id": reg.id,
                    "registrant_id": reg.id,
                    "stage_id": self.stage_open.id,
                }
            )
        )
        self.assertEqual(reg.grm_registrant_open_count, 1)

        ticket.with_context(tracking_disable=True).write({"stage_id": self.stage_closed.id})
        self.assertEqual(reg.grm_registrant_open_count, 0)

    # ------------------------------------------------------------------ #
    # _compute_grm_household_tickets                                      #
    # ------------------------------------------------------------------ #

    def test_household_ticket_count(self):
        """grm_household_ticket_count equals total tickets linked to this household."""
        self.assertEqual(self.household.grm_household_ticket_count, 1)

    def test_household_ticket_count_zero_when_no_tickets(self):
        """A household with no tickets has grm_household_ticket_count = 0."""
        new_hh = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Empty Household", "is_registrant": True, "is_group": True})
        )
        self.assertEqual(new_hh.grm_household_ticket_count, 0)

    def test_household_ticket_count_increments_with_additional_ticket(self):
        """Adding another ticket for the household increases the count."""
        hh = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Growing Household", "is_registrant": True, "is_group": True})
        )
        self.env["spp.grm.ticket"].with_context(tracking_disable=True).create(
            {
                "name": "HH Ticket 1",
                "description": "desc",
                "partner_id": self.registrant.id,
                "household_id": hh.id,
                "stage_id": self.stage_open.id,
            }
        )
        self.assertEqual(hh.grm_household_ticket_count, 1)

        self.env["spp.grm.ticket"].with_context(tracking_disable=True).create(
            {
                "name": "HH Ticket 2",
                "description": "desc",
                "partner_id": self.registrant.id,
                "household_id": hh.id,
                "stage_id": self.stage_open.id,
            }
        )
        self.assertEqual(hh.grm_household_ticket_count, 2)

    # ------------------------------------------------------------------ #
    # O2M back-references                                                 #
    # ------------------------------------------------------------------ #

    def test_grm_registrant_ticket_ids_contains_registrant_tickets(self):
        """grm_registrant_ticket_ids links back to tickets where registrant_id is this partner."""
        self.assertIn(self.open_ticket, self.registrant.grm_registrant_ticket_ids)
        self.assertIn(self.closed_ticket, self.registrant.grm_registrant_ticket_ids)

    def test_grm_household_ticket_ids_contains_household_tickets(self):
        """grm_household_ticket_ids links back to tickets where household_id is this partner."""
        self.assertIn(self.household_ticket, self.household.grm_household_ticket_ids)

    # ------------------------------------------------------------------ #
    # action_view_grm_registrant_tickets                                  #
    # ------------------------------------------------------------------ #

    def test_action_view_registrant_tickets_type(self):
        """action_view_grm_registrant_tickets returns an act_window action."""
        action = self.registrant.action_view_grm_registrant_tickets()
        self.assertEqual(action["type"], "ir.actions.act_window")

    def test_action_view_registrant_tickets_model(self):
        """action_view_grm_registrant_tickets targets spp.grm.ticket."""
        action = self.registrant.action_view_grm_registrant_tickets()
        self.assertEqual(action["res_model"], "spp.grm.ticket")

    def test_action_view_registrant_tickets_domain(self):
        """action_view_grm_registrant_tickets domain filters by registrant_id."""
        action = self.registrant.action_view_grm_registrant_tickets()
        self.assertEqual(action["domain"], [("registrant_id", "=", self.registrant.id)])

    def test_action_view_registrant_tickets_context(self):
        """action_view_grm_registrant_tickets sets default_registrant_id in context."""
        action = self.registrant.action_view_grm_registrant_tickets()
        self.assertEqual(action["context"]["default_registrant_id"], self.registrant.id)

    def test_action_view_registrant_tickets_view_mode(self):
        """action_view_grm_registrant_tickets exposes tree, form, and kanban views."""
        action = self.registrant.action_view_grm_registrant_tickets()
        for mode in ("tree", "form", "kanban"):
            self.assertIn(mode, action["view_mode"])

    # ------------------------------------------------------------------ #
    # action_view_grm_household_tickets                                   #
    # ------------------------------------------------------------------ #

    def test_action_view_household_tickets_type(self):
        """action_view_grm_household_tickets returns an act_window action."""
        action = self.household.action_view_grm_household_tickets()
        self.assertEqual(action["type"], "ir.actions.act_window")

    def test_action_view_household_tickets_model(self):
        """action_view_grm_household_tickets targets spp.grm.ticket."""
        action = self.household.action_view_grm_household_tickets()
        self.assertEqual(action["res_model"], "spp.grm.ticket")

    def test_action_view_household_tickets_domain(self):
        """action_view_grm_household_tickets domain filters by household_id."""
        action = self.household.action_view_grm_household_tickets()
        self.assertEqual(action["domain"], [("household_id", "=", self.household.id)])

    def test_action_view_household_tickets_context(self):
        """action_view_grm_household_tickets sets default_household_id in context."""
        action = self.household.action_view_grm_household_tickets()
        self.assertEqual(action["context"]["default_household_id"], self.household.id)

    def test_action_view_household_tickets_view_mode(self):
        """action_view_grm_household_tickets exposes tree, form, and kanban views."""
        action = self.household.action_view_grm_household_tickets()
        for mode in ("tree", "form", "kanban"):
            self.assertIn(mode, action["view_mode"])
