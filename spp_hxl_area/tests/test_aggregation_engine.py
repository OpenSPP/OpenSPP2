# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

from ..services.aggregation_engine import AggregationEngine
from ..services.area_matcher import AreaMatcher


@tagged("post_install", "-at_install")
class TestAggregationEngine(TransactionCase):
    """Test Aggregation Engine service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Area = cls.env["spp.area"]
        cls.Profile = cls.env["spp.hxl.import.profile"]
        cls.Rule = cls.env["spp.hxl.aggregation.rule"]

        # Create test areas
        cls.area1 = cls.Area.create(
            {
                "draft_name": "Area 1",
                "code": "A1",
                "level": 2,
            }
        )

        cls.area2 = cls.Area.create(
            {
                "draft_name": "Area 2",
                "code": "A2",
                "level": 2,
            }
        )

        # Create profile
        cls.profile = cls.Profile.create(
            {
                "name": "Test Profile",
                "code": "test_profile",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
                "area_level": 2,
            }
        )

    def test_count_aggregation(self):
        """Test count aggregation type."""
        self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Count All",
                "aggregation_type": "count",
                "output_hxl_tag": "#meta+count",
            }
        )

        matcher = AreaMatcher(self.env, strategy="pcode", level=2)
        engine = AggregationEngine(self.env, self.profile, matcher)

        rows = [
            {"#adm2+pcode": "A1", "#value": "10"},
            {"#adm2+pcode": "A1", "#value": "20"},
            {"#adm2+pcode": "A2", "#value": "30"},
        ]

        indicators, unmatched = engine.aggregate(rows, {})

        self.assertEqual(len(indicators), 2)
        self.assertEqual(len(unmatched), 0)

        # Area 1 should have count of 2
        area1_ind = next(ind for ind in indicators if ind["area_id"] == self.area1.id)
        self.assertEqual(area1_ind["value"], 2)

        # Area 2 should have count of 1
        area2_ind = next(ind for ind in indicators if ind["area_id"] == self.area2.id)
        self.assertEqual(area2_ind["value"], 1)

    def test_sum_aggregation(self):
        """Test sum aggregation type."""
        self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Sum Values",
                "aggregation_type": "sum",
                "source_column_tag": "#value",
                "output_hxl_tag": "#value+sum",
            }
        )

        matcher = AreaMatcher(self.env, strategy="pcode", level=2)
        engine = AggregationEngine(self.env, self.profile, matcher)

        rows = [
            {"#adm2+pcode": "A1", "#value": "10"},
            {"#adm2+pcode": "A1", "#value": "20"},
            {"#adm2+pcode": "A2", "#value": "30"},
        ]

        indicators, unmatched = engine.aggregate(rows, {})

        self.assertEqual(len(indicators), 2)

        # Area 1 should have sum of 30
        area1_ind = next(ind for ind in indicators if ind["area_id"] == self.area1.id)
        self.assertEqual(area1_ind["value"], 30.0)

        # Area 2 should have sum of 30
        area2_ind = next(ind for ind in indicators if ind["area_id"] == self.area2.id)
        self.assertEqual(area2_ind["value"], 30.0)

    def test_avg_aggregation(self):
        """Test average aggregation type."""
        self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Average Values",
                "aggregation_type": "avg",
                "source_column_tag": "#value",
                "output_hxl_tag": "#value+avg",
            }
        )

        matcher = AreaMatcher(self.env, strategy="pcode", level=2)
        engine = AggregationEngine(self.env, self.profile, matcher)

        rows = [
            {"#adm2+pcode": "A1", "#value": "10"},
            {"#adm2+pcode": "A1", "#value": "20"},
            {"#adm2+pcode": "A2", "#value": "30"},
        ]

        indicators, unmatched = engine.aggregate(rows, {})

        # Area 1 should have avg of 15
        area1_ind = next(ind for ind in indicators if ind["area_id"] == self.area1.id)
        self.assertEqual(area1_ind["value"], 15.0)

        # Area 2 should have avg of 30
        area2_ind = next(ind for ind in indicators if ind["area_id"] == self.area2.id)
        self.assertEqual(area2_ind["value"], 30.0)

    def test_min_max_aggregation(self):
        """Test min and max aggregation types."""
        rule_min = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Min Value",
                "aggregation_type": "min",
                "source_column_tag": "#value",
                "output_hxl_tag": "#value+min",
                "sequence": 10,
            }
        )

        rule_max = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Max Value",
                "aggregation_type": "max",
                "source_column_tag": "#value",
                "output_hxl_tag": "#value+max",
                "sequence": 20,
            }
        )

        matcher = AreaMatcher(self.env, strategy="pcode", level=2)
        engine = AggregationEngine(self.env, self.profile, matcher)

        rows = [
            {"#adm2+pcode": "A1", "#value": "10"},
            {"#adm2+pcode": "A1", "#value": "50"},
            {"#adm2+pcode": "A1", "#value": "30"},
        ]

        indicators, unmatched = engine.aggregate(rows, {})

        self.assertEqual(len(indicators), 2)  # 2 rules

        # Check min
        min_ind = next(ind for ind in indicators if ind["rule_id"] == rule_min.id)
        self.assertEqual(min_ind["value"], 10.0)

        # Check max
        max_ind = next(ind for ind in indicators if ind["rule_id"] == rule_max.id)
        self.assertEqual(max_ind["value"], 50.0)

    def test_filter_expression(self):
        """Test aggregation with filter expression."""
        self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Count Severe",
                "aggregation_type": "count",
                "filter_expression": "row.get('#severity') == 'severe'",
                "output_hxl_tag": "#count+severe",
            }
        )

        matcher = AreaMatcher(self.env, strategy="pcode", level=2)
        engine = AggregationEngine(self.env, self.profile, matcher)

        rows = [
            {"#adm2+pcode": "A1", "#severity": "severe"},
            {"#adm2+pcode": "A1", "#severity": "minor"},
            {"#adm2+pcode": "A1", "#severity": "severe"},
            {"#adm2+pcode": "A2", "#severity": "severe"},
        ]

        indicators, unmatched = engine.aggregate(rows, {})

        # Area 1 should have 2 severe (filtered from 3)
        area1_ind = next(ind for ind in indicators if ind["area_id"] == self.area1.id)
        self.assertEqual(area1_ind["value"], 2)

        # Area 2 should have 1 severe
        area2_ind = next(ind for ind in indicators if ind["area_id"] == self.area2.id)
        self.assertEqual(area2_ind["value"], 1)

    def test_unmatched_areas(self):
        """Test handling of unmatched area values."""
        self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Count All",
                "aggregation_type": "count",
            }
        )

        matcher = AreaMatcher(self.env, strategy="pcode", level=2)
        engine = AggregationEngine(self.env, self.profile, matcher)

        rows = [
            {"#adm2+pcode": "A1", "#value": "10"},
            {"#adm2+pcode": "NONEXIST", "#value": "20"},
            {"#adm2+pcode": "A2", "#value": "30"},
            {"#adm2+pcode": "ANOTHER_BAD", "#value": "40"},
        ]

        indicators, unmatched = engine.aggregate(rows, {})

        self.assertEqual(len(indicators), 2)  # Only A1 and A2
        self.assertEqual(len(unmatched), 2)  # Two unmatched

    def test_multiple_rules_per_area(self):
        """Test multiple aggregation rules on same data."""
        rule1 = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Count All",
                "aggregation_type": "count",
                "sequence": 10,
            }
        )

        rule2 = self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Sum Values",
                "aggregation_type": "sum",
                "source_column_tag": "#value",
                "sequence": 20,
            }
        )

        matcher = AreaMatcher(self.env, strategy="pcode", level=2)
        engine = AggregationEngine(self.env, self.profile, matcher)

        rows = [
            {"#adm2+pcode": "A1", "#value": "10"},
            {"#adm2+pcode": "A1", "#value": "20"},
        ]

        indicators, unmatched = engine.aggregate(rows, {})

        # Should have 2 indicators (1 per rule) for area A1
        self.assertEqual(len(indicators), 2)

        count_ind = next(ind for ind in indicators if ind["rule_id"] == rule1.id)
        sum_ind = next(ind for ind in indicators if ind["rule_id"] == rule2.id)

        self.assertEqual(count_ind["value"], 2)
        self.assertEqual(sum_ind["value"], 30.0)

    def test_to_float_conversion(self):
        """Test the _to_float helper method."""
        engine = AggregationEngine(self.env, self.profile, None)

        # Test various formats
        self.assertEqual(engine._to_float(None), 0.0)
        self.assertEqual(engine._to_float(""), 0.0)
        self.assertEqual(engine._to_float("123"), 123.0)
        self.assertEqual(engine._to_float("123.45"), 123.45)
        self.assertEqual(engine._to_float("1,234.56"), 1234.56)
        self.assertEqual(engine._to_float("1 234"), 1234.0)
        self.assertEqual(engine._to_float(42), 42.0)
        self.assertEqual(engine._to_float(42.5), 42.5)

    def test_count_distinct_aggregation(self):
        """Test count distinct aggregation type."""
        self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Unique Organizations",
                "aggregation_type": "count_distinct",
                "source_column_tag": "#org",
                "output_hxl_tag": "#org+count",
            }
        )

        matcher = AreaMatcher(self.env, strategy="pcode", level=2)
        engine = AggregationEngine(self.env, self.profile, matcher)

        rows = [
            {"#adm2+pcode": "A1", "#org": "Org A"},
            {"#adm2+pcode": "A1", "#org": "Org B"},
            {"#adm2+pcode": "A1", "#org": "Org A"},  # Duplicate
            {"#adm2+pcode": "A2", "#org": "Org C"},
        ]

        indicators, unmatched = engine.aggregate(rows, {})

        # Area 1 should have 2 distinct orgs
        area1_ind = next(ind for ind in indicators if ind["area_id"] == self.area1.id)
        self.assertEqual(area1_ind["value"], 2)

        # Area 2 should have 1 distinct org
        area2_ind = next(ind for ind in indicators if ind["area_id"] == self.area2.id)
        self.assertEqual(area2_ind["value"], 1)

    def test_percentage_aggregation(self):
        """Test percentage aggregation type."""
        self.Rule.create(
            {
                "profile_id": self.profile.id,
                "name": "Percentage Severe",
                "aggregation_type": "percentage",
                "filter_expression": "row.get('#severity') == 'severe'",
                "output_hxl_tag": "#pct+severe",
            }
        )

        matcher = AreaMatcher(self.env, strategy="pcode", level=2)
        engine = AggregationEngine(self.env, self.profile, matcher)

        rows = [
            {"#adm2+pcode": "A1", "#severity": "severe"},
            {"#adm2+pcode": "A1", "#severity": "minor"},
            {"#adm2+pcode": "A1", "#severity": "severe"},
            {"#adm2+pcode": "A1", "#severity": "minor"},
        ]

        indicators, unmatched = engine.aggregate(rows, {})

        # Area 1: 2 out of 4 = 50%
        area1_ind = next(ind for ind in indicators if ind["area_id"] == self.area1.id)
        self.assertEqual(area1_ind["value"], 50.0)

    def test_has_attribute_exact_match(self):
        """Test _has_attribute matches exact attribute names."""
        engine = AggregationEngine(self.env, self.profile, None)

        # Column with +f attribute
        hxl_columns = {"#affected+f": "Female Affected"}
        row = {"#affected+f": "100"}

        # Should match +f
        self.assertTrue(engine._has_attribute(row, "+f", hxl_columns))
        self.assertTrue(engine._has_attribute(row, "f", hxl_columns))

        # Should NOT match +m (not present)
        self.assertFalse(engine._has_attribute(row, "+m", hxl_columns))

    def test_has_attribute_no_false_positives(self):
        """Test _has_attribute doesn't match partial attribute names."""
        engine = AggregationEngine(self.env, self.profile, None)

        # Column #affected should NOT match attribute +f
        hxl_columns = {"#affected": "Total Affected"}
        row = {"#affected": "100"}

        # Should NOT match +f - the 'f' in 'affected' is not an attribute
        self.assertFalse(engine._has_attribute(row, "+f", hxl_columns))

    def test_has_attribute_multiple_attributes(self):
        """Test _has_attribute with multiple attributes on a tag."""
        engine = AggregationEngine(self.env, self.profile, None)

        # Column with multiple attributes: #affected+f+elderly
        hxl_columns = {"#affected+f+elderly": "Elderly Female Affected"}
        row = {"#affected+f+elderly": "50"}

        # Should match both +f and +elderly
        self.assertTrue(engine._has_attribute(row, "+f", hxl_columns))
        self.assertTrue(engine._has_attribute(row, "+elderly", hxl_columns))
        self.assertTrue(engine._has_attribute(row, "elderly", hxl_columns))

        # Should NOT match attributes not in the tag
        self.assertFalse(engine._has_attribute(row, "+m", hxl_columns))
        self.assertFalse(engine._has_attribute(row, "+child", hxl_columns))

    def test_has_attribute_empty_value(self):
        """Test _has_attribute returns False for empty/zero values."""
        engine = AggregationEngine(self.env, self.profile, None)

        hxl_columns = {"#affected+f": "Female Affected"}

        # Empty value should return False
        row_empty = {"#affected+f": ""}
        self.assertFalse(engine._has_attribute(row_empty, "+f", hxl_columns))

        # Zero value should return False
        row_zero = {"#affected+f": "0"}
        self.assertFalse(engine._has_attribute(row_zero, "+f", hxl_columns))

        # Whitespace only should return False
        row_whitespace = {"#affected+f": "   "}
        self.assertFalse(engine._has_attribute(row_whitespace, "+f", hxl_columns))

    def test_has_attribute_multiple_columns(self):
        """Test _has_attribute scans all columns for the attribute."""
        engine = AggregationEngine(self.env, self.profile, None)

        # Multiple columns, one with +f attribute
        hxl_columns = {
            "#affected+m": "Male Affected",
            "#affected+f": "Female Affected",
            "#population": "Total Population",
        }
        row = {
            "#affected+m": "50",
            "#affected+f": "60",
            "#population": "200",
        }

        # Should find +f in the second column
        self.assertTrue(engine._has_attribute(row, "+f", hxl_columns))
        # Should find +m in the first column
        self.assertTrue(engine._has_attribute(row, "+m", hxl_columns))
