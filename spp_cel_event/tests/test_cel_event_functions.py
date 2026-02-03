# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for CEL event helper functions."""

from datetime import date

from odoo.tests.common import TransactionCase

from ..models import cel_event_functions as fn


class TestPeriodParsing(TransactionCase):
    """Test period parsing functions."""

    def test_parse_period_year(self):
        """Test parsing full year period."""
        start, end = fn.parse_period("2024")
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 12, 31))

    def test_parse_period_quarter(self):
        """Test parsing quarter periods."""
        # Q1
        start, end = fn.parse_period("2024-Q1")
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 3, 31))

        # Q2
        start, end = fn.parse_period("2024-Q2")
        self.assertEqual(start, date(2024, 4, 1))
        self.assertEqual(end, date(2024, 6, 30))

        # Q3
        start, end = fn.parse_period("2024-Q3")
        self.assertEqual(start, date(2024, 7, 1))
        self.assertEqual(end, date(2024, 9, 30))

        # Q4
        start, end = fn.parse_period("2024-Q4")
        self.assertEqual(start, date(2024, 10, 1))
        self.assertEqual(end, date(2024, 12, 31))

    def test_parse_period_half_year(self):
        """Test parsing half-year periods."""
        # H1
        start, end = fn.parse_period("2024-H1")
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 6, 30))

        # H2
        start, end = fn.parse_period("2024-H2")
        self.assertEqual(start, date(2024, 7, 1))
        self.assertEqual(end, date(2024, 12, 31))

    def test_parse_period_month(self):
        """Test parsing month periods."""
        # January
        start, end = fn.parse_period("2024-01")
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 1, 31))

        # February (non-leap year)
        start, end = fn.parse_period("2023-02")
        self.assertEqual(start, date(2023, 2, 1))
        self.assertEqual(end, date(2023, 2, 28))

        # February (leap year)
        start, end = fn.parse_period("2024-02")
        self.assertEqual(start, date(2024, 2, 1))
        self.assertEqual(end, date(2024, 2, 29))

        # December
        start, end = fn.parse_period("2024-12")
        self.assertEqual(start, date(2024, 12, 1))
        self.assertEqual(end, date(2024, 12, 31))

    def test_parse_period_week(self):
        """Test parsing ISO week periods."""
        # Week 1 of 2024 (Jan 1-7, 2024)
        start, end = fn.parse_period("2024-W01")
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 1, 7))

        # Week 15 of 2024
        start, end = fn.parse_period("2024-W15")
        self.assertEqual(start, date(2024, 4, 8))
        self.assertEqual(end, date(2024, 4, 14))

    def test_parse_period_invalid_format(self):
        """Test invalid period formats raise ValueError."""
        with self.assertRaises(ValueError):
            fn.parse_period("invalid")

        with self.assertRaises(ValueError):
            fn.parse_period("2024-Q5")  # Invalid quarter

        with self.assertRaises(ValueError):
            fn.parse_period("2024-13")  # Invalid month

        with self.assertRaises(ValueError):
            fn.parse_period("2024-W54")  # Invalid week

        with self.assertRaises(ValueError):
            fn.parse_period("")

        with self.assertRaises(ValueError):
            fn.parse_period(None)


