# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHxlImportProfile(TransactionCase):
    """Test HXL Import Profile model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Profile = cls.env["spp.hxl.import.profile"]
        cls.Rule = cls.env["spp.hxl.aggregation.rule"]
        cls.Variable = cls.env["spp.cel.variable"]

    def test_create_profile(self):
        """Test creating a basic import profile."""
        profile = self.Profile.create(
            {
                "name": "Test Profile",
                "code": "test_profile",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
                "area_level": 2,
            }
        )

        self.assertEqual(profile.name, "Test Profile")
        self.assertEqual(profile.code, "test_profile")
        self.assertEqual(profile.area_matching_strategy, "pcode")

    def test_profile_code_uniqueness(self):
        """Test that profile codes must be unique."""
        self.Profile.create(
            {
                "name": "Profile 1",
                "code": "unique_code",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
            }
        )

        with self.assertRaises(Exception):
            self.Profile.create(
                {
                    "name": "Profile 2",
                    "code": "unique_code",
                    "area_matching_strategy": "pcode",
                    "area_column_tag": "#adm2+pcode",
                }
            )

    def test_validate_configuration_missing_area_tag(self):
        """Test validation fails when area column tag is missing."""
        profile = self.Profile.create(
            {
                "name": "Invalid Profile",
                "code": "invalid_1",
                "area_matching_strategy": "pcode",
                "area_column_tag": "",
            }
        )

        with self.assertRaises(ValidationError):
            profile.validate_configuration()

    def test_validate_configuration_gps_missing_coords(self):
        """Test validation fails for GPS strategy without lat/lon tags."""
        profile = self.Profile.create(
            {
                "name": "GPS Profile",
                "code": "gps_test",
                "area_matching_strategy": "gps",
                "area_column_tag": "#geo+lat",
                "latitude_tag": "",
                "longitude_tag": "",
            }
        )

        with self.assertRaises(ValidationError):
            profile.validate_configuration()

    def test_validate_configuration_no_rules(self):
        """Test validation fails when no aggregation rules defined."""
        profile = self.Profile.create(
            {
                "name": "No Rules Profile",
                "code": "no_rules",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
            }
        )

        with self.assertRaises(ValidationError):
            profile.validate_configuration()

    def test_validate_configuration_success(self):
        """Test successful validation with all required fields."""
        profile = self.Profile.create(
            {
                "name": "Valid Profile",
                "code": "valid_profile",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
                "area_level": 2,
            }
        )

        # Add a rule
        self.Rule.create(
            {
                "profile_id": profile.id,
                "name": "Test Rule",
                "aggregation_type": "count",
            }
        )

        # Should not raise
        result = profile.validate_configuration()
        self.assertTrue(result)

    def test_batch_count_computation(self):
        """Test that batch count is computed correctly."""
        profile = self.Profile.create(
            {
                "name": "Profile with Batches",
                "code": "batch_test",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
            }
        )

        self.assertEqual(profile.batch_count, 0)

        # Create batches
        Batch = self.env["spp.hxl.import.batch"]
        Batch.create(
            {
                "name": "Batch 1",
                "profile_id": profile.id,
            }
        )
        Batch.create(
            {
                "name": "Batch 2",
                "profile_id": profile.id,
            }
        )

        profile._compute_batch_count()
        self.assertEqual(profile.batch_count, 2)

    def test_profile_with_aggregation_rules(self):
        """Test creating profile with multiple aggregation rules."""
        profile = self.Profile.create(
            {
                "name": "Multi-Rule Profile",
                "code": "multi_rule",
                "area_matching_strategy": "name",
                "area_column_tag": "#adm3+name",
                "area_level": 3,
            }
        )

        # Create rules
        rule1 = self.Rule.create(
            {
                "profile_id": profile.id,
                "name": "Count All",
                "aggregation_type": "count",
                "output_hxl_tag": "#meta+count",
                "sequence": 10,
            }
        )

        rule2 = self.Rule.create(
            {
                "profile_id": profile.id,
                "name": "Sum Values",
                "aggregation_type": "sum",
                "source_column_tag": "#affected+ind",
                "output_hxl_tag": "#affected+ind+total",
                "sequence": 20,
            }
        )

        self.assertEqual(len(profile.aggregation_ids), 2)
        self.assertEqual(profile.aggregation_ids[0], rule1)
        self.assertEqual(profile.aggregation_ids[1], rule2)

    def test_action_view_batches(self):
        """Test the action to view batches."""
        profile = self.Profile.create(
            {
                "name": "View Test Profile",
                "code": "view_test",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
            }
        )

        action = profile.action_view_batches()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.hxl.import.batch")
        self.assertEqual(action["domain"], [("profile_id", "=", profile.id)])
