# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for spp.session case integration (session.py extension)."""

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSessionCaseIntegration(TransactionCase):
    """Test the spp.session case-related fields and methods."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data."""
        super().setUpClass()

        # Case worker (also acts as facilitator)
        cls.facilitator = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Facilitator User",
                    "login": "facilitator_user",
                    "email": "facilitator@test.com",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                    ],
                }
            )
        )

        # Partner for the case client
        cls.client = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Case Client",
                    "email": "case_client@test.com",
                }
            )
        )

        # Case type
        cls.case_type = (
            cls.env["spp.case.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session Link Type",
                    "code": "SLT001",
                    "domain": "social_protection",
                }
            )
        )

        # Session type
        cls.session_type = (
            cls.env["spp.session.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Community Session",
                    "code": "CS001",
                }
            )
        )

        # Base session (no cases linked initially)
        cls.session = (
            cls.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Base Test Session",
                    "session_type_id": cls.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": cls.facilitator.id,
                }
            )
        )

        # Cases
        cls.case1 = (
            cls.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.client.id,
                    "case_worker_id": cls.facilitator.id,
                    "presenting_issue": "<p>Case 1</p>",
                }
            )
        )

        cls.case2 = (
            cls.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.client.id,
                    "case_worker_id": cls.facilitator.id,
                    "presenting_issue": "<p>Case 2</p>",
                }
            )
        )

    # -------------------------------------------------------------------------
    # case_ids Many2many field
    # -------------------------------------------------------------------------

    def test_case_ids_field_exists_and_writable(self):
        """The case_ids M2M field can be written and read back correctly."""
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Linked Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                    "case_ids": [
                        Command.link(self.case1.id),
                        Command.link(self.case2.id),
                    ],
                }
            )
        )

        self.assertIn(self.case1, session.case_ids, "case1 should be linked to session")
        self.assertIn(self.case2, session.case_ids, "case2 should be linked to session")

    def test_bidirectional_link_case_to_session(self):
        """Linking a session to a case also makes the case appear on the session."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.facilitator.id,
                    "presenting_issue": "<p>Bidirectional test</p>",
                    "session_ids": [Command.link(self.session.id)],
                }
            )
        )

        # The M2M relation is shared (case_session_rel), so the session
        # must also see the case through case_ids
        self.assertIn(
            case,
            self.session.case_ids,
            "Linking session from case should also appear on session.case_ids",
        )

    # -------------------------------------------------------------------------
    # _compute_case_count
    # -------------------------------------------------------------------------

    def test_case_count_is_zero_with_no_cases(self):
        """case_count is 0 when no cases are linked."""
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Empty Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                }
            )
        )
        session._compute_case_count()

        self.assertEqual(session.case_count, 0, "case_count should be 0 with no linked cases")

    def test_case_count_reflects_linked_cases(self):
        """case_count matches the number of cases linked to the session."""
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Two Case Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                    "case_ids": [
                        Command.link(self.case1.id),
                        Command.link(self.case2.id),
                    ],
                }
            )
        )
        session._compute_case_count()

        self.assertEqual(session.case_count, 2, "case_count should be 2 with two linked cases")

    def test_case_count_single_case(self):
        """case_count is 1 when exactly one case is linked."""
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Single Case Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                    "case_ids": [Command.link(self.case1.id)],
                }
            )
        )
        session._compute_case_count()

        self.assertEqual(session.case_count, 1)

    def test_case_count_updates_after_unlinking(self):
        """case_count decreases when a case is unlinked."""
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Unlink Test Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                    "case_ids": [
                        Command.link(self.case1.id),
                        Command.link(self.case2.id),
                    ],
                }
            )
        )

        # Unlink one case
        session.write({"case_ids": [Command.unlink(self.case2.id)]})
        session._compute_case_count()

        self.assertEqual(session.case_count, 1, "case_count should decrease after unlinking")

    # -------------------------------------------------------------------------
    # action_view_cases
    # -------------------------------------------------------------------------

    def test_action_view_cases_returns_correct_structure(self):
        """action_view_cases returns a valid act_window action dict."""
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Action View Cases Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                    "case_ids": [Command.link(self.case1.id)],
                }
            )
        )

        action = session.action_view_cases()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.case")
        self.assertIn("list", action["view_mode"])
        self.assertIn("form", action["view_mode"])

    def test_action_view_cases_name(self):
        """action_view_cases action name is 'Related Cases'."""
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Name Test Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                }
            )
        )

        action = session.action_view_cases()

        self.assertEqual(action["name"], "Related Cases")

    def test_action_view_cases_domain_contains_case_ids(self):
        """The action domain restricts to cases linked to this session."""
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Domain Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                    "case_ids": [
                        Command.link(self.case1.id),
                        Command.link(self.case2.id),
                    ],
                }
            )
        )

        action = session.action_view_cases()
        domain = action.get("domain", [])

        self.assertTrue(
            any(
                len(clause) == 3
                and clause[0] == "id"
                and clause[1] == "in"
                and set(clause[2]) == {self.case1.id, self.case2.id}
                for clause in domain
            ),
            "Domain should filter cases by linked IDs",
        )

    def test_action_view_cases_domain_empty_when_no_cases(self):
        """Domain is [("id", "in", [])] when no cases are linked."""
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "No Cases Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                }
            )
        )

        action = session.action_view_cases()
        domain = action.get("domain", [])

        self.assertTrue(
            any(len(clause) == 3 and clause[0] == "id" and clause[1] == "in" and clause[2] == [] for clause in domain),
            "Domain should have empty id list when no cases are linked",
        )

    # -------------------------------------------------------------------------
    # Many2many relation consistency
    # -------------------------------------------------------------------------

    def test_m2m_uses_shared_relation_table(self):
        """Verify the M2M relation is consistent across both sides of the link."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.facilitator.id,
                    "presenting_issue": "<p>Relation test</p>",
                }
            )
        )
        session = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Relation Test Session",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                }
            )
        )

        # Link via the session side
        session.write({"case_ids": [Command.link(case.id)]})

        # Both sides should reflect the link
        self.assertIn(case, session.case_ids)
        self.assertIn(session, case.session_ids)

    def test_multiple_sessions_on_case_and_multiple_cases_on_session(self):
        """A case can have multiple sessions; a session can have multiple cases."""
        session_a = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session A",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                }
            )
        )
        session_b = (
            self.env["spp.session"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Session B",
                    "session_type_id": self.session_type.id,
                    "date": fields.Date.today(),
                    "facilitator_id": self.facilitator.id,
                }
            )
        )

        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.facilitator.id,
                    "presenting_issue": "<p>Multi-session case</p>",
                    "session_ids": [
                        Command.link(session_a.id),
                        Command.link(session_b.id),
                    ],
                }
            )
        )

        self.assertEqual(len(case.session_ids), 2)

        # Both sessions should see the case
        self.assertIn(case, session_a.case_ids)
        self.assertIn(case, session_b.case_ids)

        # Verify case counts
        session_a._compute_case_count()
        session_b._compute_case_count()
        self.assertEqual(session_a.case_count, 1)
        self.assertEqual(session_b.case_count, 1)