class TestDynamicPeriodGenerators(TransactionCase):
    """Test dynamic period generator functions."""

    def test_this_year(self):
        """Test this_year generator."""
        result = fn.this_year(date(2024, 6, 15))
        self.assertEqual(result, "2024")

    def test_last_year(self):
        """Test last_year generator."""
        result = fn.last_year(date(2024, 6, 15))
        self.assertEqual(result, "2023")

    def test_this_quarter(self):
        """Test this_quarter generator."""
        # Q1
        self.assertEqual(fn.this_quarter(date(2024, 1, 15)), "2024-Q1")
        self.assertEqual(fn.this_quarter(date(2024, 2, 15)), "2024-Q1")
        self.assertEqual(fn.this_quarter(date(2024, 3, 15)), "2024-Q1")

        # Q2
        self.assertEqual(fn.this_quarter(date(2024, 4, 15)), "2024-Q2")
        self.assertEqual(fn.this_quarter(date(2024, 5, 15)), "2024-Q2")
        self.assertEqual(fn.this_quarter(date(2024, 6, 15)), "2024-Q2")

        # Q3
        self.assertEqual(fn.this_quarter(date(2024, 7, 15)), "2024-Q3")
        self.assertEqual(fn.this_quarter(date(2024, 8, 15)), "2024-Q3")
        self.assertEqual(fn.this_quarter(date(2024, 9, 15)), "2024-Q3")

        # Q4
        self.assertEqual(fn.this_quarter(date(2024, 10, 15)), "2024-Q4")
        self.assertEqual(fn.this_quarter(date(2024, 11, 15)), "2024-Q4")
        self.assertEqual(fn.this_quarter(date(2024, 12, 15)), "2024-Q4")

    def test_last_quarter(self):
        """Test last_quarter generator."""
        # From Q2 -> Q1
        self.assertEqual(fn.last_quarter(date(2024, 4, 15)), "2024-Q1")

        # From Q1 -> Q4 of previous year
        self.assertEqual(fn.last_quarter(date(2024, 1, 15)), "2023-Q4")

        # From Q4 -> Q3
        self.assertEqual(fn.last_quarter(date(2024, 12, 15)), "2024-Q3")

    def test_this_month(self):
        """Test this_month generator."""
        self.assertEqual(fn.this_month(date(2024, 1, 15)), "2024-01")
        self.assertEqual(fn.this_month(date(2024, 6, 15)), "2024-06")
        self.assertEqual(fn.this_month(date(2024, 12, 15)), "2024-12")

    def test_last_month(self):
        """Test last_month generator."""
        # Regular case
        self.assertEqual(fn.last_month(date(2024, 6, 15)), "2024-05")

        # January -> December of previous year
        self.assertEqual(fn.last_month(date(2024, 1, 15)), "2023-12")

        # December -> November
        self.assertEqual(fn.last_month(date(2024, 12, 15)), "2024-11")

    def test_quarters_ago(self):
        """Test quarters_ago generator."""
        # 1 quarter ago from Q2 -> Q1
        self.assertEqual(fn.quarters_ago(1, date(2024, 6, 15)), "2024-Q1")

        # 2 quarters ago from Q2 -> Q4 of previous year
        self.assertEqual(fn.quarters_ago(2, date(2024, 6, 15)), "2023-Q4")

        # 5 quarters ago from Q2 2024 -> Q1 2023
        self.assertEqual(fn.quarters_ago(5, date(2024, 6, 15)), "2023-Q1")

    def test_months_ago(self):
        """Test months_ago generator."""
        # 1 month ago
        self.assertEqual(fn.months_ago(1, date(2024, 6, 15)), "2024-05")

        # 2 months ago
        self.assertEqual(fn.months_ago(2, date(2024, 6, 15)), "2024-04")

        # 7 months ago (crosses year boundary)
        self.assertEqual(fn.months_ago(7, date(2024, 6, 15)), "2023-11")

    def test_year_start(self):
        """Test year_start generator."""
        result = fn.year_start(date(2024, 6, 15))
        self.assertEqual(result, date(2024, 1, 1))

    def test_quarter_start(self):
        """Test quarter_start generator."""
        # Q1
        self.assertEqual(fn.quarter_start(date(2024, 2, 15)), date(2024, 1, 1))

        # Q2
        self.assertEqual(fn.quarter_start(date(2024, 5, 15)), date(2024, 4, 1))

        # Q3
        self.assertEqual(fn.quarter_start(date(2024, 8, 15)), date(2024, 7, 1))

        # Q4
        self.assertEqual(fn.quarter_start(date(2024, 11, 15)), date(2024, 10, 1))

    def test_month_start(self):
        """Test month_start generator."""
        result = fn.month_start(date(2024, 6, 15))
        self.assertEqual(result, date(2024, 6, 1))


