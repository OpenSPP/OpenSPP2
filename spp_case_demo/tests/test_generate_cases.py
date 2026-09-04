# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for spp.case.demo.generator model."""

import random
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseDemoGeneratorFields(TransactionCase):
    """Tests for field defaults and constraints on the generator model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Ensure required case stages exist for all tests
        Stage = cls.env["spp.case.stage"]
        stage_data = [
            ("Intake", "intake", 10),
            ("Assessment", "assessment", 20),
            ("Planning", "planning", 30),
            ("Implementation", "implementation", 40),
            ("Monitoring", "monitoring", 50),
            ("Closed", "closure", 60),
        ]
        for name, phase, sequence in stage_data:
            if not Stage.search([("phase", "=", phase)], limit=1):
                Stage.create({"name": name, "phase": phase, "sequence": sequence, "is_closed": phase == "closure"})

        # Ensure required case types exist
        CaseType = cls.env["spp.case.type"]
        type_data = [
            ("General Support", "GEN"),
            ("Emergency Assistance", "EMG"),
            ("Health Support", "HLT"),
            ("Child Protection", "CHP"),
        ]
        for name, code in type_data:
            if not CaseType.search([("name", "=", name)], limit=1):
                CaseType.create({"name": name, "code": code})

        # Create a registrant (beneficiary) so linking tests work
        cls.beneficiary = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create(
                {
                    "name": "Test Beneficiary",
                    "is_registrant": True,
                }
            )
        )

    def _make_generator(self, **kwargs):
        """Helper: create a spp.case.demo.generator with sensible defaults."""
        defaults = {
            "name": "Test Generator",
            "number_of_cases": 1,
            "include_stories": False,
            "cases_days_back": 30,
            "link_to_beneficiaries": True,
            "percentage_with_plans": 0.0,
            "percentage_with_visits": 0.0,
            "percentage_with_notes": 0.0,
            "percentage_closed": 0.0,
        }
        defaults.update(kwargs)
        return self.env["spp.case.demo.generator"].create(defaults)

    # ------------------------------------------------------------------
    # Constraint tests
    # ------------------------------------------------------------------

    def test_constraint_number_of_cases_minimum(self):
        """number_of_cases must be at least 1."""
        with self.assertRaises(UserError):
            self._make_generator(number_of_cases=0)

    def test_constraint_number_of_cases_maximum(self):
        """number_of_cases must not exceed 5,000."""
        with self.assertRaises(UserError):
            self._make_generator(number_of_cases=5001)

    def test_constraint_number_of_cases_valid_boundary_values(self):
        """number_of_cases of 1 and 5000 must be accepted without error."""
        gen_min = self._make_generator(number_of_cases=1)
        self.assertEqual(gen_min.number_of_cases, 1)

        gen_max = self._make_generator(number_of_cases=5000)
        self.assertEqual(gen_max.number_of_cases, 5000)

    # ------------------------------------------------------------------
    # Default field value tests
    # ------------------------------------------------------------------

    def test_default_name(self):
        """Default name should be populated."""
        gen = self._make_generator()
        self.assertTrue(gen.name)

    def test_default_number_of_cases(self):
        """Default number_of_cases should be 25 when not overridden."""
        gen = self.env["spp.case.demo.generator"].create({"name": "Default Test"})
        self.assertEqual(gen.number_of_cases, 25)

    def test_default_include_stories(self):
        """Default include_stories should be True."""
        gen = self.env["spp.case.demo.generator"].create({"name": "Default Test 2"})
        self.assertTrue(gen.include_stories)

    def test_default_cases_days_back(self):
        """Default cases_days_back should be 120."""
        gen = self.env["spp.case.demo.generator"].create({"name": "Default Test 3"})
        self.assertEqual(gen.cases_days_back, 120)

    def test_default_percentage_with_plans(self):
        """Default percentage_with_plans should be 70.0."""
        gen = self.env["spp.case.demo.generator"].create({"name": "Default Test 4"})
        self.assertAlmostEqual(gen.percentage_with_plans, 70.0)

    def test_default_percentage_closed(self):
        """Default percentage_closed should be 40.0."""
        gen = self.env["spp.case.demo.generator"].create({"name": "Default Test 5"})
        self.assertAlmostEqual(gen.percentage_closed, 40.0)

    def test_default_link_to_beneficiaries(self):
        """Default link_to_beneficiaries should be True."""
        gen = self.env["spp.case.demo.generator"].create({"name": "Default Test 6"})
        self.assertTrue(gen.link_to_beneficiaries)

    # ------------------------------------------------------------------
    # locale_origin_faker_locale related field
    # ------------------------------------------------------------------

    def test_locale_origin_faker_locale_related(self):
        """locale_origin_faker_locale should reflect the country's faker_locale."""
        country = self.env["res.country"].search([("faker_locale", "!=", False)], limit=1)
        if not country:
            # If no country has faker_locale configured, skip gracefully
            return
        gen = self._make_generator()
        gen.locale_origin = country
        self.assertEqual(gen.locale_origin_faker_locale, country.faker_locale)

    def test_locale_origin_empty_gives_empty_faker_locale(self):
        """When locale_origin is not set, locale_origin_faker_locale should be falsy."""
        gen = self._make_generator()
        gen.locale_origin = False
        # The related field returns False/empty when origin is not set
        self.assertFalse(gen.locale_origin_faker_locale)


