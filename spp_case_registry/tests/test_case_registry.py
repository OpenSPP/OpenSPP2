"""Tests for CaseRegistry (spp.case) extensions in spp_case_registry."""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseRegistry(TransactionCase):
    """Test the registry-related extensions on spp.case."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for all test methods."""
        super().setUpClass()

        # Create test user with case officer permissions
        cls.case_worker = (
            cls.env["res.users"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Registry Case Worker",
                    "login": "registry_case_worker",
                    "email": "registry_worker@test.com",
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
                    "name": "Registry Test Type",
                    "code": "RT001",
                    "domain": "social_protection",
                    "default_intensity": "2",
                }
            )
        )

        # Create a plain partner (non-registrant) as case client
        cls.client_partner = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Plain Client",
                    "email": "plain_client@test.com",
                }
            )
        )

        # Create an individual registrant
        cls.registrant_individual = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Individual Registrant",
                    "is_registrant": True,
                    "is_group": False,
                    "email": "individual@test.com",
                }
            )
        )

        # Create a second individual registrant for previous cases tests
        cls.registrant_individual_2 = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Individual Registrant Two",
                    "is_registrant": True,
                    "is_group": False,
                    "email": "individual2@test.com",
                }
            )
        )

        # Create a household (group registrant)
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

        # Create a second household for differentiation tests
        cls.household_2 = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Second Household",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
        )

        # Create area for area field tests
        cls.area = (
            cls.env["spp.area"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "draft_name": "Test Area",
                }
            )
        )

    def _create_case(self, **kwargs):
        """Helper to create a case with sane defaults."""
        vals = {
            "case_type_id": self.case_type.id,
            "partner_id": self.client_partner.id,
            "case_worker_id": self.case_worker.id,
            "presenting_issue": "<p>Test issue</p>",
        }
        vals.update(kwargs)
        return self.env["spp.case"].with_context(tracking_disable=True).create(vals)

    # -------------------------------------------------------------------------
    # Field defaults / basic creation
    # -------------------------------------------------------------------------

    def test_create_case_with_registrant_fields(self):
        """Registry-specific fields are stored on the case."""
        case = self._create_case(
            registrant_id=self.registrant_individual.id,
            household_id=self.household.id,
            area_id=self.area.id,
        )

        self.assertEqual(case.registrant_id, self.registrant_individual)
        self.assertEqual(case.household_id, self.household)
        self.assertEqual(case.area_id, self.area)

    def test_create_case_without_registry_fields(self):
        """Registry fields are all optional and default to empty."""
        case = self._create_case()

        self.assertFalse(case.registrant_id)
        self.assertFalse(case.household_id)
        self.assertFalse(case.area_id)

    def test_household_member_ids_stored(self):
        """Household members can be associated with a case."""
        case = self._create_case()

        case.write(
            {
                "household_member_ids": [
                    Command.link(self.registrant_individual.id),
                    Command.link(self.registrant_individual_2.id),
                ]
            }
        )

        self.assertIn(self.registrant_individual, case.household_member_ids)
        self.assertIn(self.registrant_individual_2, case.household_member_ids)
        self.assertEqual(len(case.household_member_ids), 2)

    # -------------------------------------------------------------------------
    # _compute_previous_cases — registrant_id branch
    # -------------------------------------------------------------------------

    def test_previous_cases_by_registrant(self):
        """Previous cases are found when the same registrant_id is used."""
        case1 = self._create_case(registrant_id=self.registrant_individual.id)
        case2 = self._create_case(registrant_id=self.registrant_individual.id)

        # Trigger compute explicitly
        case2._compute_previous_cases()

        self.assertIn(case1, case2.previous_case_ids)
        self.assertEqual(case2.previous_case_count, 1)

        # case1 should also see case2 as previous
        case1._compute_previous_cases()
        self.assertIn(case2, case1.previous_case_ids)
        self.assertEqual(case1.previous_case_count, 1)

    def test_previous_cases_does_not_include_self(self):
        """A case should never appear in its own previous_case_ids."""
        case = self._create_case(registrant_id=self.registrant_individual.id)
        case._compute_previous_cases()

        self.assertNotIn(case, case.previous_case_ids)

    def test_previous_cases_different_registrant(self):
        """Cases for different registrants do not appear as previous cases."""
        case1 = self._create_case(registrant_id=self.registrant_individual.id)
        case2 = self._create_case(registrant_id=self.registrant_individual_2.id)

        case2._compute_previous_cases()

        self.assertNotIn(case1, case2.previous_case_ids)
        self.assertEqual(case2.previous_case_count, 0)

    # -------------------------------------------------------------------------
    # _compute_previous_cases — household_id branch
    # -------------------------------------------------------------------------

    def test_previous_cases_by_household(self):
        """Previous cases are found when the same household_id is used (no registrant)."""
        case1 = self._create_case(household_id=self.household.id)
        case2 = self._create_case(household_id=self.household.id)

        case2._compute_previous_cases()

        self.assertIn(case1, case2.previous_case_ids)
        self.assertEqual(case2.previous_case_count, 1)

    def test_previous_cases_different_household(self):
        """Cases for different households do not appear as previous cases."""
        case1 = self._create_case(household_id=self.household.id)
        case2 = self._create_case(household_id=self.household_2.id)

        case2._compute_previous_cases()

        self.assertNotIn(case1, case2.previous_case_ids)
        self.assertEqual(case2.previous_case_count, 0)

    # -------------------------------------------------------------------------
    # _compute_previous_cases — neither registrant_id nor household_id
    # -------------------------------------------------------------------------

    def test_previous_cases_no_registrant_or_household(self):
        """When neither registrant_id nor household_id is set, previous cases are empty."""
        case = self._create_case()
        case._compute_previous_cases()

        self.assertFalse(case.previous_case_ids)
        self.assertEqual(case.previous_case_count, 0)

    # -------------------------------------------------------------------------
    # _compute_previous_cases — registrant_id takes precedence over household_id
    # -------------------------------------------------------------------------

    def test_previous_cases_registrant_takes_precedence(self):
        """When both registrant_id and household_id are set, registrant_id is used for matching."""
        # Two cases with same registrant but different household
        case1 = self._create_case(
            registrant_id=self.registrant_individual.id,
            household_id=self.household.id,
        )
        case2 = self._create_case(
            registrant_id=self.registrant_individual.id,
            household_id=self.household_2.id,
        )

        case2._compute_previous_cases()

        # Should match on registrant, not household
        self.assertIn(case1, case2.previous_case_ids)

    # -------------------------------------------------------------------------
    # action_view_previous_cases
    # -------------------------------------------------------------------------

    def test_action_view_previous_cases_returns_window_action(self):
        """action_view_previous_cases returns an act_window with correct domain."""
        self._create_case(registrant_id=self.registrant_individual.id)
        case2 = self._create_case(registrant_id=self.registrant_individual.id)

        # Ensure compute has run
        case2._compute_previous_cases()

        action = case2.action_view_previous_cases()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.case")
        self.assertIn("tree", action["view_mode"])
        self.assertIn("form", action["view_mode"])
        self.assertEqual(action["domain"], [("id", "in", case2.previous_case_ids.ids)])
        self.assertFalse(action["context"].get("create"))

    def test_action_view_previous_cases_empty_previous(self):
        """action_view_previous_cases works when there are no previous cases."""
        case = self._create_case()
        case._compute_previous_cases()

        action = case.action_view_previous_cases()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["domain"], [("id", "in", [])])

    # -------------------------------------------------------------------------
    # _onchange_registrant_id
    # -------------------------------------------------------------------------

    def test_onchange_registrant_id_sets_partner(self):
        """Selecting a registrant auto-fills partner_id."""
        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test</p>",
            }
        )

        case.registrant_id = self.registrant_individual
        case._onchange_registrant_id()

        self.assertEqual(case.partner_id, self.registrant_individual)

    def test_onchange_registrant_id_fills_household_from_membership(self):
        """Selecting a registrant fills household_id from group membership."""
        # Create group membership
        membership = (
            self.env["spp.group.membership"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "group": self.household.id,
                    "individual": self.registrant_individual.id,
                }
            )
        )

        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test</p>",
            }
        )

        case.registrant_id = self.registrant_individual
        case._onchange_registrant_id()

        self.assertEqual(case.household_id, self.household)

        # Clean up membership to avoid affecting other tests
        membership.unlink()

    def test_onchange_registrant_id_fills_area_from_registrant(self):
        """Selecting a registrant fills area_id if the registrant has an area."""
        # Assign an area to the registrant
        self.registrant_individual.with_context(tracking_disable=True).write({"area_id": self.area.id})

        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test</p>",
            }
        )

        case.registrant_id = self.registrant_individual
        case._onchange_registrant_id()

        self.assertEqual(case.area_id, self.area)

        # Clean up
        self.registrant_individual.with_context(tracking_disable=True).write({"area_id": False})

    def test_onchange_registrant_id_no_registrant_set(self):
        """When registrant_id is cleared, partner_id is not changed by the onchange."""
        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "partner_id": self.client_partner.id,
                "presenting_issue": "<p>Test</p>",
            }
        )

        # Clear registrant_id — onchange should not execute the fill logic
        case.registrant_id = False
        case._onchange_registrant_id()

        # partner_id should remain unchanged
        self.assertEqual(case.partner_id, self.client_partner)

    # -------------------------------------------------------------------------
    # _onchange_household_id
    # -------------------------------------------------------------------------

    def test_onchange_household_id_fills_members(self):
        """Selecting a household fills household_member_ids with group members."""
        membership1 = (
            self.env["spp.group.membership"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "group": self.household.id,
                    "individual": self.registrant_individual.id,
                }
            )
        )
        membership2 = (
            self.env["spp.group.membership"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "group": self.household.id,
                    "individual": self.registrant_individual_2.id,
                }
            )
        )

        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test</p>",
            }
        )

        case.household_id = self.household
        case._onchange_household_id()

        member_ids = case.household_member_ids.ids
        self.assertIn(self.registrant_individual.id, member_ids)
        self.assertIn(self.registrant_individual_2.id, member_ids)

        # Clean up
        membership1.unlink()
        membership2.unlink()

    def test_onchange_household_id_empty_household(self):
        """When household_id is not set, household_member_ids is not modified."""
        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test</p>",
            }
        )

        # No household selected
        case.household_id = False
        case._onchange_household_id()

        # household_member_ids should be empty
        self.assertFalse(case.household_member_ids)

    # -------------------------------------------------------------------------
    # Multiple previous cases
    # -------------------------------------------------------------------------

    def test_previous_case_count_multiple(self):
        """previous_case_count reflects all previous cases for the same registrant."""
        case1 = self._create_case(registrant_id=self.registrant_individual.id)
        case2 = self._create_case(registrant_id=self.registrant_individual.id)
        case3 = self._create_case(registrant_id=self.registrant_individual.id)

        # For case3 there should be 2 previous cases (case1 and case2)
        case3._compute_previous_cases()

        self.assertEqual(case3.previous_case_count, 2)
        self.assertIn(case1, case3.previous_case_ids)
        self.assertIn(case2, case3.previous_case_ids)
        self.assertNotIn(case3, case3.previous_case_ids)