class TestSelectionModeResolvers(TransactionCase):
    """Test selection mode resolver functions."""

    def test_get_default_select_mode_with_one_active(self):
        """Test get_default_select_mode for event type with is_one_active_per_registrant."""
        # Create event type with is_one_active_per_registrant=True
        self.env["spp.event.type"].create(
            {
                "name": "Household Survey",
                "code": "household_survey",
                "is_one_active_per_registrant": True,
            }
        )

        result = fn.get_default_select_mode(self.env, "household_survey")
        self.assertEqual(result, "active")

    def test_get_default_select_mode_without_one_active(self):
        """Test get_default_select_mode for event type without is_one_active_per_registrant."""
        # Create event type with is_one_active_per_registrant=False
        self.env["spp.event.type"].create(
            {
                "name": "Field Visit",
                "code": "field_visit",
                "is_one_active_per_registrant": False,
            }
        )

        result = fn.get_default_select_mode(self.env, "field_visit")
        self.assertEqual(result, "latest")

    def test_get_default_select_mode_nonexistent(self):
        """Test get_default_select_mode for nonexistent event type."""
        result = fn.get_default_select_mode(self.env, "nonexistent_type")
        self.assertEqual(result, "latest")

    def test_get_states_for_select_mode_active(self):
        """Test get_states_for_select_mode with 'active' mode."""
        result = fn.get_states_for_select_mode("active")
        self.assertEqual(result, ["active"])

    def test_get_states_for_select_mode_latest_active(self):
        """Test get_states_for_select_mode with 'latest_active' mode."""
        result = fn.get_states_for_select_mode("latest_active")
        self.assertEqual(result, ["active"])

    def test_get_states_for_select_mode_any(self):
        """Test get_states_for_select_mode with 'any' mode."""
        result = fn.get_states_for_select_mode("any")
        self.assertEqual(result, ["active"])

    def test_get_states_for_select_mode_latest(self):
        """Test get_states_for_select_mode with 'latest' mode."""
        result = fn.get_states_for_select_mode("latest")
        self.assertEqual(result, ["active", "superseded", "expired"])

    def test_get_states_for_select_mode_first(self):
        """Test get_states_for_select_mode with 'first' mode."""
        result = fn.get_states_for_select_mode("first")
        self.assertEqual(result, ["active", "superseded", "expired"])

    def test_get_states_for_select_mode_unknown(self):
        """Test get_states_for_select_mode with unknown mode."""
        result = fn.get_states_for_select_mode("unknown")
        # Should default to active
        self.assertEqual(result, ["active"])


