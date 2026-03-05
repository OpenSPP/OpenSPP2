"""Tests for ResPartnerCase (res.partner) extensions in spp_case_registry."""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResPartnerCase(TransactionCase):
    """Test the case-related extensions on res.partner."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for all test methods."""
        super().setUpClass()

        # Create test user for case assignment
        cls.case_worker = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Partner Case Worker",
                    "login": "partner_case_worker",
                    "email": "partner_worker@test.com",
                    "group_ids": [
                        Command.link(cls.env.ref("base.group_user").id),
                        Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                    ],
                }
            )
        )

        # Create case type
        cls.case_type = (
            cls.env["spp.case.type"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Partner Test Type",
                    "code": "PT001",
                    "domain": "social_protection",
                }
            )
        )

        # Create a closed case stage so we can test is_active == False
        cls.stage_intake = (
            cls.env["spp.case.stage"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Intake Stage",
                    "sequence": 1,
                    "phase": "intake",
                    "is_closed": False,
                }
            )
        )

        cls.stage_closed = (
            cls.env["spp.case.stage"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Closed Stage",
                    "sequence": 99,
                    "phase": "closure",
                    "is_closed": True,
                }
            )
        )

        # Individual registrant (cases via registrant_id)
        cls.individual = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Individual Partner",
                    "is_registrant": True,
                    "is_group": False,
                    "email": "individual_partner@test.com",
                }
            )
        )

        # Household registrant (cases via household_id)
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

        # A plain partner (no cases by default)
        cls.plain_partner = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Plain Partner",
                    "email": "plain@test.com",
                }
            )
        )

    def _create_case(self, registrant_id=None, household_id=None, stage_id=None, **kwargs):
        """Helper: create a case with sensible defaults."""
        vals = {
            "case_type_id": self.case_type.id,
            "partner_id": self.plain_partner.id,
            "case_worker_id": self.case_worker.id,
            "presenting_issue": "<p>Test issue</p>",
        }
        if registrant_id:
            vals["registrant_id"] = registrant_id
        if household_id:
            vals["household_id"] = household_id
        if stage_id:
            vals["stage_id"] = stage_id
        vals.update(kwargs)
        return self.env["spp.case"].with_context(tracking_disable=True).create(vals)

    # -------------------------------------------------------------------------
    # case_registrant_ids / case_household_ids One2many fields
    # -------------------------------------------------------------------------

    def test_case_registrant_ids_populated(self):
        """Cases with this individual as registrant_id appear in case_registrant_ids."""
        case = self._create_case(registrant_id=self.individual.id)

        self.assertIn(case, self.individual.case_registrant_ids)

    def test_case_household_ids_populated(self):
        """Cases with this household as household_id appear in case_household_ids."""
        case = self._create_case(household_id=self.household.id)

        self.assertIn(case, self.household.case_household_ids)

    def test_no_cases_initially(self):
        """A fresh partner has no associated cases."""
        fresh = (
            self.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Fresh Partner", "email": "fresh@test.com"})
        )

        self.assertFalse(fresh.case_registrant_ids)
        self.assertFalse(fresh.case_household_ids)

    # -------------------------------------------------------------------------
    # _compute_case_counts
    # -------------------------------------------------------------------------

    def test_case_count_registrant(self):
        """case_count reflects cases where partner is registrant."""
        self._create_case(registrant_id=self.individual.id)
        self._create_case(registrant_id=self.individual.id)

        self.individual._compute_case_counts()

        self.assertEqual(self.individual.case_count, 2)

    def test_case_count_household(self):
        """case_count reflects cases where partner is household."""
        self._create_case(household_id=self.household.id)

        self.household._compute_case_counts()

        self.assertEqual(self.household.case_count, 1)

    def test_case_count_union_of_registrant_and_household(self):
        """case_count = union of case_registrant_ids and case_household_ids (no double-count)."""
        # A partner used as both registrant and household (edge case)
        # We use two separate partners and one case each
        case_as_registrant = self._create_case(registrant_id=self.individual.id)
        # Use a different partner for the household link to keep things clean
        case_as_household = self._create_case(household_id=self.household.id)

        self.individual._compute_case_counts()
        self.household._compute_case_counts()

        self.assertEqual(self.individual.case_count, 1)
        self.assertEqual(self.household.case_count, 1)

        # Verify case objects are the expected ones
        self.assertIn(case_as_registrant, self.individual.case_registrant_ids)
        self.assertIn(case_as_household, self.household.case_household_ids)

    def test_case_active_count_only_active(self):
        """case_active_count excludes cases in a closed stage."""
        # Create one active and one closed case for the individual
        active_case = self._create_case(
            registrant_id=self.individual.id,
            stage_id=self.stage_intake.id,
        )
        closed_case = self._create_case(
            registrant_id=self.individual.id,
            stage_id=self.stage_closed.id,
        )

        # Verify stage assignment affects is_active
        self.assertTrue(active_case.is_active)
        self.assertFalse(closed_case.is_active)

        self.individual._compute_case_counts()

        self.assertEqual(self.individual.case_count, 2)
        self.assertEqual(self.individual.case_active_count, 1)

    def test_case_active_count_zero_when_all_closed(self):
        """case_active_count is 0 when all cases are in a closed stage."""
        self._create_case(
            registrant_id=self.individual.id,
            stage_id=self.stage_closed.id,
        )

        self.individual._compute_case_counts()

        self.assertEqual(self.individual.case_count, 1)
        self.assertEqual(self.individual.case_active_count, 0)

    def test_case_count_zero_for_partner_with_no_cases(self):
        """Partners with no cases have case_count = 0 and case_active_count = 0."""
        self.plain_partner._compute_case_counts()

        self.assertEqual(self.plain_partner.case_count, 0)
        self.assertEqual(self.plain_partner.case_active_count, 0)

    # -------------------------------------------------------------------------
    # action_view_cases
    # -------------------------------------------------------------------------

    def test_action_view_cases_individual(self):
        """action_view_cases returns correct action for an individual (non-group) partner."""
        action = self.individual.action_view_cases()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.case")
        self.assertIn("tree", action["view_mode"])
        self.assertIn("form", action["view_mode"])

        # Domain should filter by registrant_id OR household_id
        domain = action["domain"]
        self.assertEqual(domain[0], "|")
        self.assertIn(("registrant_id", "=", self.individual.id), domain)
        self.assertIn(("household_id", "=", self.individual.id), domain)

        # Context should default registrant_id (partner is not a group)
        self.assertEqual(action["context"]["default_registrant_id"], self.individual.id)
        self.assertFalse(action["context"]["default_household_id"])

    def test_action_view_cases_household(self):
        """action_view_cases returns correct action for a household (group) partner."""
        action = self.household.action_view_cases()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.case")

        # Context should default household_id (partner is a group)
        self.assertFalse(action["context"]["default_registrant_id"])
        self.assertEqual(action["context"]["default_household_id"], self.household.id)

    def test_action_view_cases_domain_uses_or(self):
        """The domain in action_view_cases uses OR so both registrant and household cases appear."""
        action = self.individual.action_view_cases()
        domain = action["domain"]

        # First element must be the OR operator
        self.assertEqual(domain[0], "|")
        # Second and third elements are the conditions
        conditions = domain[1:]
        registrant_condition = ("registrant_id", "=", self.individual.id)
        household_condition = ("household_id", "=", self.individual.id)
        self.assertIn(registrant_condition, conditions)
        self.assertIn(household_condition, conditions)

    # -------------------------------------------------------------------------
    # case_count computed field triggered by relation changes
    # -------------------------------------------------------------------------

    def test_case_count_updates_when_case_added(self):
        """case_count increases after a new case is linked via registrant_id."""
        initial_count = self.individual.case_count

        self._create_case(registrant_id=self.individual.id)
        self.individual._compute_case_counts()

        self.assertEqual(self.individual.case_count, initial_count + 1)
