# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestDemoStories(TransactionCase):
    """Test the fixed demo stories generation functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set context to avoid job queue delay
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        # Create test country with faker locale (avoid ISO code collisions)
        country_code = "TS"
        if cls.env["res.country"].search_count([("code", "=", country_code)]):
            country_code = "XS"

        cls.test_country = cls.env["res.country"].create(
            {
                "name": "Test Country Demo Stories",
                "code": country_code,
                "faker_locale": "en_US",
                "is_faker_locale_available": True,
                "lat_min": -10.0,
                "lat_max": 10.0,
                "lon_min": -10.0,
                "lon_max": 10.0,
                "name_position": "before",
            }
        )

        # Get group type from vocabulary
        cls.group_type = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-type", "household")

    def test_01_demo_stories_module_import(self):
        """Test that demo_stories module can be imported."""
        from odoo.addons.spp_demo.models import demo_stories

        self.assertIsNotNone(demo_stories.DEMO_STORIES)
        self.assertIsNotNone(demo_stories.RESERVED_NAMES)
        self.assertGreater(len(demo_stories.DEMO_STORIES), 0)
        self.assertGreater(len(demo_stories.RESERVED_NAMES), 0)

    def test_02_get_all_stories(self):
        """Test get_all_stories function returns all stories."""
        from odoo.addons.spp_demo.models import demo_stories

        all_stories = demo_stories.get_all_stories()
        main_stories = demo_stories.get_main_stories()
        background_stories = demo_stories.get_background_stories()
        tutorial_stories = demo_stories.get_tutorial_stories()

        self.assertEqual(len(all_stories), len(main_stories) + len(background_stories) + len(tutorial_stories))
        self.assertGreater(len(main_stories), 0)

    def test_03_get_story_by_id(self):
        """Test get_story_by_id function."""
        from odoo.addons.spp_demo.models import demo_stories

        maria = demo_stories.get_story_by_id("maria_santos")
        self.assertIsNotNone(maria)
        self.assertEqual(maria["name"], "Maria Santos")

        nonexistent = demo_stories.get_story_by_id("nonexistent_story")
        self.assertIsNone(nonexistent)

    def test_04_get_story_by_name(self):
        """Test get_story_by_name function."""
        from odoo.addons.spp_demo.models import demo_stories

        juan = demo_stories.get_story_by_name("Juan Dela Cruz")
        self.assertIsNotNone(juan)
        self.assertEqual(juan["id"], "juan_dela_cruz")

        nonexistent = demo_stories.get_story_by_name("Nonexistent Person")
        self.assertIsNone(nonexistent)

    def test_05_story_structure(self):
        """Test that stories have required structure."""
        from odoo.addons.spp_demo.models import demo_stories

        for story in demo_stories.get_main_stories():
            self.assertIn("id", story)
            self.assertIn("name", story)
            self.assertIn("type", story)
            self.assertIn("profile", story)
            self.assertIsInstance(story["profile"], dict)

    def test_06_reserved_names_match_stories(self):
        """Test that reserved names match story names."""
        from odoo.addons.spp_demo.models import demo_stories

        all_stories = demo_stories.get_all_stories()
        story_names = [story["name"] for story in all_stories]

        # All story names should be in reserved names
        for name in story_names:
            self.assertIn(name, demo_stories.RESERVED_NAMES)

    def test_07_generate_stories_method_exists(self):
        """Test that generate_stories method exists on the generator model."""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Stories Method",
                "locale_origin": self.test_country.id,
            }
        )

        self.assertTrue(hasattr(generator, "generate_stories"))
        self.assertTrue(callable(generator.generate_stories))

    def test_08_generate_single_individual_story(self):
        """Test generating a single individual story."""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Individual Story",
                "locale_origin": self.test_country.id,
            }
        )

        # Create a simple individual story
        story = {
            "id": "test_individual",
            "name": "Test Individual Person",
            "type": "individual",
            "profile": {
                "gender": "female",
                "age": 30,
            },
            "journey": [{"action": "register", "days_back": 50}],
        }

        partner = generator._create_individual_story(story)

        self.assertIsNotNone(partner)
        self.assertEqual(partner.name, "Test Individual Person")
        self.assertTrue(partner.is_registrant)
        self.assertFalse(partner.is_group)
        self.assertEqual(partner.given_name, "Test")
        self.assertEqual(partner.family_name, "Individual Person")

    def test_09_generate_single_farmer_story(self):
        """Test generating a single farmer story."""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Farmer Story",
                "locale_origin": self.test_country.id,
            }
        )

        story = {
            "id": "test_farmer",
            "name": "Test Farmer Person",
            "type": "farmer",
            "profile": {
                "gender": "male",
                "age": 45,
                "farm_size": 3.0,
                "farm_type": "crop",
                "household_size": 5,
            },
            "journey": [{"action": "register", "days_back": 100}],
        }

        partner = generator._create_farmer_story(story)

        self.assertIsNotNone(partner)
        self.assertEqual(partner.name, "Test Farmer Person")
        self.assertTrue(partner.is_registrant)
        self.assertTrue(partner.is_group)

    def test_10_generate_stories_creates_all_main_stories(self):
        """Test that generate_stories creates all main stories."""
        from odoo.addons.spp_demo.models import demo_stories

        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Full Story Generation",
                "locale_origin": self.test_country.id,
            }
        )

        # Generate all stories
        created = generator.generate_stories()

        # Check that all main stories were created
        main_stories = demo_stories.get_main_stories()
        for story in main_stories:
            self.assertIn(story["id"], created)

            # Verify the partner exists
            partner = self.env["res.partner"].search(
                [("name", "=", story["name"]), ("is_registrant", "=", True)],
                limit=1,
            )
            self.assertTrue(partner, f"Partner '{story['name']}' not found")

    def test_11_generate_stories_idempotent(self):
        """Test that generate_stories is idempotent (doesn't create duplicates)."""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Idempotent Generation",
                "locale_origin": self.test_country.id,
            }
        )

        # Generate stories twice
        created1 = generator.generate_stories()
        created2 = generator.generate_stories()

        # Should return same number of stories
        self.assertEqual(len(created1), len(created2))

        # Check no duplicates
        maria_count = self.env["res.partner"].search_count(
            [("name", "=", "Maria Santos"), ("is_registrant", "=", True)]
        )
        self.assertEqual(maria_count, 1)

    def test_12_maria_santos_story(self):
        """Test Maria Santos story creation with expected attributes."""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Maria Santos",
                "locale_origin": self.test_country.id,
            }
        )

        generator.generate_stories()

        maria = self.env["res.partner"].search(
            [("name", "=", "Maria Santos"), ("is_registrant", "=", True)],
            limit=1,
        )

        self.assertTrue(maria)
        self.assertTrue(maria.is_group)  # Farmers are groups
        self.assertTrue(maria.is_registrant)

    def test_13_household_story_with_members(self):
        """Test household story creates group with members."""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Household Story",
                "locale_origin": self.test_country.id,
            }
        )

        generator.generate_stories()

        # Carlos Morales is a household head
        carlos = self.env["res.partner"].search(
            [("name", "=", "Carlos Morales"), ("is_registrant", "=", True)],
            limit=1,
        )

        self.assertTrue(carlos)
        self.assertTrue(carlos.is_group)

        # Check household members were created
        memberships = self.env["spp.group.membership"].search([("group", "=", carlos.id)])
        # Should have spouse + 3 children = 4 members (from the story definition)
        self.assertGreater(len(memberships), 0)

    def test_14_background_stories_created(self):
        """Test that background stories are also created."""
        from odoo.addons.spp_demo.models import demo_stories

        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Background Stories",
                "locale_origin": self.test_country.id,
            }
        )

        generator.generate_stories()

        # Check background stories
        background_stories = demo_stories.get_background_stories()
        for story in background_stories:
            partner = self.env["res.partner"].search(
                [("name", "=", story["name"]), ("is_registrant", "=", True)],
                limit=1,
            )
            self.assertTrue(partner, f"Background story '{story['name']}' not created")

    def test_15_story_registration_dates(self):
        """Test that story registration dates are set correctly based on journey."""
        from odoo import fields

        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Registration Dates",
                "locale_origin": self.test_country.id,
            }
        )

        generator.generate_stories()

        maria = self.env["res.partner"].search(
            [("name", "=", "Maria Santos"), ("is_registrant", "=", True)],
            limit=1,
        )

        # Maria's first action is 180 days back
        expected_date = fields.Date.today()
        self.assertIsNotNone(maria.registration_date)
        # Registration should be in the past
        self.assertLess(maria.registration_date, expected_date)
