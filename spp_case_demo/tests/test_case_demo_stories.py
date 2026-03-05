# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for case_demo_stories module - pure Python, no Odoo model access needed."""

from odoo.tests import TransactionCase, tagged

from ..models.case_demo_stories import (
    BACKGROUND_CASES,
    CASE_DEMO_STORIES,
    RESERVED_CASE_NAMES,
    get_all_case_stories,
    get_background_case_stories,
    get_case_story_by_id,
    get_main_case_stories,
)


@tagged("post_install", "-at_install")
class TestCaseDemoStories(TransactionCase):
    """Tests for the demo stories data module."""

    def test_case_demo_stories_list_not_empty(self):
        """The main stories list should have entries."""
        self.assertTrue(CASE_DEMO_STORIES, "CASE_DEMO_STORIES must not be empty")

    def test_background_cases_list_not_empty(self):
        """The background cases list should have entries."""
        self.assertTrue(BACKGROUND_CASES, "BACKGROUND_CASES must not be empty")

    def test_reserved_case_names_not_empty(self):
        """Reserved names list should have entries."""
        self.assertTrue(RESERVED_CASE_NAMES, "RESERVED_CASE_NAMES must not be empty")

    def test_each_main_story_has_required_keys(self):
        """Every main story must have id, case_name, case_profile, and journey."""
        required_keys = {"id", "case_name", "case_profile", "journey"}
        for story in CASE_DEMO_STORIES:
            missing = required_keys - set(story.keys())
            self.assertFalse(
                missing,
                f"Story '{story.get('case_name', '?')}' is missing keys: {missing}",
            )

    def test_each_story_journey_is_list(self):
        """Every story's journey must be a list."""
        for story in get_all_case_stories():
            self.assertIsInstance(
                story["journey"],
                list,
                f"Journey for '{story.get('case_name', '?')}' must be a list",
            )

    def test_each_story_case_profile_is_dict(self):
        """Every story's case_profile must be a dict."""
        for story in get_all_case_stories():
            self.assertIsInstance(
                story["case_profile"],
                dict,
                f"case_profile for '{story.get('case_name', '?')}' must be a dict",
            )

    def test_story_ids_are_unique(self):
        """All story IDs must be unique."""
        all_ids = [s["id"] for s in get_all_case_stories()]
        self.assertEqual(
            len(all_ids),
            len(set(all_ids)),
            "Duplicate story IDs detected",
        )

    def test_get_main_case_stories_returns_main_list(self):
        """get_main_case_stories should return CASE_DEMO_STORIES."""
        result = get_main_case_stories()
        self.assertEqual(result, CASE_DEMO_STORIES)

    def test_get_background_case_stories_returns_background_list(self):
        """get_background_case_stories should return BACKGROUND_CASES."""
        result = get_background_case_stories()
        self.assertEqual(result, BACKGROUND_CASES)

    def test_get_all_case_stories_combines_both_lists(self):
        """get_all_case_stories should combine main and background stories."""
        all_stories = get_all_case_stories()
        expected_count = len(CASE_DEMO_STORIES) + len(BACKGROUND_CASES)
        self.assertEqual(len(all_stories), expected_count)

    def test_get_all_case_stories_main_stories_first(self):
        """Main stories should appear before background stories in the combined list."""
        all_stories = get_all_case_stories()
        main_count = len(CASE_DEMO_STORIES)
        self.assertEqual(all_stories[:main_count], CASE_DEMO_STORIES)
        self.assertEqual(all_stories[main_count:], BACKGROUND_CASES)

    def test_get_case_story_by_id_found(self):
        """get_case_story_by_id should return the correct story when it exists."""
        # Use the first story in main stories as a known ID
        first_story = CASE_DEMO_STORIES[0]
        result = get_case_story_by_id(first_story["id"])
        self.assertEqual(result, first_story)

    def test_get_case_story_by_id_background_story(self):
        """get_case_story_by_id should also find background case stories."""
        first_background = BACKGROUND_CASES[0]
        result = get_case_story_by_id(first_background["id"])
        self.assertEqual(result, first_background)

    def test_get_case_story_by_id_not_found_returns_none(self):
        """get_case_story_by_id should return None for an unknown ID."""
        result = get_case_story_by_id("this_id_does_not_exist_xyz")
        self.assertIsNone(result)

    def test_santos_family_support_story_exists(self):
        """The Santos Family Support story must exist by its known ID."""
        story = get_case_story_by_id("santos_family_support")
        self.assertIsNotNone(story)
        self.assertEqual(story["case_name"], "Santos Family Support")

    def test_dela_cruz_emergency_story_exists(self):
        """The Dela Cruz Emergency story must exist."""
        story = get_case_story_by_id("dela_cruz_emergency")
        self.assertIsNotNone(story)

    def test_garcia_elder_care_story_exists(self):
        """The Garcia Elder Care story must exist."""
        story = get_case_story_by_id("garcia_elder_care")
        self.assertIsNotNone(story)

    def test_mendoza_child_protection_story_exists(self):
        """The Mendoza Child Protection story must exist."""
        story = get_case_story_by_id("mendoza_child_protection")
        self.assertIsNotNone(story)

    def test_hassan_resettlement_story_exists(self):
        """The Hassan Resettlement story must exist."""
        story = get_case_story_by_id("hassan_resettlement")
        self.assertIsNotNone(story)

    def test_morales_household_crisis_story_exists(self):
        """The Morales Household Crisis story must exist."""
        story = get_case_story_by_id("morales_household_crisis")
        self.assertIsNotNone(story)

    def test_martinez_disability_support_story_exists(self):
        """The Martinez Disability Support story must exist."""
        story = get_case_story_by_id("martinez_disability_support")
        self.assertIsNotNone(story)

    def test_al_rahman_family_assessment_story_exists(self):
        """The Al-Rahman Family Assessment story must exist."""
        story = get_case_story_by_id("al_rahman_family_assessment")
        self.assertIsNotNone(story)

    def test_said_family_support_story_exists(self):
        """The Said Family Support story must exist."""
        story = get_case_story_by_id("said_family_support")
        self.assertIsNotNone(story)

    def test_story_journey_actions_are_strings(self):
        """Every journey step must have an action key that is a string."""
        for story in get_all_case_stories():
            for step in story["journey"]:
                self.assertIn("action", step, f"Journey step missing 'action' in story {story['id']}")
                self.assertIsInstance(step["action"], str)

    def test_story_journey_days_back_non_negative(self):
        """Journey steps that specify days_back must have a non-negative value."""
        for story in get_all_case_stories():
            for step in story["journey"]:
                if "days_back" in step:
                    self.assertGreaterEqual(
                        step["days_back"],
                        0,
                        f"days_back must be >= 0 in story '{story['id']}'",
                    )

    def test_santos_story_has_close_case_action(self):
        """The Santos story should include a close_case journey step."""
        story = get_case_story_by_id("santos_family_support")
        actions = [step["action"] for step in story["journey"]]
        self.assertIn("close_case", actions)

    def test_background_pending_intake_story(self):
        """The pending_intake background story must exist."""
        story = get_case_story_by_id("pending_intake")
        self.assertIsNotNone(story)

    def test_background_assessment_phase_story(self):
        """The assessment_phase background story must exist."""
        story = get_case_story_by_id("assessment_phase")
        self.assertIsNotNone(story)

    def test_background_closed_unsuccessful_story(self):
        """The closed_unsuccessful background story must exist and have a close_case step."""
        story = get_case_story_by_id("closed_unsuccessful")
        self.assertIsNotNone(story)
        actions = [step["action"] for step in story["journey"]]
        self.assertIn("close_case", actions)
