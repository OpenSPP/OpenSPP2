# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHxlAggregationRule(TransactionCase):
    """Test HXL Aggregation Rule model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Rule = cls.env["spp.hxl.aggregation.rule"]
        cls.Profile = cls.env["spp.hxl.import.profile"]
        cls.Variable = cls.env["spp.cel.variable"]

        # Create test profile
        cls.profile = cls.Profile.create(
            {
                "name": "Test Profile",
                "code": "test_agg_rule_profile",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
            }
        )

    def test_create_rule(self):
        """Test creating a basic aggregation rule."""
        rule = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Count Households",
                "aggregation_type": "count",
            }
        )

        self.assertEqual(rule.name, "Count Households")
        self.assertEqual(rule.aggregation_type, "count")
        self.assertEqual(rule.profile_id, self.profile)

    def test_required_fields(self):
        """Test that required fields are enforced."""
        # profile_id is required
        with self.assertRaises(Exception):
            self.Rule.create(
                {
                    "name": "Test Rule",
                    "aggregation_type": "count",
                }
            )

        # name is required
        with self.assertRaises(Exception):
            self.Rule.create(
                {
                    "profile_id": self.profile.id,
                    "aggregation_type": "count",
                }
            )

    def test_default_values(self):
        """Test default values are set correctly."""
        rule = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Default Test",
                "aggregation_type": "sum",
            }
        )

        self.assertEqual(rule.sequence, 10)
        self.assertEqual(rule.aggregation_type, "sum")
        self.assertTrue(rule.active)

    def test_ordering(self):
        """Test rules are ordered by profile_id and sequence."""
        rule1 = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Rule 1",
                "aggregation_type": "count",
                "sequence": 20,
            }
        )

        rule2 = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Rule 2",
                "aggregation_type": "sum",
                "sequence": 5,
            }
        )

        rules = self.Rule.search([("profile_id", "=", self.profile.id)])

        # Rule2 (sequence 5) should come before Rule1 (sequence 20)
        self.assertEqual(rules[0], rule2)
        self.assertEqual(rules[1], rule1)

    def test_all_aggregation_types(self):
        """Test all aggregation type selections."""
        types = [
            "count",
            "sum",
            "avg",
            "min",
            "max",
            "count_distinct",
            "percentage",
        ]

        for agg_type in types:
            rule = self.Rule.create(
                {
                    "profile_id": self.profile.id,
                    "name": f"Test {agg_type}",
                    "aggregation_type": agg_type,
                }
            )
            self.assertEqual(rule.aggregation_type, agg_type)

    def test_variable_linking(self):
        """Test linking rule to CEL variable."""
        # Get or create a variable
        variable = self.Variable.search([], limit=1)
        if not variable:
            variable = self.Variable.create(
                {
                    "name": "test_variable",
                    "label": "Test Variable",
                    "data_type": "number",
                }
            )

        rule = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Variable Linked Rule",
                "aggregation_type": "sum",
                "variable_id": variable.id,
            }
        )

        self.assertEqual(rule.variable_id, variable)

    def test_name_get_display(self):
        """Test name_get returns profile code with name."""
        rule = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Test Display",
                "aggregation_type": "count",
            }
        )

        result = rule.name_get()

        # Should return [(id, 'profile_code: rule_name')]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], rule.id)
        self.assertIn(self.profile.code, result[0][1])
        self.assertIn("Test Display", result[0][1])

    def test_cascade_deletion(self):
        """Test rule is deleted when profile is deleted."""
        # Create a new profile for this test
        profile = self.Profile.create(
            {
                "name": "Cascade Test Profile",
                "code": "cascade_test",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
            }
        )

        rule = self.Rule.create(
            {
                "profile_id": profile.id,
                "name": "Cascade Rule",
                "aggregation_type": "count",
            }
        )
        rule_id = rule.id

        # Delete profile
        profile.unlink()

        # Rule should be deleted
        rule_check = self.Rule.browse(rule_id)
        self.assertFalse(rule_check.exists())

    def test_disaggregate_by_tags(self):
        """Test disaggregation tags field."""
        rule = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Disaggregate Test",
                "aggregation_type": "count",
                "disaggregate_by_tags": "+f,+m,+children",
            }
        )

        self.assertEqual(rule.disaggregate_by_tags, "+f,+m,+children")

    def test_filter_expression_storage(self):
        """Test filter expression field."""
        rule = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Filter Test",
                "aggregation_type": "count",
                "filter_expression": "row.get('severity') == 'severe'",
            }
        )

        self.assertEqual(rule.filter_expression, "row.get('severity') == 'severe'")

    def test_output_hxl_tag(self):
        """Test output HXL tag field."""
        rule = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Output Tag Test",
                "aggregation_type": "sum",
                "source_column_tag": "#affected+hh",
                "output_hxl_tag": "#affected+hh+sum",
            }
        )

        self.assertEqual(rule.source_column_tag, "#affected+hh")
        self.assertEqual(rule.output_hxl_tag, "#affected+hh+sum")

    def test_active_toggle(self):
        """Test active field toggles correctly."""
        rule = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Active Test",
                "aggregation_type": "count",
            }
        )

        self.assertTrue(rule.active)

        rule.active = False
        self.assertFalse(rule.active)

        rule.active = True
        self.assertTrue(rule.active)
