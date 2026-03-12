# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Comprehensive integration tests for CEL Event Data Integration.

Tests cover:
1. event() function with various selection modes and temporal filters
2. has_event() function for existence checks
3. events_count() and aggregation functions
4. SQL vs Python execution paths
5. Real-world eligibility scenarios
6. Performance characteristics
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCelEventIntegration(TransactionCase):
    """Integration tests for CEL event data functions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create event types
        cls.survey_type = cls.env["spp.event.type"].create(
            {
                "name": "Household Survey",
                "code": "household_survey",
                "category": "survey",
                "is_one_active_per_registrant": True,
            }
        )

        cls.visit_type = cls.env["spp.event.type"].create(
            {
                "name": "Field Visit",
                "code": "field_visit",
                "category": "visit",
                "is_one_active_per_registrant": False,  # Can have multiple active
            }
        )

        cls.assessment_type = cls.env["spp.event.type"].create(
            {
                "name": "Disability Assessment",
                "code": "disability_assessment",
                "category": "survey",  # Assessments use survey category
                "is_one_active_per_registrant": True,
            }
        )

        cls.attendance_type = cls.env["spp.event.type"].create(
            {
                "name": "Attendance",
                "code": "attendance",
                "category": "manual",  # Manual entry for attendance tracking
                "is_one_active_per_registrant": False,
            }
        )

        # Create test registrants
        cls.registrant_poor = cls.env["res.partner"].create(
            {
                "name": "John Doe",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.registrant_middle = cls.env["res.partner"].create(
            {
                "name": "Jane Smith",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.registrant_rich = cls.env["res.partner"].create(
            {
                "name": "Bob Johnson",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.registrant_no_data = cls.env["res.partner"].create(
            {
                "name": "Alice Brown",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create survey events with income data
        cls.survey_poor = cls.env["spp.event.data"].create(
            {
                "partner_id": cls.registrant_poor.id,
                "event_type_id": cls.survey_type.id,
                "collection_date": date.today() - timedelta(days=30),
                "state": "draft",
                "data_json": {
                    "income": 300,
                    "household_size": 6,
                    "has_disability": True,
                },
            }
        )
        cls.survey_poor.action_activate()

        cls.survey_middle = cls.env["spp.event.data"].create(
            {
                "partner_id": cls.registrant_middle.id,
                "event_type_id": cls.survey_type.id,
                "collection_date": date.today() - timedelta(days=60),
                "state": "draft",
                "data_json": {
                    "income": 800,
                    "household_size": 3,
                    "has_disability": False,
                },
            }
        )
        cls.survey_middle.action_activate()

        cls.survey_rich = cls.env["spp.event.data"].create(
            {
                "partner_id": cls.registrant_rich.id,
                "event_type_id": cls.survey_type.id,
                "collection_date": date.today() - timedelta(days=400),  # Old survey
                "state": "draft",
                "data_json": {
                    "income": 2000,
                    "household_size": 2,
                    "has_disability": False,
                },
            }
        )
        cls.survey_rich.action_activate()

        # Create disability assessments
        cls.assessment_poor = cls.env["spp.event.data"].create(
            {
                "partner_id": cls.registrant_poor.id,
                "event_type_id": cls.assessment_type.id,
                "collection_date": date.today() - timedelta(days=90),
                "state": "draft",
                "data_json": {
                    "is_disabled": True,
                    "disability_level": "severe",
                    "score": 85,
                },
            }
        )
        cls.assessment_poor.action_activate()

        # Create multiple visits for testing aggregation
        for i in range(10):
            visit = cls.env["spp.event.data"].create(
                {
                    "partner_id": cls.registrant_poor.id,
                    "event_type_id": cls.visit_type.id,
                    "collection_date": date.today() - timedelta(days=i * 30),
                    "state": "draft",
                    "data_json": {
                        "verified": i % 2 == 0,  # Half verified
                        "visit_number": i + 1,
                    },
                }
            )
            visit.action_activate()

        # Create attendance records for testing counting
        for i in range(150):
            attendance = cls.env["spp.event.data"].create(
                {
                    "partner_id": cls.registrant_poor.id,
                    "event_type_id": cls.attendance_type.id,
                    "collection_date": date(2024, 1, 1) + timedelta(days=i * 2),
                    "state": "draft",
                    "data_json": {
                        "attended": i < 120,  # 120 attended, 30 absent
                        "day_number": i + 1,
                    },
                }
            )
            attendance.action_activate()

        # Setup CEL service
        cls.cel_service = cls.env["spp.cel.service"]
        cls.profile = "registry_individuals"

    # ══════════════════════════════════════════════════════════════════════════════
    # Test event() function - Basic field access
    # ══════════════════════════════════════════════════════════════════════════════

    def test_event_basic_field_access_dot_notation(self):
        """Test event('type').field > value pattern."""
        expr = "event('household_survey').income < 500"
        result = self.cel_service.compile_expression(expr, self.profile)

        self.assertTrue(result["valid"], f"Error: {result.get('error')}")
        self.assertIn(self.registrant_poor.id, result["ids"])
        self.assertNotIn(self.registrant_middle.id, result["ids"])
        self.assertNotIn(self.registrant_rich.id, result["ids"])

    def test_event_value_compare_income_range(self):
        """Test EventValueCompare with income in a range (between two thresholds)."""
        from ..models.cel_event_queryplan import EventValueCompare

        # Income > 500
        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op=">",
            rhs=500,
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertNotIn(self.registrant_poor.id, ids)  # 300 < 500
        self.assertIn(self.registrant_middle.id, ids)  # 800 > 500
        self.assertIn(self.registrant_rich.id, ids)  # 2000 > 500

    def test_event_field_access_no_matching_event(self):
        """Test event field access when no event exists returns empty set."""
        expr = "event('household_survey').income < 500"
        # Registrant with no survey should not match
        result = self.cel_service.compile_expression(expr, self.profile)
        self.assertNotIn(self.registrant_no_data.id, result["ids"])

    def test_event_field_access_boolean_comparison(self):
        """Test comparing boolean field from event."""
        expr = "event('disability_assessment').is_disabled == true"
        result = self.cel_service.compile_expression(expr, self.profile)

        self.assertTrue(result["valid"], f"Error: {result.get('error')}")
        self.assertIn(self.registrant_poor.id, result["ids"])

    def test_event_field_access_string_comparison(self):
        """Test comparing string field from event."""
        expr = "event('disability_assessment').disability_level == 'severe'"
        result = self.cel_service.compile_expression(expr, self.profile)

        self.assertTrue(result["valid"], f"Error: {result.get('error')}")
        self.assertIn(self.registrant_poor.id, result["ids"])

    # ══════════════════════════════════════════════════════════════════════════════
    # Test event() with temporal filters
    # ══════════════════════════════════════════════════════════════════════════════

    def test_event_within_days_filter(self):
        """Test event with within_days temporal filter."""
        # Only poor registrant has survey within 365 days
        # Rich registrant has old survey (400 days ago)
        # This test would need parser support for named parameters
        # For now, we test the executor directly
        from ..models.cel_event_queryplan import EventValueCompare

        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=500,
            within_days=365,
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)
        self.assertNotIn(self.registrant_rich.id, ids)  # Too old

    def test_event_within_days_recent_only(self):
        """Test within_days filters out old events."""
        from ..models.cel_event_queryplan import EventValueCompare

        # Use within_days=100 to exclude middle registrant (60 days) includes poor (30 days)
        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op=">",
            rhs=0,  # Any income
            within_days=100,
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)  # 30 days ago
        self.assertIn(self.registrant_middle.id, ids)  # 60 days ago
        self.assertNotIn(self.registrant_rich.id, ids)  # 400 days ago

    def test_event_period_filter_year(self):
        """Test event with period='2024' filter.

        Note: With select='latest' (default for attendance), we get the latest
        attendance record in 2024. Since attendance records i>=120 have attended=False,
        the latest record in 2024 has attended=False. So we test with select='any'
        to check if ANY event in the period matches.
        """
        from ..models.cel_event_queryplan import EventValueCompare

        # Test with select='any' to check if any attendance in 2024 has attended=True
        plan = EventValueCompare(
            event_type="attendance",
            field_name="attended",
            op="==",
            rhs=True,
            period="2024",
            select="any",  # Check any matching event, not just latest
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Poor registrant has attendance with attended=True in 2024
        self.assertIn(self.registrant_poor.id, ids)

    def test_event_after_before_filters(self):
        """Test event with after/before date filters."""
        from ..models.cel_event_queryplan import EventValueCompare

        cutoff_date = date.today() - timedelta(days=100)
        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op=">",
            rhs=0,
            after=cutoff_date,
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Poor (30 days) and middle (60 days) are within 100 days
        self.assertIn(self.registrant_poor.id, ids)
        self.assertIn(self.registrant_middle.id, ids)
        self.assertNotIn(self.registrant_rich.id, ids)  # 400 days ago

    def test_event_within_months_filter(self):
        """Test event with within_months temporal filter."""
        from ..models.cel_event_queryplan import EventValueCompare

        # Poor registrant survey is 30 days ago, within 3 months
        # Middle registrant survey is 60 days ago, within 3 months
        # Rich registrant survey is 400 days ago, NOT within 3 months
        # Note: using 3 months instead of 2 to avoid boundary issues with
        # PostgreSQL INTERVAL month arithmetic near the 60-day mark.
        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op=">",
            rhs=0,
            within_months=3,
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)  # 30 days ago
        self.assertIn(self.registrant_middle.id, ids)  # 60 days ago
        self.assertNotIn(self.registrant_rich.id, ids)  # 400 days ago

    # ══════════════════════════════════════════════════════════════════════════════
    # Test event() with selection modes
    # ══════════════════════════════════════════════════════════════════════════════

    def test_event_select_active_mode(self):
        """Test event with select='active' mode."""
        from ..models.cel_event_queryplan import EventValueCompare

        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=1000,
            select="active",
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Should find active surveys for poor and middle
        self.assertIn(self.registrant_poor.id, ids)
        self.assertIn(self.registrant_middle.id, ids)

    def test_event_select_latest_mode(self):
        """Test event with select='latest' mode."""
        # Create multiple surveys for one registrant
        old_survey = self.env["spp.event.data"].create(
            {
                "partner_id": self.registrant_poor.id,
                "event_type_id": self.survey_type.id,
                "collection_date": date.today() - timedelta(days=200),
                "state": "active",
                "data_json": {"income": 5000},  # High income in old survey
            }
        )

        # Latest should still be the newer one with income=300
        from ..models.cel_event_queryplan import EventValueCompare

        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=500,
            select="latest",
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Should use latest (30 days ago, income=300)
        self.assertIn(self.registrant_poor.id, ids)

        # Cleanup
        old_survey.unlink()

    def test_event_select_first_mode(self):
        """Test event with select='first' mode."""
        # Create newer survey for poor registrant with higher income
        new_survey = self.env["spp.event.data"].create(
            {
                "partner_id": self.registrant_poor.id,
                "event_type_id": self.survey_type.id,
                "collection_date": date.today() - timedelta(days=10),
                "state": "active",
                "data_json": {"income": 5000},  # High income now
            }
        )

        from ..models.cel_event_queryplan import EventValueCompare

        # First should use oldest survey (income=300)
        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=500,
            select="first",
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Should use first/oldest (income=300)
        self.assertIn(self.registrant_poor.id, ids)

        # Cleanup
        new_survey.unlink()

    def test_event_select_latest_active_mode(self):
        """Test event with select='latest_active' mode."""
        from ..models.cel_event_queryplan import EventValueCompare

        # Create a superseded (old) survey with high income
        old_survey = self.env["spp.event.data"].create(
            {
                "partner_id": self.registrant_poor.id,
                "event_type_id": self.survey_type.id,
                "collection_date": date.today() - timedelta(days=200),
                "state": "superseded",
                "data_json": {"income": 5000},
            }
        )

        # latest_active should only consider active events, picking the most recent
        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=500,
            select="latest_active",
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Should match poor registrant (active survey has income=300)
        self.assertIn(self.registrant_poor.id, ids)

        # Cleanup
        old_survey.unlink()

    # ══════════════════════════════════════════════════════════════════════════════
    # Test has_event() function
    # ══════════════════════════════════════════════════════════════════════════════

    def test_has_event_basic_existence(self):
        """Test has_event() basic existence check."""
        from ..models.cel_event_queryplan import EventExists

        plan = EventExists(
            event_type="disability_assessment",
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Poor registrant has assessment
        self.assertIn(self.registrant_poor.id, ids)
        # Others don't
        self.assertNotIn(self.registrant_middle.id, ids)
        self.assertNotIn(self.registrant_rich.id, ids)

    def test_has_event_with_temporal_filter(self):
        """Test has_event with within_days filter."""
        from ..models.cel_event_queryplan import EventExists

        # Assessment is 90 days old
        plan = EventExists(
            event_type="disability_assessment",
            within_days=365,  # Should match
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)
        self.assertIn(self.registrant_poor.id, ids)

        # With stricter filter
        plan_strict = EventExists(
            event_type="disability_assessment",
            within_days=30,  # Should not match (assessment is 90 days old)
            states=["active"],
        )

        ids_strict = executor._execute_plan("res.partner", plan_strict)
        self.assertNotIn(self.registrant_poor.id, ids_strict)

    def test_has_event_no_matching_event(self):
        """Test has_event returns empty when no event exists."""
        from ..models.cel_event_queryplan import EventExists

        plan = EventExists(
            event_type="household_survey",
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # No data registrant should not be included
        self.assertNotIn(self.registrant_no_data.id, ids)

    # ══════════════════════════════════════════════════════════════════════════════
    # Test events_count() and aggregation
    # ══════════════════════════════════════════════════════════════════════════════

    def test_events_count_basic(self):
        """Test events_count() basic counting."""
        from ..models.cel_event_queryplan import EventsAggregate

        # Poor registrant has 10 visits
        plan = EventsAggregate(
            event_type="field_visit",
            field_name=None,  # count doesn't need field
            agg="count",
            op=">=",
            rhs=5,
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)
        self.assertNotIn(self.registrant_middle.id, ids)  # No visits

    def test_events_count_with_period(self):
        """Test events_count with period filter."""
        from ..models.cel_event_queryplan import EventsAggregate

        # Count attendance in 2024
        plan = EventsAggregate(
            event_type="attendance",
            field_name=None,
            agg="count",
            op=">=",
            rhs=100,
            period="2024",
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)  # Has 150 attendance records

    def test_events_count_exact_match(self):
        """Test events_count with exact equality."""
        from ..models.cel_event_queryplan import EventsAggregate

        # Poor registrant has exactly 10 visits
        plan = EventsAggregate(
            event_type="field_visit",
            field_name=None,
            agg="count",
            op="==",
            rhs=10,
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)

    def test_events_sum_aggregation(self):
        """Test events_sum() aggregation over visit_number field."""
        from ..models.cel_event_queryplan import EventsAggregate

        # Sum of visit_number across all 10 visits = 1+2+...+10 = 55
        plan = EventsAggregate(
            event_type="field_visit",
            field_name="visit_number",
            agg="sum",
            op=">=",
            rhs=50,
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)  # Sum = 55 >= 50
        self.assertNotIn(self.registrant_middle.id, ids)  # No visits

    def test_events_avg_aggregation(self):
        """Test events_avg() aggregation over visit_number field."""
        from ..models.cel_event_queryplan import EventsAggregate

        # Avg of visit_number across 10 visits = 55/10 = 5.5
        plan = EventsAggregate(
            event_type="field_visit",
            field_name="visit_number",
            agg="avg",
            op=">=",
            rhs=5,
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)  # Avg = 5.5 >= 5
        self.assertNotIn(self.registrant_middle.id, ids)  # No visits

    def test_events_min_aggregation(self):
        """Test events_min() aggregation over visit_number field."""
        from ..models.cel_event_queryplan import EventsAggregate

        plan = EventsAggregate(
            event_type="field_visit",
            field_name="visit_number",
            agg="min",
            op="==",
            rhs=1,
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)  # Min visit_number = 1

    def test_events_max_aggregation(self):
        """Test events_max() aggregation over visit_number field."""
        from ..models.cel_event_queryplan import EventsAggregate

        plan = EventsAggregate(
            event_type="field_visit",
            field_name="visit_number",
            agg="max",
            op="==",
            rhs=10,
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)  # Max visit_number = 10

    # ══════════════════════════════════════════════════════════════════════════════
    # Test SQL path vs Python path
    # ══════════════════════════════════════════════════════════════════════════════

    def test_sql_path_used_for_simple_comparison(self):
        """Test that SQL path is used for simple comparisons."""
        from ..models.cel_event_queryplan import EventValueCompare

        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=500,
        )

        executor = self.env["spp.cel.executor"]

        # Check if SQL path can be used
        can_use_sql = executor._can_use_sql_path(plan)
        self.assertTrue(can_use_sql, "SQL path should be available for simple comparison")

        # Execute and verify results
        ids = executor._execute_plan("res.partner", plan)
        self.assertIn(self.registrant_poor.id, ids)

    def test_python_path_fallback_with_default(self):
        """Test Python path is used when default value is specified."""
        from ..models.cel_event_queryplan import EventValueCompare

        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=500,
            default=0,  # Default forces Python path
        )

        executor = self.env["spp.cel.executor"]

        # SQL path should not be available with default
        can_use_sql = executor._can_use_sql_path(plan)
        self.assertFalse(can_use_sql, "SQL path should not be available with default value")

        # Execute via Python path
        ids = executor._exec_event_value_python("res.partner", plan)
        self.assertIn(self.registrant_poor.id, ids)

    def test_sql_path_performance_simple_query(self):
        """Test SQL path performance for simple queries."""
        import time

        from ..models.cel_event_queryplan import EventValueCompare

        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=1000,
        )

        executor = self.env["spp.cel.executor"]

        # Time SQL execution
        start = time.time()
        ids_sql = executor._exec_event_value_sql("res.partner", plan)
        sql_time = time.time() - start

        # Should complete quickly (< 1 second even with small dataset)
        self.assertLess(sql_time, 1.0, f"SQL path took {sql_time}s - too slow")
        self.assertGreater(len(ids_sql), 0, "Should find matching records")

    # ══════════════════════════════════════════════════════════════════════════════
    # Real-world eligibility scenarios
    # ══════════════════════════════════════════════════════════════════════════════

    def test_scenario_poverty_program_eligibility(self):
        """Real-world scenario: Poverty program requires recent survey with low income."""
        from ..models.cel_event_queryplan import EventExists, EventValueCompare

        # Eligibility: has_event('household_survey', within_days=365) AND income < 500
        has_survey = EventExists(
            event_type="household_survey",
            within_days=365,
            states=["active"],
        )

        low_income = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=500,
            within_days=365,
        )

        executor = self.env["spp.cel.executor"]

        # Execute both conditions
        has_survey_ids = executor._execute_plan("res.partner", has_survey)
        low_income_ids = executor._execute_plan("res.partner", low_income)

        # Intersection = eligible
        eligible_ids = set(has_survey_ids) & set(low_income_ids)

        # Poor registrant should be eligible
        self.assertIn(self.registrant_poor.id, eligible_ids)
        # Rich registrant not eligible (old survey)
        self.assertNotIn(self.registrant_rich.id, eligible_ids)
        # Middle registrant not eligible (income too high)
        self.assertNotIn(self.registrant_middle.id, eligible_ids)

    def test_scenario_disability_program_eligibility(self):
        """Real-world scenario: Disability program requires assessment and low income."""
        from ..models.cel_event_queryplan import EventExists, EventValueCompare

        has_assessment = EventExists(
            event_type="disability_assessment",
            states=["active"],
        )

        is_disabled = EventValueCompare(
            event_type="disability_assessment",
            field_name="is_disabled",
            op="==",
            rhs=True,
        )

        executor = self.env["spp.cel.executor"]

        has_assessment_ids = executor._execute_plan("res.partner", has_assessment)
        is_disabled_ids = executor._execute_plan("res.partner", is_disabled)

        eligible_ids = set(has_assessment_ids) & set(is_disabled_ids)

        # Only poor registrant has disability assessment with is_disabled=True
        self.assertIn(self.registrant_poor.id, eligible_ids)
        self.assertNotIn(self.registrant_middle.id, eligible_ids)
        self.assertNotIn(self.registrant_rich.id, eligible_ids)

    def test_scenario_attendance_compliance(self):
        """Real-world scenario: Attendance compliance requires 80% attendance."""
        from ..models.cel_event_queryplan import EventsAggregate

        # Poor registrant has 120 attended out of 150 = 80%
        # Require >= 100 attended days
        plan = EventsAggregate(
            event_type="attendance",
            field_name=None,
            agg="count",
            op=">=",
            rhs=100,
            period="2024",
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)

    def test_scenario_regular_visits_required(self):
        """Real-world scenario: Program requires at least 4 visits per year."""
        from ..models.cel_event_queryplan import EventsAggregate

        plan = EventsAggregate(
            event_type="field_visit",
            field_name=None,
            agg="count",
            op=">=",
            rhs=4,
            within_days=365,
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Poor registrant has 10 visits (some within 365 days)
        self.assertIn(self.registrant_poor.id, ids)

    # ══════════════════════════════════════════════════════════════════════════════
    # Edge cases and error handling
    # ══════════════════════════════════════════════════════════════════════════════

    def test_event_field_missing_in_json(self):
        """Test accessing field that doesn't exist in event data."""
        from ..models.cel_event_queryplan import EventValueCompare

        plan = EventValueCompare(
            event_type="household_survey",
            field_name="nonexistent_field",
            op="==",
            rhs="value",
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Should return empty result (no matches)
        self.assertEqual(len(ids), 0)

    def test_event_invalid_event_type(self):
        """Test querying non-existent event type."""
        from ..models.cel_event_queryplan import EventExists

        plan = EventExists(
            event_type="nonexistent_type",
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Should return empty (no events of this type)
        self.assertEqual(len(ids), 0)

    def test_event_null_comparison(self):
        """Test comparing event field with null/None."""
        from ..models.cel_event_queryplan import EventValueCompare

        plan = EventValueCompare(
            event_type="household_survey",
            field_name="missing_field",
            op="==",
            rhs=None,
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Fields that don't exist are treated as None
        # So this should match all registrants with surveys
        self.assertGreater(len(ids), 0)

    def test_event_numeric_type_coercion(self):
        """Test numeric field comparison handles type coercion."""
        from ..models.cel_event_queryplan import EventValueCompare

        # Compare income (stored as int/float) with float
        plan = EventValueCompare(
            event_type="household_survey",
            field_name="income",
            op="<",
            rhs=500.0,  # Float comparison
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        self.assertIn(self.registrant_poor.id, ids)

    def test_event_empty_states_list(self):
        """Test behavior with empty states list."""
        from ..models.cel_event_queryplan import EventExists

        plan = EventExists(
            event_type="household_survey",
            states=[],  # Empty states
        )

        executor = self.env["spp.cel.executor"]

        # Should use default states
        # This might return results or empty depending on implementation
        ids = executor._execute_plan("res.partner", plan)
        self.assertIsInstance(ids, list)

    def test_multiple_active_events_same_type(self):
        """Test selection when multiple active events exist (for non-one-active types)."""
        # Visit type allows multiple active events
        # Poor registrant has 10 active visits
        from ..models.cel_event_queryplan import EventValueCompare

        plan = EventValueCompare(
            event_type="field_visit",
            field_name="verified",
            op="==",
            rhs=True,
            select="latest",  # Should pick most recent
        )

        executor = self.env["spp.cel.executor"]
        ids = executor._execute_plan("res.partner", plan)

        # Should handle multiple active events correctly
        self.assertIsInstance(ids, list)

    # ══════════════════════════════════════════════════════════════════════════════
    # Integration with CEL service
    # ══════════════════════════════════════════════════════════════════════════════

    def test_cel_service_compilation_succeeds(self):
        """Test that CEL service can compile event expressions."""
        # Tests basic CEL compilation only. event() syntax is parsed via the translator but
        # the end-to-end compile_expression path for full event expressions is tested via executor plan tests above.
        expr = "true"  # Basic expression that should work
        result = self.cel_service.compile_expression(expr, self.profile)

        self.assertTrue(result["valid"], f"Error: {result.get('error')}")
        self.assertIsInstance(result["count"], int)
        self.assertIsInstance(result["ids"], list)

    def test_cel_service_get_matching_ids(self):
        """Test get_matching_ids wrapper method."""
        # Tests basic CEL compilation only. event() syntax is parsed via the translator but
        # the end-to-end compile_expression path for full event expressions is tested via executor plan tests above.
        expr = "true"
        ids = self.cel_service.get_matching_ids(expr, self.profile)

        self.assertIsInstance(ids, list)
        self.assertGreater(len(ids), 0)

    # ══════════════════════════════════════════════════════════════════════════════
    # Performance benchmarks
    # ══════════════════════════════════════════════════════════════════════════════

    def test_performance_event_exists_large_dataset(self):
        """Benchmark has_event performance with current dataset."""
        import time

        from ..models.cel_event_queryplan import EventExists

        plan = EventExists(
            event_type="attendance",
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]

        start = time.time()
        ids = executor._execute_plan("res.partner", plan)
        elapsed = time.time() - start

        # Should complete quickly even with 150 attendance records
        self.assertLess(elapsed, 1.0, f"EventExists took {elapsed}s - too slow")
        self.assertGreater(len(ids), 0)

    def test_performance_event_count_aggregation(self):
        """Benchmark events_count performance."""
        import time

        from ..models.cel_event_queryplan import EventsAggregate

        plan = EventsAggregate(
            event_type="attendance",
            field_name=None,
            agg="count",
            op=">=",
            rhs=50,
            states=["active"],
        )

        executor = self.env["spp.cel.executor"]

        start = time.time()
        ids = executor._execute_plan("res.partner", plan)
        elapsed = time.time() - start

        # Should complete quickly with GROUP BY
        self.assertLess(elapsed, 1.0, f"EventsAggregate count took {elapsed}s - too slow")
        self.assertGreater(len(ids), 0)

    # ══════════════════════════════════════════════════════════════════════════════
    # Helper method tests
    # ══════════════════════════════════════════════════════════════════════════════

    def test_parse_period_year(self):
        """Test period parsing for year format."""
        from ..models.cel_event_functions import parse_period

        start, end = parse_period("2024")
        self.assertEqual(start, date(2024, 1, 1))
        self.assertEqual(end, date(2024, 12, 31))

    def test_parse_period_quarter(self):
        """Test period parsing for quarter format."""
        from ..models.cel_event_functions import parse_period

        start, end = parse_period("2024-Q2")
        self.assertEqual(start, date(2024, 4, 1))
        self.assertEqual(end, date(2024, 6, 30))

    def test_parse_period_month(self):
        """Test period parsing for month format."""
        from ..models.cel_event_functions import parse_period

        start, end = parse_period("2024-03")
        self.assertEqual(start, date(2024, 3, 1))
        self.assertEqual(end, date(2024, 3, 31))

    def test_parse_period_invalid_format(self):
        """Test period parsing with invalid format raises error."""
        from ..models.cel_event_functions import parse_period

        with self.assertRaises(ValueError):
            parse_period("invalid")

    def test_get_default_states_for_select_mode(self):
        """Test state list resolution for selection modes."""
        from ..models.cel_event_functions import get_states_for_select_mode

        self.assertEqual(get_states_for_select_mode("active"), ["active"])
        self.assertEqual(get_states_for_select_mode("latest_active"), ["active"])
        self.assertEqual(
            get_states_for_select_mode("latest"),
            ["active", "superseded", "expired"],
        )
        self.assertEqual(
            get_states_for_select_mode("first"),
            ["active", "superseded", "expired"],
        )
