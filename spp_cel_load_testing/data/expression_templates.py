# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""CEL Expression Templates for Load Testing.

This module provides a collection of CEL expressions organized by complexity level,
used for performance testing and benchmarking of the CEL expression evaluator.

Expression Categories:
- simple: Basic field comparisons and arithmetic
- medium: Multiple conditions, simple member operations
- complex_exists: Member existence checks with predicates
- complex_count: Member counting with complex filters
- complex_aggregate: Field aggregations (sum, avg, min, max)
- metric_based: Calculations using household metrics
- event_basic: Simple event-based conditions
- event_temporal: Time-bounded event queries
- event_aggregate: Event counting and aggregations

Note: Expressions use age_years(birthdate) instead of r.age because
the `age` field is computed and not stored in the database.
"""


# Expression templates organized by complexity level
# Format: List of (name, expression) tuples

EXPRESSIONS: dict[str, list[tuple[str, str]]] = {
    "simple": [
        ("age_check", "age_years(r.birthdate) >= 18"),
        ("income_threshold", "r.income < 5000"),
        ("birthdate_exists", "r.birthdate != null"),
        ("income_positive", "r.income > 0"),
        ("age_range", "age_years(r.birthdate) >= 18 && age_years(r.birthdate) <= 65"),
        ("true_literal", "true"),
    ],
    "medium": [
        (
            "adult_with_income",
            "age_years(r.birthdate) >= 18 && r.income > 0",
        ),
        (
            "low_income_adult",
            "age_years(r.birthdate) >= 18 && r.income < 3000",
        ),
        (
            "elderly_check",
            "age_years(r.birthdate) >= 65",
        ),
        (
            "working_age_poor",
            "age_years(r.birthdate) >= 18 && age_years(r.birthdate) <= 60 && r.income < 2000",
        ),
        (
            "low_income_threshold",
            "r.income < 4000",
        ),
        (
            "multiple_criteria",
            "age_years(r.birthdate) >= 25 && r.income < 5000",
        ),
    ],
    "complex_exists": [
        (
            "has_young_child",
            "members.exists(m, age_years(m.birthdate) < 5)",
        ),
        (
            "has_elderly_member",
            "members.exists(m, age_years(m.birthdate) >= 65)",
        ),
        (
            "has_low_income_member",
            "members.exists(m, m.income < 1000)",
        ),
        (
            "has_working_age_adult",
            "members.exists(m, age_years(m.birthdate) >= 18 && age_years(m.birthdate) <= 60)",
        ),
        (
            "has_young_member",
            "members.exists(m, age_years(m.birthdate) < 18)",
        ),
        (
            "has_income_earner",
            "members.exists(m, m.income > 0)",
        ),
    ],
    "complex_count": [
        (
            "household_size_check",
            "members.count(m, true) >= 4",
        ),
        (
            "multiple_children",
            "members.count(m, age_years(m.birthdate) < 18) >= 3",
        ),
        (
            "few_income_earners",
            "members.count(m, m.income > 0) < 2",
        ),
        (
            "dependency_ratio",
            (
                "members.count(m, age_years(m.birthdate) < 18 || age_years(m.birthdate) >= 65) > "
                "members.count(m, age_years(m.birthdate) >= 18 && age_years(m.birthdate) < 65)"
            ),
        ),
        (
            "adults_count",
            "members.count(m, age_years(m.birthdate) >= 18) >= 2",
        ),
        (
            "large_family",
            "members.count(m, true) >= 5 && members.count(m, age_years(m.birthdate) < 5) >= 2",
        ),
    ],
    "complex_aggregate": [
        (
            "low_total_income",
            "members.sum(m, m.income, true) < 10000",
        ),
        (
            "low_avg_income",
            "members.avg(m, m.income, true) < 2000",
        ),
        (
            "per_capita_income",
            "members.sum(m, m.income, true) / members.count(m, true) < 1500",
        ),
        (
            "low_adult_avg_income",
            "members.avg(m, m.income, age_years(m.birthdate) >= 18) < 3000",
        ),
        (
            "income_inequality",
            "members.max(m, m.income, true) > 3 * members.avg(m, m.income, true)",
        ),
        (
            "vulnerable_household_income",
            "members.sum(m, m.income, true) < 5000 && members.count(m, age_years(m.birthdate) < 18) >= 2",
        ),
    ],
    "metric_based": [
        (
            "household_income_ratio",
            "household.total_income / household.member_count < 1000",
        ),
        (
            "high_dependency_ratio",
            "household.dependency_ratio > 0.5",
        ),
        (
            "low_income_density",
            "household.total_income / household.adult_count < 2500",
        ),
        (
            "composite_vulnerability",
            "household.total_income < 8000 && household.child_count >= 3",
        ),
        (
            "elderly_household",
            "household.elderly_count >= 2 && household.total_income < 6000",
        ),
    ],
    "event_basic": [
        (
            "low_survey_income",
            "event('household_survey').income < 5000",
        ),
        (
            "unemployed_status",
            "event('employment_status').employed == false",
        ),
        (
            "poor_housing",
            "event('housing_assessment').score < 50",
        ),
        (
            "food_insecure",
            "event('food_security').status == 'insecure'",
        ),
        (
            "multiple_event_conditions",
            "event('survey').income < 3000 && event('assessment').vulnerable == true",
        ),
    ],
    "event_temporal": [
        (
            "recent_low_income",
            "event('household_survey', within_days=365).income < 5000",
        ),
        (
            "recent_unemployment",
            "event('employment_status', within_days=90).employed == false",
        ),
        (
            "yearly_income_check",
            "event('annual_survey', within_months=12).total_income < 12000",
        ),
        (
            "recent_vulnerability",
            "event('vulnerability_assessment', within_days=180).score >= 70",
        ),
        (
            "recent_multiple_events",
            "event('survey', within_days=365).income < 4000 && event('assessment', within_days=365).vulnerable == true",
        ),
    ],
    "event_aggregate": [
        (
            "high_attendance",
            "events_count('attendance', period='2024') >= 150",
        ),
        (
            "frequent_participation",
            "events_count('training', within_months=6) >= 3",
        ),
        (
            "active_beneficiary",
            "events_count('program_activity', within_days=90) >= 5",
        ),
        (
            "regular_visits",
            "events_count('home_visit', within_months=12) >= 4",
        ),
        (
            "engagement_threshold",
            "events_count('attendance', within_days=365) >= 100 && events_count('training', within_days=365) >= 2",
        ),
        (
            "multi_year_participation",
            "has_event('activity', within_months=24)",
        ),
    ],
}


def get_expressions_by_complexity(level: str) -> list[tuple[str, str]]:
    """Get all expressions for a specific complexity level.

    Args:
        level: Complexity level (simple, medium, complex_exists, etc.)

    Returns:
        List of (name, expression) tuples

    Raises:
        KeyError: If the complexity level doesn't exist
    """
    if level not in EXPRESSIONS:
        available = ", ".join(EXPRESSIONS.keys())
        raise KeyError(f"Unknown complexity level: {level}. Available levels: {available}")
    return EXPRESSIONS[level]


def get_all_expressions() -> list[tuple[str, str, str]]:
    """Get all expressions with their complexity levels.

    Returns:
        List of (complexity, name, expression) tuples
    """
    result = []
    for complexity, expressions in EXPRESSIONS.items():
        for name, expression in expressions:
            result.append((complexity, name, expression))
    return result


def get_expression_count() -> int:
    """Get total number of expressions across all complexity levels.

    Returns:
        Total count of expressions
    """
    return sum(len(exprs) for exprs in EXPRESSIONS.values())


def get_complexity_levels() -> list[str]:
    """Get list of all complexity levels.

    Returns:
        List of complexity level names
    """
    return list(EXPRESSIONS.keys())
