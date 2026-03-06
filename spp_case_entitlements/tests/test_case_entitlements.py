"""Tests for CaseEntitlements model in spp_case_entitlements."""

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseEntitlements(TransactionCase):
    """Test the CaseEntitlements extension of spp.case."""

    @classmethod
    def setUpClass(cls):
        """Set up test data shared across all test methods."""
        super().setUpClass()

        # Create test case worker user
        cls.case_worker = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "CE Test Case Worker",
                    "login": "ce_test_worker",
                    "email": "ce_worker@test.com",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                    ],
                }
            )
        )

        # Create test partner (client) — not a registrant so no domain restriction
        cls.client = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "CE Test Client",
                    "email": "ce_client@test.com",
                }
            )
        )

        # Create registrant partner for entitlements (must have is_registrant=True)
        cls.registrant = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "CE Test Registrant",
                    "email": "ce_registrant@test.com",
                    "is_registrant": True,
                }
            )
        )

        # Create a second registrant for isolation tests
        cls.registrant2 = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "CE Test Registrant 2",
                    "email": "ce_registrant2@test.com",
                    "is_registrant": True,
                }
            )
        )

        # Create case type
        cls.case_type = (
            cls.env["spp.case.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "CE Social Protection",
                    "code": "CESP001",
                    "domain": "social_protection",
                    "default_intensity": "2",
                }
            )
        )

        # Create case stage (non-closed)
        cls.stage_intake = (
            cls.env["spp.case.stage"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "CE Intake",
                    "sequence": 1,
                    "phase": "intake",
                    "is_closed": False,
                }
            )
        )

        # Create a closed stage (needed for action_close_case)
        cls.stage_closed = (
            cls.env["spp.case.stage"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "CE Closed",
                    "sequence": 99,
                    "phase": "closure",
                    "is_closed": True,
                }
            )
        )

        # Create an spp.program (needed for spp.cycle which is needed for spp.entitlement)
        cls.program = (
            cls.env["spp.program"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "CE Test Program",
                }
            )
        )

        # Create an spp.cycle linked to the program
        cls.cycle = (
            cls.env["spp.cycle"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "CE Test Cycle",
                    "program_id": cls.program.id,
                    "start_date": fields.Date.today(),
                    "end_date": fields.Date.today(),
                }
            )
        )

        # Create test case linked to the registrant (so entitlements can be matched by partner)
        cls.case = (
            cls.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.registrant.id,
                    "case_worker_id": cls.case_worker.id,
                    "stage_id": cls.stage_intake.id,
                    "presenting_issue": "<p>CE test presenting issue</p>",
                }
            )
        )

        # Create approved entitlement for registrant
        cls.entitlement_approved = (
            cls.env["spp.entitlement"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": cls.registrant.id,
                    "cycle_id": cls.cycle.id,
                    "initial_amount": 500.0,
                    "state": "approved",
                    "is_cash_entitlement": True,
                }
            )
        )

        # Create pending entitlement for registrant
        cls.entitlement_pending = (
            cls.env["spp.entitlement"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": cls.registrant.id,
                    "cycle_id": cls.cycle.id,
                    "initial_amount": 300.0,
                    "state": "pending_validation",
                    "is_cash_entitlement": True,
                }
            )
        )

        # Create draft entitlement for registrant
        cls.entitlement_draft = (
            cls.env["spp.entitlement"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": cls.registrant.id,
                    "cycle_id": cls.cycle.id,
                    "initial_amount": 200.0,
                    "state": "draft",
                    "is_cash_entitlement": True,
                }
            )
        )

    # ------------------------------------------------------------------
    # Computed field: _compute_entitlement_info
    # ------------------------------------------------------------------

    def test_entitlement_count_with_no_entitlements(self):
        """A case with no entitlements should have count = 0 and has_entitlements = False."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "stage_id": self.stage_intake.id,
                    "presenting_issue": "<p>Empty entitlements case</p>",
                }
            )
        )
        case._compute_entitlement_info()

        self.assertEqual(case.entitlement_count, 0, "Empty case should have entitlement_count 0")
        self.assertFalse(case.has_entitlements, "Empty case should have has_entitlements False")
        self.assertEqual(case.approved_entitlement_count, 0)
        self.assertEqual(case.pending_entitlement_count, 0)
        self.assertEqual(case.total_entitlement_amount, 0.0)

    def test_entitlement_count_with_entitlements(self):
        """A case with linked entitlements should reflect the correct counts."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                    Command.link(self.entitlement_draft.id),
                ]
            }
        )
        self.case._compute_entitlement_info()

        self.assertEqual(self.case.entitlement_count, 3, "Should have 3 entitlements")
        self.assertTrue(self.case.has_entitlements, "has_entitlements should be True")

    def test_approved_entitlement_count(self):
        """approved_entitlement_count counts only entitlements with state 'approved'."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                    Command.link(self.entitlement_draft.id),
                ]
            }
        )
        self.case._compute_entitlement_info()

        self.assertEqual(self.case.approved_entitlement_count, 1)

    def test_pending_entitlement_count(self):
        """pending_entitlement_count counts only entitlements with state 'pending_validation'."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                    Command.link(self.entitlement_draft.id),
                ]
            }
        )
        self.case._compute_entitlement_info()

        self.assertEqual(self.case.pending_entitlement_count, 1)

    def test_total_entitlement_amount_only_approved(self):
        """total_entitlement_amount sums only approved entitlement initial_amount values."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                    Command.link(self.entitlement_draft.id),
                ]
            }
        )
        self.case._compute_entitlement_info()

        # Only the approved entitlement's amount (500.0) should be summed
        self.assertEqual(
            self.case.total_entitlement_amount,
            500.0,
            "Total amount should sum only approved entitlements",
        )

    def test_total_entitlement_amount_multiple_approved(self):
        """total_entitlement_amount sums all approved entitlements when more than one."""
        second_approved = (
            self.env["spp.entitlement"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.registrant.id,
                    "cycle_id": self.cycle.id,
                    "initial_amount": 250.0,
                    "state": "approved",
                    "is_cash_entitlement": True,
                }
            )
        )
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(second_approved.id),
                ]
            }
        )
        self.case._compute_entitlement_info()

        self.assertEqual(
            self.case.total_entitlement_amount,
            750.0,
            "Total amount should be sum of both approved entitlements",
        )

    def test_has_entitlements_true(self):
        """has_entitlements is True when entitlement_ids is non-empty."""
        self.case.write({"entitlement_ids": [Command.link(self.entitlement_approved.id)]})
        self.case._compute_entitlement_info()
        self.assertTrue(self.case.has_entitlements)

    # ------------------------------------------------------------------
    # Onchange: _onchange_partner_entitlements
    # ------------------------------------------------------------------

    def test_onchange_partner_loads_entitlements(self):
        """Setting partner_id via onchange loads all partner entitlements."""
        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "stage_id": self.stage_intake.id,
                "presenting_issue": "<p>Onchange test</p>",
            }
        )

        # Trigger the onchange by setting partner_id
        case.partner_id = self.registrant
        case._onchange_partner_entitlements()

        expected_ids = set(self.env["spp.entitlement"].search([("partner_id", "=", self.registrant.id)]).ids)
        actual_ids = set(case.entitlement_ids.ids)
        self.assertEqual(
            actual_ids,
            expected_ids,
            "Onchange should load all entitlements for the selected partner",
        )

    def test_onchange_partner_clears_entitlements_when_none(self):
        """Clearing partner_id via onchange should clear entitlement_ids."""
        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.registrant.id,
                "case_worker_id": self.case_worker.id,
                "stage_id": self.stage_intake.id,
                "presenting_issue": "<p>Onchange clear test</p>",
            }
        )

        # Clear partner then trigger onchange
        case.partner_id = False
        case._onchange_partner_entitlements()

        self.assertFalse(
            case.entitlement_ids,
            "Entitlements should be cleared when partner is removed",
        )

    def test_onchange_partner_no_entitlements_for_partner(self):
        """Onchange when partner has no entitlements results in empty entitlement_ids."""
        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "stage_id": self.stage_intake.id,
                "presenting_issue": "<p>No entitlements partner test</p>",
            }
        )

        # registrant2 has no entitlements created in setUpClass
        case.partner_id = self.registrant2
        case._onchange_partner_entitlements()

        self.assertFalse(
            case.entitlement_ids,
            "Entitlements should be empty for a partner with no entitlements",
        )

    # ------------------------------------------------------------------
    # Action: action_view_entitlements
    # ------------------------------------------------------------------

    def test_action_view_entitlements_returns_correct_action(self):
        """action_view_entitlements returns an act_window action for spp.entitlement."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                ]
            }
        )

        action = self.case.action_view_entitlements()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.entitlement")
        self.assertIn("list", action["view_mode"])
        self.assertIn("form", action["view_mode"])
        self.assertEqual(action["name"], "Entitlements")

    def test_action_view_entitlements_domain_contains_linked_ids(self):
        """action_view_entitlements domain limits to linked entitlement IDs."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                ]
            }
        )

        action = self.case.action_view_entitlements()
        domain_ids = action["domain"][0][2]

        self.assertIn(self.entitlement_approved.id, domain_ids)
        self.assertIn(self.entitlement_pending.id, domain_ids)
        self.assertNotIn(self.entitlement_draft.id, domain_ids)

    def test_action_view_entitlements_context_default_partner(self):
        """action_view_entitlements sets default_partner_id in context."""
        action = self.case.action_view_entitlements()

        self.assertEqual(
            action["context"]["default_partner_id"],
            self.case.partner_id.id,
            "Context should carry default_partner_id from the case",
        )

    def test_action_view_entitlements_context_create_false(self):
        """action_view_entitlements disables record creation from the window."""
        action = self.case.action_view_entitlements()

        self.assertFalse(
            action["context"].get("create"),
            "Context 'create' flag should be False",
        )

    def test_action_view_entitlements_ensure_one(self):
        """action_view_entitlements raises ValueError when called on an empty recordset."""
        empty = self.env["spp.case"].browse([])
        with self.assertRaises(ValueError):
            empty.action_view_entitlements()

    # ------------------------------------------------------------------
    # Action: action_view_approved_entitlements
    # ------------------------------------------------------------------

    def test_action_view_approved_entitlements_returns_correct_action(self):
        """action_view_approved_entitlements returns an act_window for spp.entitlement."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                    Command.link(self.entitlement_draft.id),
                ]
            }
        )

        action = self.case.action_view_approved_entitlements()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.entitlement")
        self.assertEqual(action["name"], "Approved Entitlements")

    def test_action_view_approved_entitlements_domain_approved_only(self):
        """action_view_approved_entitlements domain contains only approved IDs."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                    Command.link(self.entitlement_draft.id),
                ]
            }
        )

        action = self.case.action_view_approved_entitlements()
        domain_ids = action["domain"][0][2]

        self.assertIn(self.entitlement_approved.id, domain_ids)
        self.assertNotIn(self.entitlement_pending.id, domain_ids)
        self.assertNotIn(self.entitlement_draft.id, domain_ids)

    def test_action_view_approved_entitlements_context_create_false(self):
        """action_view_approved_entitlements disables record creation."""
        action = self.case.action_view_approved_entitlements()

        self.assertFalse(action["context"].get("create"))

    def test_action_view_approved_entitlements_context_default_partner(self):
        """action_view_approved_entitlements sets default_partner_id in context."""
        action = self.case.action_view_approved_entitlements()

        self.assertEqual(
            action["context"]["default_partner_id"],
            self.case.partner_id.id,
        )

    def test_action_view_approved_entitlements_ensure_one(self):
        """action_view_approved_entitlements raises ValueError on empty recordset."""
        empty = self.env["spp.case"].browse([])
        with self.assertRaises(ValueError):
            empty.action_view_approved_entitlements()

    def test_action_view_approved_entitlements_empty_when_none_approved(self):
        """action_view_approved_entitlements returns empty domain list when no approved."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "stage_id": self.stage_intake.id,
                    "presenting_issue": "<p>No approved entitlements</p>",
                }
            )
        )
        case.write({"entitlement_ids": [Command.link(self.entitlement_pending.id)]})

        action = case.action_view_approved_entitlements()
        domain_ids = action["domain"][0][2]

        self.assertEqual(domain_ids, [], "Domain IDs should be empty when no approved entitlements")

    # ------------------------------------------------------------------
    # Action: action_view_pending_entitlements
    # ------------------------------------------------------------------

    def test_action_view_pending_entitlements_returns_correct_action(self):
        """action_view_pending_entitlements returns an act_window for spp.entitlement."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                    Command.link(self.entitlement_draft.id),
                ]
            }
        )

        action = self.case.action_view_pending_entitlements()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.entitlement")
        self.assertEqual(action["name"], "Pending Entitlements")

    def test_action_view_pending_entitlements_domain_pending_only(self):
        """action_view_pending_entitlements domain contains only pending_validation IDs."""
        self.case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                    Command.link(self.entitlement_draft.id),
                ]
            }
        )

        action = self.case.action_view_pending_entitlements()
        domain_ids = action["domain"][0][2]

        self.assertIn(self.entitlement_pending.id, domain_ids)
        self.assertNotIn(self.entitlement_approved.id, domain_ids)
        self.assertNotIn(self.entitlement_draft.id, domain_ids)

    def test_action_view_pending_entitlements_context_create_false(self):
        """action_view_pending_entitlements disables record creation."""
        action = self.case.action_view_pending_entitlements()
        self.assertFalse(action["context"].get("create"))

    def test_action_view_pending_entitlements_context_default_partner(self):
        """action_view_pending_entitlements sets default_partner_id in context."""
        action = self.case.action_view_pending_entitlements()

        self.assertEqual(
            action["context"]["default_partner_id"],
            self.case.partner_id.id,
        )

    def test_action_view_pending_entitlements_ensure_one(self):
        """action_view_pending_entitlements raises ValueError on empty recordset."""
        empty = self.env["spp.case"].browse([])
        with self.assertRaises(ValueError):
            empty.action_view_pending_entitlements()

    def test_action_view_pending_entitlements_empty_when_none_pending(self):
        """action_view_pending_entitlements returns empty domain list when no pending."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "stage_id": self.stage_intake.id,
                    "presenting_issue": "<p>No pending entitlements</p>",
                }
            )
        )
        case.write({"entitlement_ids": [Command.link(self.entitlement_approved.id)]})

        action = case.action_view_pending_entitlements()
        domain_ids = action["domain"][0][2]

        self.assertEqual(domain_ids, [], "Domain IDs should be empty when no pending entitlements")

    # ------------------------------------------------------------------
    # currency_id default
    # ------------------------------------------------------------------

    def test_currency_id_defaults_to_company_currency(self):
        """currency_id should default to the company currency."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "stage_id": self.stage_intake.id,
                    "presenting_issue": "<p>Currency test</p>",
                }
            )
        )

        self.assertEqual(
            case.currency_id,
            self.env.company.currency_id,
            "currency_id should default to the active company currency",
        )

    # ------------------------------------------------------------------
    # Integration: linking entitlements and verifying computed fields
    # ------------------------------------------------------------------

    def test_linking_entitlements_updates_computed_fields(self):
        """Linking entitlements to a case triggers recompute of entitlement info fields."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "stage_id": self.stage_intake.id,
                    "presenting_issue": "<p>Integration test</p>",
                }
            )
        )

        # Initially no entitlements
        self.assertEqual(case.entitlement_count, 0)
        self.assertFalse(case.has_entitlements)

        # Link entitlements
        case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                ]
            }
        )

        self.assertEqual(case.entitlement_count, 2)
        self.assertTrue(case.has_entitlements)
        self.assertEqual(case.approved_entitlement_count, 1)
        self.assertEqual(case.pending_entitlement_count, 1)
        self.assertEqual(case.total_entitlement_amount, 500.0)

    def test_removing_entitlement_updates_counts(self):
        """Unlinking an entitlement from a case decrements the computed counts."""
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "stage_id": self.stage_intake.id,
                    "presenting_issue": "<p>Remove entitlement test</p>",
                }
            )
        )
        case.write(
            {
                "entitlement_ids": [
                    Command.link(self.entitlement_approved.id),
                    Command.link(self.entitlement_pending.id),
                ]
            }
        )
        self.assertEqual(case.entitlement_count, 2)

        # Now unlink one
        case.write({"entitlement_ids": [Command.unlink(self.entitlement_approved.id)]})

        self.assertEqual(case.entitlement_count, 1)
        self.assertEqual(case.approved_entitlement_count, 0)
        self.assertEqual(case.total_entitlement_amount, 0.0)

    def test_entitlement_state_change_updates_approved_count(self):
        """Changing an entitlement's state updates approved/pending counts on the case."""
        # Create a local entitlement in pending state
        ent = (
            self.env["spp.entitlement"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "partner_id": self.registrant.id,
                    "cycle_id": self.cycle.id,
                    "initial_amount": 100.0,
                    "state": "pending_validation",
                    "is_cash_entitlement": True,
                }
            )
        )
        case = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.registrant.id,
                    "case_worker_id": self.case_worker.id,
                    "stage_id": self.stage_intake.id,
                    "presenting_issue": "<p>State change test</p>",
                    "entitlement_ids": [Command.link(ent.id)],
                }
            )
        )

        self.assertEqual(case.pending_entitlement_count, 1)
        self.assertEqual(case.approved_entitlement_count, 0)

        # Approve the entitlement directly (bypass state machine for test isolation)
        ent.write({"state": "approved"})

        self.assertEqual(case.pending_entitlement_count, 0)
        self.assertEqual(case.approved_entitlement_count, 1)
        self.assertEqual(case.total_entitlement_amount, 100.0)

    def test_multiple_cases_share_entitlement(self):
        """The same entitlement can be linked to multiple cases (M2M relationship)."""
        case_a = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "stage_id": self.stage_intake.id,
                    "presenting_issue": "<p>Case A</p>",
                    "entitlement_ids": [Command.link(self.entitlement_approved.id)],
                }
            )
        )
        case_b = (
            self.env["spp.case"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": self.client.id,
                    "case_worker_id": self.case_worker.id,
                    "stage_id": self.stage_intake.id,
                    "presenting_issue": "<p>Case B</p>",
                    "entitlement_ids": [Command.link(self.entitlement_approved.id)],
                }
            )
        )

        self.assertIn(self.entitlement_approved, case_a.entitlement_ids)
        self.assertIn(self.entitlement_approved, case_b.entitlement_ids)
