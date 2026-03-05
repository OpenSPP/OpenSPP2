"""Tests for Case extensions added by spp_grm_case_link."""

from psycopg2 import IntegrityError

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseGRMLink(TransactionCase):
    """Test the fields and methods added to spp.case by spp_grm_case_link."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Case worker user
        cls.case_worker = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Case Worker CGL",
                    "login": "test_case_worker_cgl",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                    ],
                }
            )
        )

        # GRM officer user (also used as ticket assignee)
        cls.grm_officer = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "GRM Officer CGL",
                    "login": "test_grm_officer_cgl",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_grm.group_grm_officer").id),
                    ],
                }
            )
        )

        # Partner / registrant
        cls.registrant = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Registrant CGL",
                    "is_registrant": True,
                    "email": "registrant_cgl@test.com",
                }
            )
        )

        # GRM ticket stage
        cls.ticket_stage = (
            cls.env["spp.grm.ticket.stage"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "New CGL",
                    "stage_type": "new",
                    "is_closed": False,
                    "sequence": 2,
                }
            )
        )

        # Case type
        cls.case_type = (
            cls.env["spp.case.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Social Protection CGL",
                    "code": "SP-CGL-001",
                    "domain": "social_protection",
                    "default_intensity": "2",
                }
            )
        )

        # GRM ticket to use as source
        cls.source_ticket = (
            cls.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Source Ticket CGL",
                    "description": "Source ticket for case tests",
                    "partner_id": cls.registrant.id,
                    "stage_id": cls.ticket_stage.id,
                    "user_id": cls.grm_officer.id,
                }
            )
        )

        # A base case (without source ticket)
        cls.case = (
            cls.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.registrant.id,
                    "case_worker_id": cls.case_worker.id,
                    "presenting_issue": "<p>Presenting issue CGL</p>",
                }
            )
        )

    # -------------------------------------------------------------------------
    # Tests for grm_ticket_count computed field
    # -------------------------------------------------------------------------

    def test_grm_ticket_count_no_tickets(self):
        """A case with no linked tickets should have grm_ticket_count of 0."""
        self.case._compute_grm_ticket_count()
        self.assertEqual(self.case.grm_ticket_count, 0, "grm_ticket_count should be 0 with no tickets")

    def test_grm_ticket_count_one_ticket(self):
        """A case with one linked ticket should have grm_ticket_count of 1."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>One ticket case</p>",
                }
            )
        )
        self.env["spp.grm.ticket"].with_context(tracking_disable=True).create(
            {
                "name": "Linked Ticket CGL",
                "description": "Description for linked ticket",
                "partner_id": self.registrant.id,
                "stage_id": self.ticket_stage.id,
                "case_id": case.id,
            }
        )
        case._compute_grm_ticket_count()
        self.assertEqual(case.grm_ticket_count, 1, "grm_ticket_count should be 1 with one ticket")

    def test_grm_ticket_count_multiple_tickets(self):
        """A case with multiple linked tickets should have the correct count."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Multi ticket case</p>",
                }
            )
        )
        for i in range(3):
            self.env["spp.grm.ticket"].with_context(tracking_disable=True).create(
                {
                    "name": f"Multi Ticket {i} CGL",
                    "description": f"Description {i}",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                    "case_id": case.id,
                }
            )
        case._compute_grm_ticket_count()
        self.assertEqual(case.grm_ticket_count, 3, "grm_ticket_count should be 3 with three tickets")

    # -------------------------------------------------------------------------
    # Tests for source_grm_ticket_id field
    # -------------------------------------------------------------------------

    def test_source_grm_ticket_id_field(self):
        """source_grm_ticket_id should be settable and readable on a case."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Source ticket field test</p>",
                    "source_grm_ticket_id": self.source_ticket.id,
                }
            )
        )
        self.assertEqual(
            case.source_grm_ticket_id,
            self.source_ticket,
            "source_grm_ticket_id should reference the source ticket",
        )

    def test_source_grm_ticket_id_optional(self):
        """source_grm_ticket_id should not be required; a case can exist without it."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>No source ticket</p>",
                }
            )
        )
        self.assertFalse(case.source_grm_ticket_id, "source_grm_ticket_id should be False when not set")

    def test_source_grm_ticket_id_ondelete_restrict(self):
        """Deleting a GRM ticket used as source for a case should raise (ondelete=restrict)."""
        new_ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Restricted Source Ticket CGL",
                    "description": "Source ticket to test ondelete restrict",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                }
            )
        )
        self.env["spp.case"].with_context(tracking_disable=True).create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.registrant.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Source restrict test</p>",
                "source_grm_ticket_id": new_ticket.id,
            }
        )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            new_ticket.unlink()

    # -------------------------------------------------------------------------
    # Tests for grm_ticket_ids One2many
    # -------------------------------------------------------------------------

    def test_grm_ticket_ids_reflects_linked_tickets(self):
        """grm_ticket_ids should contain all tickets that have case_id set to this case."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>O2M test case</p>",
                }
            )
        )
        ticket1 = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "O2M Ticket 1 CGL",
                    "description": "Ticket 1",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                    "case_id": case.id,
                }
            )
        )
        ticket2 = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "O2M Ticket 2 CGL",
                    "description": "Ticket 2",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                    "case_id": case.id,
                }
            )
        )
        self.assertIn(ticket1, case.grm_ticket_ids, "Ticket 1 should be in grm_ticket_ids")
        self.assertIn(ticket2, case.grm_ticket_ids, "Ticket 2 should be in grm_ticket_ids")

    # -------------------------------------------------------------------------
    # Tests for action_create_grm_ticket
    # -------------------------------------------------------------------------

    def test_action_create_grm_ticket_returns_action(self):
        """action_create_grm_ticket should return a window action."""
        action = self.case.action_create_grm_ticket()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.grm.ticket")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "new")

    def test_action_create_grm_ticket_sets_default_partner(self):
        """action_create_grm_ticket should pre-fill partner_id in context."""
        action = self.case.action_create_grm_ticket()

        self.assertIn("context", action)
        self.assertEqual(
            action["context"]["default_partner_id"],
            self.case.partner_id.id,
            "default_partner_id should match the case partner",
        )

    def test_action_create_grm_ticket_sets_default_case(self):
        """action_create_grm_ticket should pre-fill case_id in context."""
        action = self.case.action_create_grm_ticket()

        self.assertEqual(
            action["context"]["default_case_id"],
            self.case.id,
            "default_case_id should reference the current case",
        )

    def test_action_create_grm_ticket_sets_default_name(self):
        """action_create_grm_ticket should pre-fill the default ticket name."""
        action = self.case.action_create_grm_ticket()

        self.assertIn("default_name", action["context"])
        self.assertIn(self.case.name, action["context"]["default_name"])

    def test_action_create_grm_ticket_sets_default_description(self):
        """action_create_grm_ticket should pre-fill the default description."""
        action = self.case.action_create_grm_ticket()

        self.assertIn("default_description", action["context"])
        self.assertIn(self.case.name, action["context"]["default_description"])
        self.assertIn(self.case.case_type_id.name, action["context"]["default_description"])

    def test_action_create_grm_ticket_name(self):
        """action_create_grm_ticket action should have the correct name."""
        action = self.case.action_create_grm_ticket()
        self.assertEqual(action["name"], "Create GRM Ticket")

    # -------------------------------------------------------------------------
    # Tests for action_view_grm_tickets
    # -------------------------------------------------------------------------

    def test_action_view_grm_tickets_no_tickets(self):
        """action_view_grm_tickets with no tickets returns a list/form action."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>No tickets case</p>",
                }
            )
        )

        action = case.action_view_grm_tickets()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.grm.ticket")
        # With zero tickets, falls through to tree+form
        self.assertIn("tree", action["view_mode"])
        self.assertEqual(action["domain"], [("case_id", "=", case.id)])

    def test_action_view_grm_tickets_one_ticket_opens_form(self):
        """action_view_grm_tickets with exactly one ticket opens form view directly."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Single ticket case</p>",
                }
            )
        )
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Single Ticket CGL",
                    "description": "Single ticket",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                    "case_id": case.id,
                }
            )
        )
        # Recompute count
        case._compute_grm_ticket_count()

        action = case.action_view_grm_tickets()
        self.assertEqual(action["view_mode"], "form", "Single ticket should open form view")
        self.assertEqual(action["res_id"], ticket.id, "Should open the single ticket record")

    def test_action_view_grm_tickets_multiple_tickets_opens_list(self):
        """action_view_grm_tickets with multiple tickets opens tree+form view."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Multiple ticket case</p>",
                }
            )
        )
        for i in range(2):
            self.env["spp.grm.ticket"].with_context(tracking_disable=True).create(
                {
                    "name": f"Multi Ticket {i} CGL2",
                    "description": f"Description {i}",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                    "case_id": case.id,
                }
            )
        # Recompute count
        case._compute_grm_ticket_count()

        action = case.action_view_grm_tickets()
        self.assertIn("tree", action["view_mode"], "Multiple tickets should open tree view")

    def test_action_view_grm_tickets_sets_domain(self):
        """action_view_grm_tickets domain should filter on current case."""
        action = self.case.action_view_grm_tickets()
        self.assertEqual(
            action["domain"],
            [("case_id", "=", self.case.id)],
            "Domain should filter tickets by case_id",
        )

    def test_action_view_grm_tickets_sets_context(self):
        """action_view_grm_tickets should pass default_case_id and default_partner_id."""
        action = self.case.action_view_grm_tickets()
        self.assertEqual(action["context"]["default_case_id"], self.case.id)
        self.assertEqual(action["context"]["default_partner_id"], self.case.partner_id.id)

    def test_action_view_grm_tickets_name(self):
        """action_view_grm_tickets action should have the correct name."""
        action = self.case.action_view_grm_tickets()
        self.assertEqual(action["name"], "Related GRM Tickets")