@tagged("post_install", "-at_install")
class TestCaseDemoGeneratorHelpers(TransactionCase):
    """Tests for the private helper methods on spp.case.demo.generator."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Stage = cls.env["spp.case.stage"]
        stage_data = [
            ("Intake", "intake", 10),
            ("Assessment", "assessment", 20),
            ("Planning", "planning", 30),
            ("Implementation", "implementation", 40),
            ("Monitoring", "monitoring", 50),
            ("Closed", "closure", 60),
        ]
        for name, phase, sequence in stage_data:
            if not Stage.search([("phase", "=", phase)], limit=1):
                Stage.create({"name": name, "phase": phase, "sequence": sequence, "is_closed": phase == "closure"})

        CaseType = cls.env["spp.case.type"]
        type_data = [
            ("General Support", "GEN"),
            ("Emergency Assistance", "EMG"),
            ("Health Support", "HLT"),
            ("Child Protection", "CHP"),
        ]
        for name, code in type_data:
            if not CaseType.search([("name", "=", name)], limit=1):
                CaseType.create({"name": name, "code": code})

        cls.beneficiary = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Demo Beneficiary", "is_registrant": True})
        )
        cls.non_registrant = (
            cls.env["res.partner"].with_context(tracking_disable=True).create({"name": "Non Registrant"})
        )

        cls.gen = cls.env["spp.case.demo.generator"].create(
            {
                "name": "Helper Test Generator",
                "number_of_cases": 1,
                "include_stories": False,
                "link_to_beneficiaries": True,
                "percentage_with_plans": 0.0,
                "percentage_with_visits": 0.0,
                "percentage_with_notes": 0.0,
                "percentage_closed": 0.0,
            }
        )

    # ------------------------------------------------------------------
    # _get_available_beneficiaries
    # ------------------------------------------------------------------

    def test_get_available_beneficiaries_returns_registrants(self):
        """_get_available_beneficiaries should return only is_registrant partners."""
        beneficiaries = self.gen._get_available_beneficiaries()
        self.assertTrue(len(beneficiaries) >= 1)
        for partner in beneficiaries:
            self.assertTrue(partner.is_registrant)

    def test_get_available_beneficiaries_excludes_non_registrants(self):
        """Non-registrant partners must not appear in the beneficiaries list."""
        beneficiaries = self.gen._get_available_beneficiaries()
        self.assertNotIn(self.non_registrant, beneficiaries)

    # ------------------------------------------------------------------
    # _get_or_create_case_type
    # ------------------------------------------------------------------

    def test_get_or_create_case_type_finds_existing(self):
        """_get_or_create_case_type should return existing type by name."""
        existing = self.env["spp.case.type"].search([("name", "=", "General Support")], limit=1)
        result = self.gen._get_or_create_case_type("General Support")
        self.assertEqual(result.id, existing.id)

    def test_get_or_create_case_type_creates_new(self):
        """_get_or_create_case_type should create a type when none exists."""
        unique_name = "Unique Test Type XYZ123"
        # Ensure it doesn't pre-exist
        self.env["spp.case.type"].search([("name", "=", unique_name)]).unlink()

        result = self.gen._get_or_create_case_type(unique_name)
        self.assertTrue(result)
        self.assertEqual(result.name, unique_name)

    def test_get_or_create_case_type_code_truncated(self):
        """Created case type code should be truncated to 10 characters."""
        long_name = "Very Long Type Name That Exceeds Ten Chars"
        self.env["spp.case.type"].search([("name", "=", long_name)]).unlink()
        result = self.gen._get_or_create_case_type(long_name)
        self.assertLessEqual(len(result.code), 10)

    # ------------------------------------------------------------------
    # _get_random_case_type
    # ------------------------------------------------------------------

    def test_get_random_case_type_returns_type_when_types_exist(self):
        """_get_random_case_type should return a case type when types exist."""
        result = self.gen._get_random_case_type()
        self.assertTrue(result, "Expected a case type to be returned")
        self.assertIsInstance(result._name, str)
        self.assertEqual(result._name, "spp.case.type")

    def test_get_random_case_type_returns_none_when_no_types(self):
        """_get_random_case_type should return None when no types exist."""
        gen = self.gen
        with patch.object(
            type(self.env["spp.case.type"]),
            "search",
            return_value=self.env["spp.case.type"],
        ):
            result = gen._get_random_case_type()
            self.assertIsNone(result)

    # ------------------------------------------------------------------
    # _get_random_stage
    # ------------------------------------------------------------------

    def test_get_random_stage_returns_stage_when_stages_exist(self):
        """_get_random_stage should return a stage when stages exist."""
        result = self.gen._get_random_stage()
        self.assertTrue(result)
        self.assertEqual(result._name, "spp.case.stage")

    def test_get_random_stage_returns_none_when_no_stages(self):
        """_get_random_stage should return None when no stages exist."""
        with patch.object(
            type(self.env["spp.case.stage"]),
            "search",
            return_value=self.env["spp.case.stage"],
        ):
            result = self.gen._get_random_stage()
            self.assertIsNone(result)

    # ------------------------------------------------------------------
    # _determine_stage_from_journey
    # ------------------------------------------------------------------

    def test_determine_stage_closure_for_close_case_action(self):
        """Journey with close_case action should return closure stage."""
        journey = [{"action": "close_case", "days_back": 5}]
        result = self.gen._determine_stage_from_journey(journey)
        if result:
            self.assertEqual(result.phase, "closure")

    def test_determine_stage_monitoring_for_many_visits(self):
        """Journey with >3 visits/notes should return monitoring stage."""
        journey = [
            {"action": "home_visit", "days_back": 50},
            {"action": "progress_note", "days_back": 40},
            {"action": "home_visit", "days_back": 30},
            {"action": "progress_note", "days_back": 20},
        ]
        result = self.gen._determine_stage_from_journey(journey)
        if result:
            self.assertEqual(result.phase, "monitoring")

    def test_determine_stage_implementation_for_completed_intervention(self):
        """Journey with complete_intervention should prefer implementation stage."""
        journey = [
            {"action": "create_plan", "days_back": 30},
            {"action": "complete_intervention", "days_back": 20, "intervention": "X"},
        ]
        result = self.gen._determine_stage_from_journey(journey)
        if result:
            self.assertEqual(result.phase, "implementation")

    def test_determine_stage_planning_for_create_plan(self):
        """Journey with create_plan (no completions) should return planning stage."""
        journey = [
            {"action": "intake", "days_back": 40},
            {"action": "create_plan", "days_back": 35},
        ]
        result = self.gen._determine_stage_from_journey(journey)
        if result:
            self.assertEqual(result.phase, "planning")

    def test_determine_stage_assessment_for_assessment_action(self):
        """Journey with assessment action should return assessment stage."""
        journey = [
            {"action": "intake", "days_back": 20},
            {"action": "assessment", "days_back": 18},
        ]
        result = self.gen._determine_stage_from_journey(journey)
        if result:
            self.assertEqual(result.phase, "assessment")

    def test_determine_stage_default_to_intake(self):
        """Journey with only intake action should default to intake stage."""
        journey = [{"action": "intake", "days_back": 5}]
        result = self.gen._determine_stage_from_journey(journey)
        if result:
            self.assertEqual(result.phase, "intake")

    # ------------------------------------------------------------------
    # _find_or_create_client
    # ------------------------------------------------------------------

    def test_find_or_create_client_finds_existing_registrant(self):
        """_find_or_create_client returns existing registrant by name."""
        from unittest.mock import MagicMock

        client_info = {"name": self.beneficiary.name}
        result = self.gen._find_or_create_client(client_info, [self.beneficiary], MagicMock())
        self.assertEqual(result.id, self.beneficiary.id)

    def test_find_or_create_client_returns_random_from_list_when_name_missing(self):
        """_find_or_create_client returns from beneficiaries when no name given."""
        from unittest.mock import MagicMock

        client_info = {}
        result = self.gen._find_or_create_client(client_info, [self.beneficiary], MagicMock())
        self.assertEqual(result.id, self.beneficiary.id)

    def test_find_or_create_client_returns_none_when_no_beneficiaries_and_no_name(self):
        """_find_or_create_client returns None when list is empty and no name match."""
        from unittest.mock import MagicMock

        client_info = {}
        result = self.gen._find_or_create_client(client_info, [], MagicMock())
        self.assertIsNone(result)

    def test_find_or_create_client_falls_back_to_list_when_name_not_found(self):
        """When name doesn't match existing registrant, a random beneficiary is returned."""
        from unittest.mock import MagicMock

        client_info = {"name": "Nonexistent Person XYZ999"}
        result = self.gen._find_or_create_client(client_info, [self.beneficiary], MagicMock())
        self.assertEqual(result.id, self.beneficiary.id)

    # ------------------------------------------------------------------
    # _get_or_create_service
    # ------------------------------------------------------------------

    def test_get_or_create_service_returns_none_when_model_not_in_env(self):
        """_get_or_create_service should return None when spp.service is not installed."""
        # spp.service is not in spp_case_demo's dependency tree
        result = self.gen._get_or_create_service("Some Service")
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestCaseDemoGeneratorGenerate(TransactionCase):
    """Tests for the main generate_cases flow on spp.case.demo.generator."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Stage = cls.env["spp.case.stage"]
        stage_data = [
            ("Intake", "intake", 10, False),
            ("Assessment", "assessment", 20, False),
            ("Planning", "planning", 30, False),
            ("Implementation", "implementation", 40, False),
            ("Monitoring", "monitoring", 50, False),
            ("Closed", "closure", 60, True),
        ]
        for name, phase, sequence, is_closed in stage_data:
            if not Stage.search([("phase", "=", phase)], limit=1):
                Stage.create({"name": name, "phase": phase, "sequence": sequence, "is_closed": is_closed})

        CaseType = cls.env["spp.case.type"]
        type_data = [
            ("General Support", "GEN", 1),
            ("Emergency Assistance", "EMG", 3),
            ("Health Support", "HLT", 1),
            ("Child Protection", "CHP", 2),
        ]
        for name, code, intensity in type_data:
            if not CaseType.search([("name", "=", name)], limit=1):
                CaseType.create({"name": name, "code": code, "default_intensity": str(intensity)})

        # partner_id is required on spp.case; always provide a registrant
        cls.beneficiary = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Gen Test Beneficiary", "is_registrant": True})
        )

    def _make_generator(self, **kwargs):
        # Default to link_to_beneficiaries=True because spp.case.partner_id is required
        defaults = {
            "name": "Gen Test",
            "number_of_cases": 2,
            "include_stories": False,
            "cases_days_back": 30,
            "link_to_beneficiaries": True,
            "percentage_with_plans": 0.0,
            "percentage_with_visits": 0.0,
            "percentage_with_notes": 0.0,
            "percentage_closed": 0.0,
        }
        defaults.update(kwargs)
        return self.env["spp.case.demo.generator"].create(defaults)

    # ------------------------------------------------------------------
    # generate_cases: no beneficiaries but link_to_beneficiaries=True
    # ------------------------------------------------------------------

    def test_generate_cases_raises_when_no_beneficiaries_and_link_enabled(self):
        """Should raise UserError when link_to_beneficiaries=True but no registrants exist."""
        gen = self._make_generator(link_to_beneficiaries=True, number_of_cases=1)
        # Odoo model methods must be patched on the class, not the instance
        GeneratorModel = type(gen)
        with patch.object(GeneratorModel, "_get_available_beneficiaries", return_value=self.env["res.partner"]):
            with self.assertRaises(UserError):
                gen.generate_cases()

    # ------------------------------------------------------------------
    # generate_cases: basic random case generation
    # ------------------------------------------------------------------

    def test_generate_cases_creates_requested_number_of_cases(self):
        """generate_cases should create number_of_cases random cases."""
        gen = self._make_generator(number_of_cases=3, include_stories=False)
        cases_before = self.env["spp.case"].search([]).ids
        result = gen.generate_cases()
        new_cases = self.env["spp.case"].search([("id", "not in", cases_before)])
        self.assertEqual(len(new_cases), 3)
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.case")

    def test_generate_cases_returns_action_with_generated_case_ids(self):
        """The action domain returned by generate_cases should only include new cases."""
        gen = self._make_generator(number_of_cases=2, include_stories=False)
        cases_before = self.env["spp.case"].search([]).ids
        result = gen.generate_cases()

        domain = result.get("domain", [])
        self.assertTrue(domain)
        id_list = domain[0][2]
        for cid in id_list:
            self.assertNotIn(cid, cases_before)

    def test_generate_cases_with_link_to_beneficiaries(self):
        """generate_cases with link_to_beneficiaries=True links cases to registrants."""
        gen = self._make_generator(number_of_cases=2, link_to_beneficiaries=True)
        result = gen.generate_cases()
        domain = result["domain"]
        case_ids = domain[0][2]
        cases = self.env["spp.case"].browse(case_ids)
        for case in cases:
            if case.partner_id:
                self.assertTrue(case.partner_id.is_registrant)

    def test_generate_cases_context_action_properties(self):
        """The returned action should contain the right view_mode and context."""
        gen = self._make_generator(number_of_cases=1, include_stories=False)
        result = gen.generate_cases()
        self.assertIn("list", result.get("view_mode", ""))
        self.assertIn("search_default_group_by_stage", result.get("context", {}))

    # ------------------------------------------------------------------
    # generate_cases: percentage-driven related data
    # ------------------------------------------------------------------

    def test_generate_cases_with_plans(self):
        """generate_cases with percentage_with_plans=100 creates plans."""
        gen = self._make_generator(
            number_of_cases=2,
            percentage_with_plans=100.0,
        )
        result = gen.generate_cases()
        case_ids = result["domain"][0][2]
        cases = self.env["spp.case"].browse(case_ids)
        plans = self.env["spp.case.intervention.plan"].search([("case_id", "in", cases.ids)])
        self.assertTrue(len(plans) >= 1, "Expected at least one plan to be created")

    def test_generate_cases_with_visits(self):
        """generate_cases with percentage_with_visits=100 creates visits."""
        gen = self._make_generator(
            number_of_cases=2,
            percentage_with_visits=100.0,
        )
        result = gen.generate_cases()
        case_ids = result["domain"][0][2]
        visits = self.env["spp.case.visit"].search([("case_id", "in", case_ids)])
        self.assertTrue(len(visits) >= 1, "Expected at least one visit to be created")

    def test_generate_cases_with_notes(self):
        """generate_cases with percentage_with_notes=100 creates notes."""
        gen = self._make_generator(
            number_of_cases=2,
            percentage_with_notes=100.0,
        )
        result = gen.generate_cases()
        case_ids = result["domain"][0][2]
        notes = self.env["spp.case.note"].search([("case_id", "in", case_ids)])
        self.assertTrue(len(notes) >= 1, "Expected at least one note to be created")

    def test_generate_cases_with_closure(self):
        """generate_cases with percentage_closed=100 closes all cases."""
        closure_stage = self.env["spp.case.stage"].search([("phase", "=", "closure")], limit=1)
        gen = self._make_generator(
            number_of_cases=2,
            percentage_closed=100.0,
        )
        result = gen.generate_cases()
        case_ids = result["domain"][0][2]
        cases = self.env["spp.case"].browse(case_ids)
        for case in cases:
            if closure_stage:
                self.assertEqual(case.stage_id.id, closure_stage.id)
                self.assertTrue(case.actual_closure_date)

    # ------------------------------------------------------------------
    # generate_cases: with stories
    # ------------------------------------------------------------------

    def test_generate_cases_with_stories_creates_cases(self):
        """generate_cases with include_stories=True creates the demo story cases."""
        from ..models.case_demo_stories import CASE_DEMO_STORIES

        story_count = len(CASE_DEMO_STORIES)
        gen = self._make_generator(
            number_of_cases=story_count,
            include_stories=True,
        )
        result = gen.generate_cases()
        self.assertEqual(result["type"], "ir.actions.act_window")
        case_ids = result["domain"][0][2]
        self.assertTrue(len(case_ids) >= 1)

    def test_generate_cases_with_stories_zero_remaining(self):
        """When number_of_cases equals story count, no random cases are added beyond stories."""
        from ..models.case_demo_stories import CASE_DEMO_STORIES

        story_count = len(CASE_DEMO_STORIES)
        gen = self._make_generator(
            number_of_cases=story_count,
            include_stories=True,
        )
        result = gen.generate_cases()
        case_ids = result["domain"][0][2]
        # Total should be at most story_count (stories that succeed)
        self.assertLessEqual(len(case_ids), story_count)

    def test_generate_cases_stories_plus_random(self):
        """When number_of_cases exceeds story count, random cases fill the rest."""
        from ..models.case_demo_stories import CASE_DEMO_STORIES

        story_count = len(CASE_DEMO_STORIES)
        extra = 3
        gen = self._make_generator(
            number_of_cases=story_count + extra,
            include_stories=True,
        )
        result = gen.generate_cases()
        case_ids = result["domain"][0][2]
        # Stories that succeed plus extra random cases
        self.assertLessEqual(len(case_ids), story_count + extra)
        self.assertGreater(len(case_ids), 0)


@tagged("post_install", "-at_install")
class TestCaseDemoGeneratorJourney(TransactionCase):
    """Tests for _process_case_journey and _create_case_from_story."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Stage = cls.env["spp.case.stage"]
        stage_data = [
            ("Intake", "intake", 10, False),
            ("Assessment", "assessment", 20, False),
            ("Planning", "planning", 30, False),
            ("Implementation", "implementation", 40, False),
            ("Monitoring", "monitoring", 50, False),
            ("Closed", "closure", 60, True),
        ]
        for name, phase, sequence, is_closed in stage_data:
            if not Stage.search([("phase", "=", phase)], limit=1):
                Stage.create({"name": name, "phase": phase, "sequence": sequence, "is_closed": is_closed})

        CaseType = cls.env["spp.case.type"]
        for name, code in [("General Support", "GEN2"), ("Emergency Assistance", "EMG2")]:
            if not CaseType.search([("name", "=", name)], limit=1):
                CaseType.create({"name": name, "code": code})

        cls.client = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Journey Test Client", "is_registrant": True})
        )

        cls.gen = cls.env["spp.case.demo.generator"].create(
            {
                "name": "Journey Test Gen",
                "number_of_cases": 1,
                "include_stories": False,
                "link_to_beneficiaries": True,
                "percentage_with_plans": 0.0,
                "percentage_with_visits": 0.0,
                "percentage_with_notes": 0.0,
                "percentage_closed": 0.0,
            }
        )

        # Base case for journey tests
        case_type = CaseType.search([("name", "=", "General Support")], limit=1)
        stage_intake = Stage.search([("phase", "=", "intake")], limit=1)
        cls.base_case = (
            cls.env["spp.case"]
            .sudo()
            .create(
                {
                    "case_type_id": case_type.id,
                    "stage_id": stage_intake.id,
                    "partner_id": cls.client.id,
                    "presenting_issue": "Journey test case",
                    "case_worker_id": cls.env.user.id,
                }
            )
        )

    def _fake(self):
        """Return a simple Faker instance for test use."""
        from faker import Faker

        return Faker("en_US")

    # ------------------------------------------------------------------
    # _process_case_journey: individual action types
    # ------------------------------------------------------------------

    def test_journey_create_plan(self):
        """create_plan action should produce an intervention plan."""
        fake = self._fake()
        journey = [{"action": "create_plan", "days_back": 10, "plan_name": "Test Plan", "goals": "Goals"}]
        self.gen._process_case_journey(self.base_case, journey, fake)
        plans = self.env["spp.case.intervention.plan"].search([("case_id", "=", self.base_case.id)])
        self.assertTrue(len(plans) >= 1)

    def test_journey_add_intervention_requires_current_plan(self):
        """add_intervention without a prior create_plan should produce no intervention."""
        fake = self._fake()
        count_before = self.env["spp.case.intervention"].search_count([("plan_id.case_id", "=", self.base_case.id)])
        journey = [{"action": "add_intervention", "days_back": 10, "intervention": "Orphan intervention"}]
        self.gen._process_case_journey(self.base_case, journey, fake)
        count_after = self.env["spp.case.intervention"].search_count([("plan_id.case_id", "=", self.base_case.id)])
        # Without a plan, no intervention should be created
        self.assertEqual(count_before, count_after)

    def test_journey_create_plan_then_add_intervention(self):
        """create_plan followed by add_intervention creates an intervention."""
        fake = self._fake()
        journey = [
            {"action": "create_plan", "days_back": 20, "plan_name": "Plan For Intervention"},
            {"action": "add_intervention", "days_back": 18, "intervention": "Test Intervention Step"},
        ]
        self.gen._process_case_journey(self.base_case, journey, fake)
        interventions = self.env["spp.case.intervention"].search(
            [("plan_id.case_id", "=", self.base_case.id), ("name", "=", "Test Intervention Step")]
        )
        self.assertTrue(len(interventions) >= 1)

    def test_journey_complete_intervention(self):
        """complete_intervention marks the named intervention as completed."""
        fake = self._fake()
        journey = [
            {"action": "create_plan", "days_back": 30, "plan_name": "Completion Plan"},
            {"action": "add_intervention", "days_back": 28, "intervention": "To Be Completed"},
            {"action": "complete_intervention", "days_back": 20, "intervention": "To Be Completed"},
        ]
        self.gen._process_case_journey(self.base_case, journey, fake)
        intervention = self.env["spp.case.intervention"].search(
            [
                ("plan_id.case_id", "=", self.base_case.id),
                ("name", "=", "To Be Completed"),
                ("state", "=", "completed"),
            ],
            limit=1,
        )
        self.assertTrue(intervention, "Intervention should have been marked as completed")

    def test_journey_complete_intervention_name_not_found(self):
        """complete_intervention with a name that doesn't match any intervention is a no-op."""
        fake = self._fake()
        journey = [
            {"action": "create_plan", "days_back": 30, "plan_name": "No-op Plan"},
            {
                "action": "complete_intervention",
                "days_back": 20,
                "intervention": "Nonexistent intervention name",
            },
        ]
        # Should not raise
        try:
            self.gen._process_case_journey(self.base_case, journey, fake)
        except Exception as exc:
            self.fail(f"complete_intervention raised unexpectedly: {exc}")

    def test_journey_home_visit(self):
        """home_visit action should create a case visit with visit_type='home'."""
        fake = self._fake()
        journey = [{"action": "home_visit", "days_back": 5, "purpose": "Check-in"}]
        count_before = self.env["spp.case.visit"].search_count([("case_id", "=", self.base_case.id)])
        self.gen._process_case_journey(self.base_case, journey, fake)
        count_after = self.env["spp.case.visit"].search_count([("case_id", "=", self.base_case.id)])
        self.assertEqual(count_after, count_before + 1)
        visit = self.env["spp.case.visit"].search([("case_id", "=", self.base_case.id)], order="id desc", limit=1)
        self.assertEqual(visit.visit_type, "home")

    def test_journey_office_visit(self):
        """office_visit action should create a case visit with visit_type='office'."""
        fake = self._fake()
        journey = [{"action": "office_visit", "days_back": 5, "purpose": "Office meeting"}]
        self.gen._process_case_journey(self.base_case, journey, fake)
        visit = self.env["spp.case.visit"].search([("case_id", "=", self.base_case.id)], order="id desc", limit=1)
        self.assertEqual(visit.visit_type, "office")

    def test_journey_final_visit(self):
        """final_visit action should create a visit (treated as 'home' type)."""
        fake = self._fake()
        journey = [{"action": "final_visit", "days_back": 3, "purpose": "Closure visit"}]
        count_before = self.env["spp.case.visit"].search_count([("case_id", "=", self.base_case.id)])
        self.gen._process_case_journey(self.base_case, journey, fake)
        count_after = self.env["spp.case.visit"].search_count([("case_id", "=", self.base_case.id)])
        self.assertEqual(count_after, count_before + 1)

    def test_journey_progress_note(self):
        """progress_note action should create a case note with note_type='progress'."""
        fake = self._fake()
        journey = [{"action": "progress_note", "days_back": 10, "note": "Progress made"}]
        count_before = self.env["spp.case.note"].search_count([("case_id", "=", self.base_case.id)])
        self.gen._process_case_journey(self.base_case, journey, fake)
        count_after = self.env["spp.case.note"].search_count([("case_id", "=", self.base_case.id)])
        self.assertEqual(count_after, count_before + 1)
        note = self.env["spp.case.note"].search([("case_id", "=", self.base_case.id)], order="id desc", limit=1)
        self.assertEqual(note.note_type, "progress")

    def test_journey_assessment_note(self):
        """assessment action should create a case note with note_type='assessment'."""
        fake = self._fake()
        journey = [{"action": "assessment", "days_back": 15, "notes": "Assessment done"}]
        self.gen._process_case_journey(self.base_case, journey, fake)
        note = self.env["spp.case.note"].search(
            [("case_id", "=", self.base_case.id), ("note_type", "=", "assessment")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(note)

    def test_journey_emergency_assessment_note(self):
        """emergency_assessment action should create an assessment note."""
        fake = self._fake()
        journey = [{"action": "emergency_assessment", "days_back": 2}]
        self.gen._process_case_journey(self.base_case, journey, fake)
        note = self.env["spp.case.note"].search(
            [("case_id", "=", self.base_case.id), ("note_type", "=", "assessment")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(note)

    def test_journey_safety_assessment_note(self):
        """safety_assessment action should create an assessment note."""
        fake = self._fake()
        journey = [{"action": "safety_assessment", "days_back": 2}]
        self.gen._process_case_journey(self.base_case, journey, fake)
        note = self.env["spp.case.note"].search(
            [("case_id", "=", self.base_case.id), ("note_type", "=", "assessment")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(note)

    def test_journey_add_referral_skips_silently_when_no_service_model(self):
        """add_referral without spp.service model does not raise; it skips silently."""
        fake = self._fake()
        journey = [{"action": "add_referral", "days_back": 10, "service": "Housing", "reason": "Need it"}]
        # spp.service doesn't exist in this module, so it returns None and no referral is created
        try:
            self.gen._process_case_journey(self.base_case, journey, fake)
        except Exception as exc:
            self.fail(f"_process_case_journey raised unexpectedly: {exc}")

    def test_journey_close_case(self):
        """close_case action moves case to closure stage and sets closure date."""
        fake = self._fake()
        journey = [{"action": "close_case", "days_back": 5}]
        self.gen._process_case_journey(self.base_case, journey, fake)
        closure_stage = self.env["spp.case.stage"].search([("phase", "=", "closure")], limit=1)
        if closure_stage:
            self.assertEqual(self.base_case.stage_id.id, closure_stage.id)
            self.assertTrue(self.base_case.actual_closure_date)

    def test_journey_close_case_also_completes_active_plan(self):
        """close_case with an active plan should mark the plan as completed."""
        fake = self._fake()
        case_type = self.env["spp.case.type"].search([("name", "=", "General Support")], limit=1)
        stage_intake = self.env["spp.case.stage"].search([("phase", "=", "intake")], limit=1)
        test_case = (
            self.env["spp.case"]
            .sudo()
            .create(
                {
                    "case_type_id": case_type.id,
                    "stage_id": stage_intake.id,
                    "partner_id": self.client.id,
                    "presenting_issue": "Plan closure test",
                    "case_worker_id": self.env.user.id,
                }
            )
        )
        journey = [
            {"action": "create_plan", "days_back": 40, "plan_name": "Plan to Close"},
            {"action": "close_case", "days_back": 5},
        ]
        self.gen._process_case_journey(test_case, journey, fake)
        plan = self.env["spp.case.intervention.plan"].search([("case_id", "=", test_case.id)], limit=1)
        if plan:
            self.assertEqual(plan.state, "completed")

    def test_journey_close_case_releases_the_current_plan(self):
        """close_case must not leave a finished plan as the case's current plan.

        The step used to write ``state`` directly, so the generated plan kept
        ``is_current`` and had no ``actual_end_date`` -- the incoherent pair
        spp_case_base #458 is about, seeded into every demo database.
        """
        fake = self._fake()
        case_type = self.env["spp.case.type"].search([("name", "=", "General Support")], limit=1)
        stage_intake = self.env["spp.case.stage"].search([("phase", "=", "intake")], limit=1)
        test_case = (
            self.env["spp.case"]
            .sudo()
            .create(
                {
                    "case_type_id": case_type.id,
                    "stage_id": stage_intake.id,
                    "partner_id": self.client.id,
                    "presenting_issue": "Plan currency test",
                    "case_worker_id": self.env.user.id,
                }
            )
        )
        journey = [
            {"action": "create_plan", "days_back": 40, "plan_name": "Plan to Release"},
            {"action": "close_case", "days_back": 5},
        ]
        self.gen._process_case_journey(test_case, journey, fake)

        plan = self.env["spp.case.intervention.plan"].search([("case_id", "=", test_case.id)], limit=1)
        self.assertTrue(plan, "create_plan should have produced a plan to close")
        self.assertEqual(plan.state, "completed", "close_case should complete the plan")
        self.assertTrue(plan.actual_end_date, "Completing through the action should stamp actual_end_date")
        self.assertFalse(plan.is_current, "A completed plan is not the case's current plan")
        self.assertFalse(test_case.current_plan_id, "The closed case should report no current plan")

    def test_journey_intake_action_is_ignored_gracefully(self):
        """intake action has no handler; it should be skipped without error."""
        fake = self._fake()
        journey = [{"action": "intake", "days_back": 10, "notes": "Intake note"}]
        try:
            self.gen._process_case_journey(self.base_case, journey, fake)
        except Exception as exc:
            self.fail(f"intake action raised unexpectedly: {exc}")

    # ------------------------------------------------------------------
    # _create_case_from_story
    # ------------------------------------------------------------------

    def test_create_case_from_story_santos(self):
        """_create_case_from_story should create a case for the Santos story."""
        from ..models.case_demo_stories import get_case_story_by_id

        story = get_case_story_by_id("santos_family_support")
        fake = self._fake()
        case = self.gen._create_case_from_story(story, fake, [self.client])
        self.assertTrue(case)
        self.assertTrue(case.id)

    def test_create_case_from_story_emergency(self):
        """_create_case_from_story should handle the emergency story without error."""
        from ..models.case_demo_stories import get_case_story_by_id

        story = get_case_story_by_id("dela_cruz_emergency")
        fake = self._fake()
        case = self.gen._create_case_from_story(story, fake, [self.client])
        self.assertTrue(case)

    def test_create_case_from_story_garcia_elder_care(self):
        """_create_case_from_story should handle the Garcia story with referral action."""
        from ..models.case_demo_stories import get_case_story_by_id

        story = get_case_story_by_id("garcia_elder_care")
        fake = self._fake()
        case = self.gen._create_case_from_story(story, fake, [self.client])
        self.assertTrue(case)

    def test_create_case_from_story_sets_case_type(self):
        """Created case should have the case_type specified in the story."""
        from ..models.case_demo_stories import get_case_story_by_id

        story = get_case_story_by_id("santos_family_support")
        fake = self._fake()
        case = self.gen._create_case_from_story(story, fake, [self.client])
        self.assertTrue(case.case_type_id)

    def test_create_case_from_story_sets_opened_date(self):
        """Created case should have an opened_date based on the intake step."""
        from ..models.case_demo_stories import get_case_story_by_id

        story = get_case_story_by_id("santos_family_support")
        fake = self._fake()
        case = self.gen._create_case_from_story(story, fake, [self.client])
        self.assertTrue(case.opened_date)

    def test_create_case_from_story_closed_story_has_closure_date(self):
        """A story with a close_case step should result in a case with closure date set."""
        from ..models.case_demo_stories import get_case_story_by_id

        story = get_case_story_by_id("santos_family_support")
        fake = self._fake()
        case = self.gen._create_case_from_story(story, fake, [self.client])
        # Santos story has a close_case step
        self.assertTrue(case.actual_closure_date)


@tagged("post_install", "-at_install")
class TestCaseDemoGeneratorAddHelpers(TransactionCase):
    """Tests for _add_random_plan, _add_random_visits, _add_random_notes, _close_random_case."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Stage = cls.env["spp.case.stage"]
        stage_data = [
            ("Intake", "intake", 10, False),
            ("Closure", "closure", 60, True),
        ]
        for name, phase, sequence, is_closed in stage_data:
            if not Stage.search([("phase", "=", phase)], limit=1):
                Stage.create({"name": name, "phase": phase, "sequence": sequence, "is_closed": is_closed})

        CaseType = cls.env["spp.case.type"]
        if not CaseType.search([("name", "=", "General Support")], limit=1):
            CaseType.create({"name": "General Support", "code": "GEN3"})

        cls.client = (
            cls.env["res.partner"]
            .with_context(tracking_disable=True)
            .create({"name": "Add Helper Client", "is_registrant": True})
        )

        case_type = CaseType.search([("name", "=", "General Support")], limit=1)
        stage = Stage.search([("phase", "=", "intake")], limit=1)
        cls.test_case = (
            cls.env["spp.case"]
            .sudo()
            .create(
                {
                    "case_type_id": case_type.id,
                    "stage_id": stage.id,
                    "partner_id": cls.client.id,
                    "presenting_issue": "Helper tests",
                    "case_worker_id": cls.env.user.id,
                }
            )
        )

        cls.gen = cls.env["spp.case.demo.generator"].create(
            {
                "name": "Add Helper Gen",
                "number_of_cases": 1,
                "include_stories": False,
                "link_to_beneficiaries": True,
                "percentage_with_plans": 0.0,
                "percentage_with_visits": 0.0,
                "percentage_with_notes": 0.0,
                "percentage_closed": 0.0,
            }
        )

    def _fake(self):
        from faker import Faker

        return Faker("en_US")

    def test_add_random_plan_creates_plan_with_interventions(self):
        """_add_random_plan should create one plan with 2-4 interventions."""
        from odoo import fields

        fake = self._fake()
        intake_date = fields.Date.today()
        self.gen._add_random_plan(self.test_case, fake, intake_date)
        plans = self.env["spp.case.intervention.plan"].search([("case_id", "=", self.test_case.id)])
        self.assertTrue(len(plans) >= 1)
        for plan in plans:
            interventions = self.env["spp.case.intervention"].search([("plan_id", "=", plan.id)])
            self.assertGreaterEqual(len(interventions), 2)
            self.assertLessEqual(len(interventions), 4)

    def test_add_random_visits_creates_visits(self):
        """_add_random_visits should create 1-3 visits on the case."""
        from odoo import fields

        fake = self._fake()
        intake_date = fields.Date.today()
        count_before = self.env["spp.case.visit"].search_count([("case_id", "=", self.test_case.id)])
        self.gen._add_random_visits(self.test_case, fake, intake_date)
        count_after = self.env["spp.case.visit"].search_count([("case_id", "=", self.test_case.id)])
        added = count_after - count_before
        self.assertGreaterEqual(added, 1)
        self.assertLessEqual(added, 3)

    def test_add_random_notes_creates_notes(self):
        """_add_random_notes should create 1-4 notes on the case."""
        from odoo import fields

        fake = self._fake()
        intake_date = fields.Date.today()
        count_before = self.env["spp.case.note"].search_count([("case_id", "=", self.test_case.id)])
        self.gen._add_random_notes(self.test_case, fake, intake_date)
        count_after = self.env["spp.case.note"].search_count([("case_id", "=", self.test_case.id)])
        added = count_after - count_before
        self.assertGreaterEqual(added, 1)
        self.assertLessEqual(added, 4)

    def test_close_random_case_moves_to_closure_stage(self):
        """_close_random_case should move the case to closure stage and set closure date."""
        from odoo import fields

        fake = self._fake()
        intake_date = fields.Date.today()
        closure_stage = self.env["spp.case.stage"].search([("phase", "=", "closure")], limit=1)
        self.gen._close_random_case(self.test_case, fake, intake_date)
        if closure_stage:
            self.assertEqual(self.test_case.stage_id.id, closure_stage.id)
            self.assertTrue(self.test_case.actual_closure_date)

    def test_close_random_case_does_nothing_without_closure_stage(self):
        """_close_random_case should not raise even if no closure stage is configured."""
        from odoo import fields

        fake = self._fake()
        intake_date = fields.Date.today()
        with patch.object(
            type(self.env["spp.case.stage"]),
            "search",
            return_value=self.env["spp.case.stage"],
        ):
            try:
                self.gen._close_random_case(self.test_case, fake, intake_date)
            except Exception as exc:
                self.fail(f"_close_random_case raised unexpectedly: {exc}")

    def test_add_random_plan_completed_plan_is_not_current(self):
        """A demo plan that lands on "completed" must not stay the current plan.

        ``_add_random_plan`` used to pass ``state="completed"`` straight to
        ``create()`` alongside ``is_current=True``, seeding the exact state
        spp_case_base #458 reports. The state is forced here rather than relied
        on: the generator picks it at random.
        """
        from odoo import fields

        real_choice = random.choice

        def always_completed(seq):
            """Force the plan-state draw only; leave every other draw random."""
            if list(seq) == ["draft", "active", "completed"]:
                return "completed"
            return real_choice(seq)

        with patch.object(random, "choice", side_effect=always_completed):
            self.gen._add_random_plan(self.test_case, self._fake(), fields.Date.today())

        plan = self.env["spp.case.intervention.plan"].search([("case_id", "=", self.test_case.id)], limit=1)
        self.assertTrue(plan, "_add_random_plan should have produced a plan")
        self.assertEqual(plan.state, "completed", "Test premise: the forced draw lands on completed")
        self.assertTrue(plan.actual_end_date, "Completing through the action should stamp actual_end_date")
        self.assertFalse(plan.is_current, "A completed plan is not the case's current plan")
        self.assertTrue(plan.intervention_ids, "Interventions should be added before the plan completes")