class TestTemporalFilterHelpers(TransactionCase):
    """Test temporal filter helper functions."""

    def test_apply_temporal_filters_no_filters(self):
        """Test apply_temporal_filters with no filters."""
        start, end = fn.apply_temporal_filters()
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_apply_temporal_filters_after_only(self):
        """Test apply_temporal_filters with only 'after' filter."""
        start, end = fn.apply_temporal_filters(after=date(2024, 1, 1))
        self.assertEqual(start, date(2024, 1, 1))
        self.assertIsNone(end)

    def test_apply_temporal_filters_before_only(self):
        """Test apply_temporal_filters with only 'before' filter."""
        start, end = fn.apply_temporal_filters(before=date(2024, 12, 31))
        self.assertIsNone(start)
        self.assertEqual(end, date(2024, 12, 31))

    def test_apply_temporal_filters_after_and_before(self):
        """Test apply_temporal_filters with both 'after' and 'before'."""
        start, end = fn.apply_temporal_filters(after=date(2024, 1, 1), before=date(2024, 12, 31))
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 12, 31))

    def test_apply_temporal_filters_within_days(self):
        """Test apply_temporal_filters with within_days."""
        base = date(2024, 6, 15)
        start, end = fn.apply_temporal_filters(base_date=base, within_days=30)
        self.assertEqual(start, date(2024, 5, 16))  # 30 days before
        self.assertEqual(end, date(2024, 6, 15))  # base_date

    def test_apply_temporal_filters_within_months(self):
        """Test apply_temporal_filters with within_months."""
        base = date(2024, 6, 15)
        start, end = fn.apply_temporal_filters(base_date=base, within_months=3)
        self.assertEqual(start, date(2024, 3, 15))  # 3 months before
        self.assertEqual(end, date(2024, 6, 15))  # base_date

    def test_apply_temporal_filters_period(self):
        """Test apply_temporal_filters with period."""
        start, end = fn.apply_temporal_filters(period="2024-Q2")
        self.assertEqual(start, date(2024, 4, 1))
        self.assertEqual(end, date(2024, 6, 30))

    def test_apply_temporal_filters_after_as_period(self):
        """Test apply_temporal_filters with 'after' as period string."""
        start, end = fn.apply_temporal_filters(after="2024-Q1")
        self.assertEqual(start, date(2024, 1, 1))
        self.assertIsNone(end)

    def test_apply_temporal_filters_before_as_period(self):
        """Test apply_temporal_filters with 'before' as period string."""
        start, end = fn.apply_temporal_filters(before="2024-Q2")
        self.assertIsNone(start)
        self.assertEqual(end, date(2024, 6, 30))

    def test_apply_temporal_filters_combined_intersection(self):
        """Test apply_temporal_filters with multiple filters (intersection)."""
        # Period is full year, but after/before narrows it down
        start, end = fn.apply_temporal_filters(period="2024", after=date(2024, 6, 1), before=date(2024, 9, 30))
        # Should take the most restrictive range
        self.assertEqual(start, date(2024, 6, 1))
        self.assertEqual(end, date(2024, 9, 30))

    def test_apply_temporal_filters_combined_within_days_and_period(self):
        """Test apply_temporal_filters with within_days and period."""
        base = date(2024, 3, 15)
        start, end = fn.apply_temporal_filters(base_date=base, within_days=30, period="2024-Q1")
        # within_days: 2024-02-14 to 2024-03-15
        # period: 2024-01-01 to 2024-03-31
        # Intersection: 2024-02-14 to 2024-03-15
        self.assertEqual(start, date(2024, 2, 14))
        self.assertEqual(end, date(2024, 3, 15))

    def test_validate_temporal_range_valid(self):
        """Test validate_temporal_range with valid range."""
        start, end = fn.validate_temporal_range(date(2024, 1, 1), date(2024, 12, 31))
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 12, 31))

    def test_validate_temporal_range_invalid(self):
        """Test validate_temporal_range with invalid range (start > end)."""
        start, end = fn.validate_temporal_range(date(2024, 12, 31), date(2024, 1, 1))
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_validate_temporal_range_none_values(self):
        """Test validate_temporal_range with None values."""
        start, end = fn.validate_temporal_range(None, date(2024, 12, 31))
        self.assertIsNone(start)
        self.assertEqual(end, date(2024, 12, 31))

        start, end = fn.validate_temporal_range(date(2024, 1, 1), None)
        self.assertEqual(start, date(2024, 1, 1))
        self.assertIsNone(end)


class TestUtilityFunctions(TransactionCase):
    """Test utility functions."""

    def test_days_between(self):
        """Test days_between function."""
        result = fn.days_between(date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(result, 30)

        # Negative case
        result = fn.days_between(date(2024, 1, 31), date(2024, 1, 1))
        self.assertEqual(result, -30)

    def test_is_within_range_full_range(self):
        """Test is_within_range with both start and end."""
        # Within range
        self.assertTrue(fn.is_within_range(date(2024, 6, 15), date(2024, 1, 1), date(2024, 12, 31)))

        # Before range
        self.assertFalse(fn.is_within_range(date(2023, 12, 31), date(2024, 1, 1), date(2024, 12, 31)))

        # After range
        self.assertFalse(fn.is_within_range(date(2025, 1, 1), date(2024, 1, 1), date(2024, 12, 31)))

    def test_is_within_range_start_only(self):
        """Test is_within_range with only start bound."""
        self.assertTrue(fn.is_within_range(date(2024, 6, 15), start=date(2024, 1, 1)))
        self.assertFalse(fn.is_within_range(date(2023, 12, 31), start=date(2024, 1, 1)))

    def test_is_within_range_end_only(self):
        """Test is_within_range with only end bound."""
        self.assertTrue(fn.is_within_range(date(2024, 6, 15), end=date(2024, 12, 31)))
        self.assertFalse(fn.is_within_range(date(2025, 1, 1), end=date(2024, 12, 31)))

    def test_is_within_range_no_bounds(self):
        """Test is_within_range with no bounds."""
        self.assertTrue(fn.is_within_range(date(2024, 6, 15)))
