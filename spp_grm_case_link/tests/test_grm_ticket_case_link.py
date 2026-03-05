"""Tests for GRM ticket extensions added by spp_grm_case_link."""

from psycopg2 import IntegrityError

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGRMTicketCaseLink(TransactionCase):
    """Test the fields and methods added to spp.grm.ticket by spp_grm_case_link."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a GRM manager user
        cls.grm_manager = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "GRM Manager TGL",
                    "login": "test_grm_manager_tgl",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_grm.group_grm_manager").id),
                    ],
                }
            )
        )

        # Create a GRM officer user
        cls.grm_officer = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "GRM Officer TGL",
                    "login": "test_grm_officer_tgl",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_grm.group_grm_officer").id),
                    ],
                }
            )
        )

        # Create a partner (registrant) to attach to tickets
        cls.registrant = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Registrant TGL",
                    "is_registrant": True,
                    "email": "registrant_tgl@test.com",
                }
            )
        )

        # Create a stage for tickets
        cls.ticket_stage = (
            cls.env["spp.grm.ticket.stage"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "New TGL",
                    "stage_type": "new",
                    "is_closed": False,
                    "sequence": 1,
                }
            )
        )

        # Create a case type for cases created during tests
        cls.case_type = (
            cls.env["spp.case.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Social Protection TGL",
                    "code": "SP-TGL-001",
                    "domain": "social_protection",
                    "default_intensity": "2",
                }
            )
        )

        # Create a case worker user
        cls.case_worker = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Case Worker TGL",
                    "login": "test_case_worker_tgl",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                    ],
                }
            )
        )

        # Create a basic GRM ticket (without a linked case)
        cls.ticket = (
            cls.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Ticket TGL",
                    "description": "Test description for TGL",
                    "partner_id": cls.registrant.id,
                    "stage_id": cls.ticket_stage.id,
                    "user_id": cls.grm_officer.id,
                }
            )
        )

        # Create a case to link
        cls.case = (
            cls.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.registrant.id,
                    "case_worker_id": cls.case_worker.id,
                    "presenting_issue": "<p>Presenting issue for TGL tests</p>",
                }
            )
        )

    # -------------------------------------------------------------------------
    # Tests for case_count computed field
    # -------------------------------------------------------------------------

    def test_case_count_no_case(self):
        """Ticket without a linked case should have case_count of 0."""
        # The ticket created in setUpClass has no case_id
        self.ticket._compute_case_count()
        self.assertEqual(self.ticket.case_count, 0, "case_count should be 0 when no case is linked")

    def test_case_count_with_case(self):
        """Ticket with a linked case should have case_count of 1."""
        ticket_with_case = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Linked Ticket TGL",
                    "description": "Description for linked ticket",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                    "case_id": self.case.id,
                }
            )
        )
        ticket_with_case._compute_case_count()
        self.assertEqual(ticket_with_case.case_count, 1, "case_count should be 1 when a case is linked")

    def test_case_count_recomputes_when_case_changes(self):
        """case_count should update when case_id is set then cleared."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Dynamic Link Ticket TGL",
                    "description": "Dynamic link description",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                }
            )
        )

        # Initially no case
        ticket._compute_case_count()
        self.assertEqual(ticket.case_count, 0)

        # Link a case
        ticket.case_id = self.case.id
        ticket._compute_case_count()
        self.assertEqual(ticket.case_count, 1)

        # Remove the case
        ticket.case_id = False
        ticket._compute_case_count()
        self.assertEqual(ticket.case_count, 0)

    # -------------------------------------------------------------------------
    # Tests for action_escalate_to_case
    # -------------------------------------------------------------------------

    def test_action_escalate_to_case_returns_action(self):
        """action_escalate_to_case should return a window action opening the wizard."""
        action = self.ticket.action_escalate_to_case()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.grm.escalate.wizard")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "new")

    def test_action_escalate_to_case_sets_default_ticket(self):
        """action_escalate_to_case should pass the ticket id in context."""
        action = self.ticket.action_escalate_to_case()

        self.assertIn("context", action)
        self.assertEqual(action["context"]["default_ticket_id"], self.ticket.id)

    def test_action_escalate_to_case_name(self):
        """action_escalate_to_case should use the correct action name."""
        action = self.ticket.action_escalate_to_case()
        self.assertEqual(action["name"], "Escalate to Case")

    # -------------------------------------------------------------------------
    # Tests for action_view_case
    # -------------------------------------------------------------------------

    def test_action_view_case_no_case(self):
        """action_view_case returns an empty dict when no case is linked."""
        result = self.ticket.action_view_case()
        self.assertEqual(result, {}, "Should return empty dict when no case is linked")

    def test_action_view_case_with_case(self):
        """action_view_case returns a form action pointing to the linked case."""
        ticket_with_case = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "View Case Ticket TGL",
                    "description": "Ticket for action_view_case test",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                    "case_id": self.case.id,
                }
            )
        )

        action = ticket_with_case.action_view_case()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.case")
        self.assertEqual(action["res_id"], self.case.id)
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "current")

    def test_action_view_case_name(self):
        """action_view_case action should have the correct name."""
        ticket_with_case = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "View Case Name Ticket TGL",
                    "description": "Ticket for action_view_case name test",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                    "case_id": self.case.id,
                }
            )
        )

        action = ticket_with_case.action_view_case()
        self.assertEqual(action["name"], "Related Case")

    # -------------------------------------------------------------------------
    # Tests for new fields
    # -------------------------------------------------------------------------

    def test_case_id_field_set_and_read(self):
        """case_id field should be settable and readable on a ticket."""
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Field Test Ticket TGL",
                    "description": "Test field",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                }
            )
        )
        self.assertFalse(ticket.case_id, "case_id should be empty initially")

        ticket.case_id = self.case.id
        self.assertEqual(ticket.case_id, self.case, "case_id should be the linked case")

    def test_case_id_ondelete_restrict(self):
        """Deleting a case linked to a ticket should raise an error (ondelete=restrict)."""
        new_case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "presenting_issue": "<p>Case to be deleted</p>",
                }
            )
        )
        ticket = (
            self.env["spp.grm.ticket"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Restricted Delete Ticket TGL",
                    "description": "Testing ondelete restrict",
                    "partner_id": self.registrant.id,
                    "stage_id": self.ticket_stage.id,
                    "case_id": new_case.id,
                }
            )
        )
        # Attempting to delete a case that is linked to a ticket via ondelete=restrict
        # must raise an exception
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            new_case.unlink()

        # Verify ticket and case still exist
        self.assertTrue(ticket.exists(), "Ticket should still exist")
        self.assertTrue(new_case.exists(), "Case should still exist")
