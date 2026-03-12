# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for CEL Variable event aggregation extension."""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCELVariableEventAggregation(TransactionCase):
    """Tests for event aggregation in CEL variables."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CELVariable = cls.env["spp.cel.variable"]
        cls.EventType = cls.env["spp.event.type"]
        cls.Category = cls.env["spp.cel.variable.category"]

        # Create a test category
        cls.category = cls.Category.create(
            {
                "name": "Test Category",
                "code": "test_cat",
            }
        )

        # Create a test event type
        cls.event_type = cls.EventType.create(
            {
                "name": "Payment Event",
                "code": "payment",
                "target_type": "individual",
                "category": "manual",
            }
        )

    def test_aggregate_target_includes_events(self):
        """Test that events is a valid aggregate_target option."""
        variable = self.CELVariable.create(
            {
                "name": "test_event_count",
                "cel_accessor": "event_count",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "count",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
            }
        )
        self.assertEqual(variable.aggregate_target, "events")

    def test_event_count_cel_expression(self):
        """Test CEL expression generation for event count."""
        variable = self.CELVariable.create(
            {
                "name": "test_payment_count",
                "cel_accessor": "payment_count",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "count",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
            }
        )
        self.assertEqual(variable.cel_expression, "events_count('payment')")

    def test_event_exists_cel_expression(self):
        """Test CEL expression generation for event exists."""
        variable = self.CELVariable.create(
            {
                "name": "test_has_payment",
                "cel_accessor": "has_payment",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "exists",
                "value_type": "boolean",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
            }
        )
        self.assertEqual(variable.cel_expression, "has_event('payment')")

    def test_event_sum_cel_expression(self):
        """Test CEL expression generation for event sum."""
        variable = self.CELVariable.create(
            {
                "name": "test_total_amount",
                "cel_accessor": "total_amount",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "sum",
                "value_type": "money",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_field": "amount",
            }
        )
        self.assertEqual(variable.cel_expression, "events_sum('payment', 'amount')")

    def test_event_avg_cel_expression(self):
        """Test CEL expression generation for event average."""
        variable = self.CELVariable.create(
            {
                "name": "test_avg_score",
                "cel_accessor": "avg_score",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "avg",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_field": "score",
            }
        )
        self.assertEqual(variable.cel_expression, "events_avg('payment', 'score')")

    def test_event_temporal_this_year(self):
        """Test CEL expression with this_year temporal filter."""
        variable = self.CELVariable.create(
            {
                "name": "test_ytd_count",
                "cel_accessor": "ytd_count",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "count",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_temporal": "this_year",
            }
        )
        self.assertEqual(
            variable.cel_expression,
            "events_count('payment', period=this_year())",
        )

    def test_event_temporal_this_quarter(self):
        """Test CEL expression with this_quarter temporal filter."""
        variable = self.CELVariable.create(
            {
                "name": "test_qtd_sum",
                "cel_accessor": "qtd_sum",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "sum",
                "value_type": "money",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_temporal": "this_quarter",
                "event_agg_field": "amount",
            }
        )
        self.assertEqual(
            variable.cel_expression,
            "events_sum('payment', 'amount', period=this_quarter())",
        )

    def test_event_temporal_within_days(self):
        """Test CEL expression with within_days temporal filter."""
        variable = self.CELVariable.create(
            {
                "name": "test_recent_count",
                "cel_accessor": "recent_count",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "count",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_temporal": "within_days",
                "event_agg_temporal_value": 90,
            }
        )
        self.assertEqual(
            variable.cel_expression,
            "events_count('payment', within_days=90)",
        )

    def test_event_temporal_within_months(self):
        """Test CEL expression with within_months temporal filter."""
        variable = self.CELVariable.create(
            {
                "name": "test_6month_sum",
                "cel_accessor": "six_month_sum",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "sum",
                "value_type": "money",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_temporal": "within_months",
                "event_agg_temporal_value": 6,
                "event_agg_field": "amount",
            }
        )
        self.assertEqual(
            variable.cel_expression,
            "events_sum('payment', 'amount', within_months=6)",
        )

    def test_event_all_states(self):
        """Test CEL expression with all states filter."""
        variable = self.CELVariable.create(
            {
                "name": "test_all_states_count",
                "cel_accessor": "all_states_count",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "count",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_states": "all",
            }
        )
        self.assertIn(
            "states=['active', 'superseded', 'expired']",
            variable.cel_expression,
        )

    def test_event_with_custom_filter_ignored(self):
        """Test that aggregate_filter is not included in generated event expression.

        The where_predicate feature is not implemented in the executor, so
        aggregate_filter is intentionally excluded from the generated CEL
        expression to avoid silently wrong results.
        """
        variable = self.CELVariable.create(
            {
                "name": "test_large_payments",
                "cel_accessor": "large_payments",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "sum",
                "value_type": "money",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_field": "amount",
                "aggregate_filter": "e.amount > 1000",
            }
        )
        # where= should NOT be in the expression since where_predicate is not implemented
        self.assertNotIn("where=", variable.cel_expression)
        self.assertEqual(variable.cel_expression, "events_sum('payment', 'amount')")

    def test_event_aggregation_without_type_raises_validation(self):
        """Test that missing event type raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.CELVariable.create(
                {
                    "name": "test_no_type",
                    "cel_accessor": "no_type_var",
                    "source_type": "aggregate",
                    "aggregate_target": "events",
                    "aggregate_type": "count",
                    "value_type": "number",
                    "category_id": self.category.id,
                    # No event_agg_type_id — constraint should reject this
                }
            )

    def test_onchange_aggregate_target_clears_event_fields(self):
        """Test that changing aggregate_target clears event-specific fields."""
        variable = self.CELVariable.create(
            {
                "name": "test_switch",
                "cel_accessor": "switch_var",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "count",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_temporal": "this_year",
            }
        )

        # Simulate onchange
        variable.aggregate_target = "members"
        variable._onchange_aggregate_target_event()

        self.assertFalse(variable.event_agg_type_id)
        self.assertEqual(variable.event_agg_temporal, "all")

    def test_within_days_requires_value(self):
        """Test that within_days requires a positive temporal value."""
        with self.assertRaises(ValidationError):
            self.CELVariable.create(
                {
                    "name": "test_invalid_within_days",
                    "cel_accessor": "invalid_days",
                    "source_type": "aggregate",
                    "aggregate_target": "events",
                    "aggregate_type": "count",
                    "value_type": "number",
                    "category_id": self.category.id,
                    "event_agg_type_id": self.event_type.id,
                    "event_agg_temporal": "within_days",
                    # No event_agg_temporal_value
                }
            )

    def test_within_months_requires_value(self):
        """Test that within_months requires a positive temporal value."""
        with self.assertRaises(ValidationError):
            self.CELVariable.create(
                {
                    "name": "test_invalid_within_months",
                    "cel_accessor": "invalid_months",
                    "source_type": "aggregate",
                    "aggregate_target": "events",
                    "aggregate_type": "count",
                    "value_type": "number",
                    "category_id": self.category.id,
                    "event_agg_type_id": self.event_type.id,
                    "event_agg_temporal": "within_months",
                    "event_agg_temporal_value": 0,  # Invalid - must be positive
                }
            )

    def test_sum_without_field_raises_validation(self):
        """Test that sum aggregation without event_agg_field raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.CELVariable.create(
                {
                    "name": "test_sum_no_field",
                    "cel_accessor": "sum_no_field",
                    "source_type": "aggregate",
                    "aggregate_target": "events",
                    "aggregate_type": "sum",
                    "value_type": "money",
                    "category_id": self.category.id,
                    "event_agg_type_id": self.event_type.id,
                    # No event_agg_field — constraint should reject
                }
            )

    def test_avg_without_field_raises_validation(self):
        """Test that avg aggregation without event_agg_field raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.CELVariable.create(
                {
                    "name": "test_avg_no_field",
                    "cel_accessor": "avg_no_field",
                    "source_type": "aggregate",
                    "aggregate_target": "events",
                    "aggregate_type": "avg",
                    "value_type": "number",
                    "category_id": self.category.id,
                    "event_agg_type_id": self.event_type.id,
                    # No event_agg_field — constraint should reject
                }
            )

    def test_has_event_with_temporal_filter(self):
        """Test has_event expression with temporal filter."""
        variable = self.CELVariable.create(
            {
                "name": "test_has_recent_payment",
                "cel_accessor": "has_recent_payment",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "exists",
                "value_type": "boolean",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_temporal": "within_days",
                "event_agg_temporal_value": 30,
            }
        )
        self.assertEqual(variable.cel_expression, "has_event('payment', within_days=30)")

    def test_has_event_with_named_period(self):
        """Test has_event expression with named period."""
        variable = self.CELVariable.create(
            {
                "name": "test_has_payment_this_year",
                "cel_accessor": "has_payment_year",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "exists",
                "value_type": "boolean",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_temporal": "this_year",
            }
        )
        self.assertEqual(variable.cel_expression, "has_event('payment', period=this_year())")

    def test_has_event_with_all_states(self):
        """Test has_event expression with all states filter."""
        variable = self.CELVariable.create(
            {
                "name": "test_has_any_payment",
                "cel_accessor": "has_any_payment",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "exists",
                "value_type": "boolean",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_states": "all",
            }
        )
        self.assertIn("states=['active', 'superseded', 'expired']", variable.cel_expression)
        self.assertTrue(variable.cel_expression.startswith("has_event("))

    def test_onchange_aggregate_type_clears_field(self):
        """Test that switching to count/exists clears event_agg_field."""
        variable = self.CELVariable.create(
            {
                "name": "test_type_switch",
                "cel_accessor": "type_switch_var",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "sum",
                "value_type": "money",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_field": "amount",
            }
        )
        self.assertEqual(variable.event_agg_field, "amount")

        # Simulate onchange to count
        variable.aggregate_type = "count"
        variable._onchange_aggregate_type_event()
        self.assertFalse(variable.event_agg_field)

    def test_onchange_temporal_resets_value(self):
        """Test that switching temporal type resets the value."""
        variable = self.CELVariable.create(
            {
                "name": "test_temporal_switch",
                "cel_accessor": "temporal_switch_var",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "count",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_temporal": "within_days",
                "event_agg_temporal_value": 90,
            }
        )
        self.assertEqual(variable.event_agg_temporal_value, 90)

        # Simulate onchange to named period
        variable.event_agg_temporal = "this_year"
        variable._onchange_event_agg_temporal()
        self.assertEqual(variable.event_agg_temporal_value, 0)

    def test_event_min_cel_expression(self):
        """Test CEL expression generation for event min."""
        variable = self.CELVariable.create(
            {
                "name": "test_min_score",
                "cel_accessor": "min_score",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "min",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_field": "score",
            }
        )
        self.assertEqual(variable.cel_expression, "events_min('payment', 'score')")

    def test_event_max_cel_expression(self):
        """Test CEL expression generation for event max."""
        variable = self.CELVariable.create(
            {
                "name": "test_max_score",
                "cel_accessor": "max_score",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "max",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_field": "score",
            }
        )
        self.assertEqual(variable.cel_expression, "events_max('payment', 'score')")

    def test_event_this_month_temporal(self):
        """Test CEL expression with this_month temporal filter."""
        variable = self.CELVariable.create(
            {
                "name": "test_mtd_count",
                "cel_accessor": "mtd_count",
                "source_type": "aggregate",
                "aggregate_target": "events",
                "aggregate_type": "count",
                "value_type": "number",
                "category_id": self.category.id,
                "event_agg_type_id": self.event_type.id,
                "event_agg_temporal": "this_month",
            }
        )
        self.assertEqual(
            variable.cel_expression,
            "events_count('payment', period=this_month())",
        )
