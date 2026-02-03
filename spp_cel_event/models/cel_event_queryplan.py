# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Query plan dataclasses for CEL event data integration.

This module defines the query plan node types used to represent CEL expressions
that query event data. These nodes are produced by the CEL translator and consumed
by the CEL executor to generate optimized SQL queries or Python evaluation code.

Query Plan Nodes:
    EventValueCompare: Compare a field value from a registrant's event
    EventExists: Check if a matching event exists
    EventsAggregate: Aggregate values across multiple events
    EventsCollection: Collection operations (exists, count, all, any)
    EventFieldRef: Reference to an event field (intermediate representation)

Example:
    # CEL: event('survey', within_days=365).income > 500
    # Translates to:
    EventValueCompare(
        event_type='survey',
        field_name='income',
        op='>',
        rhs=500,
        select='auto',
        within_days=365
    )
"""

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class EventValueCompare:
    """Compare a value from registrant's event with selection/filter.

    This node represents a comparison between a field value extracted from
    a registrant's event and a target value. Supports temporal filtering,
    state filtering, and selection modes for choosing which event to use
    when multiple events match.

    Attributes:
        event_type: Event type code (e.g., 'household_survey', 'visit')
        field_name: Field name in event's data_json to extract
        op: Comparison operator (==, !=, >, >=, <, <=)
        rhs: Right-hand side value to compare against
        select: Selection mode ('active', 'latest', 'latest_active', 'first', 'any', 'auto')
        after: Filter events with collection_date >= this date
        before: Filter events with collection_date <= this date
        within_days: Filter events within last N days from today
        within_months: Filter events within last N months from today
        period: Named period filter (e.g., '2024', '2024-Q1')
        states: Filter events by state (default: derived from select mode)
        default: Value to return if no matching event found

    Example:
        # event('survey', select='latest', within_days=365).income > 500
        EventValueCompare(
            event_type='survey',
            field_name='income',
            op='>',
            rhs=500,
            select='latest',
            within_days=365
        )
    """

    event_type: str
    field_name: str
    op: str
    rhs: Any

    # Selection mode
    select: str = "auto"

    # Temporal filters
    after: date | None = None
    before: date | None = None
    within_days: int | None = None
    within_months: int | None = None
    period: str | None = None

    # State filter
    states: list[str] | None = None

    # Default value when no event found
    default: Any = None


@dataclass
class EventExists:
    """Check if matching event exists for registrant.

    This node represents an existence check - returns True if at least one
    event matching the filters exists, False otherwise. Commonly used for
    simple eligibility checks like "has recent survey".

    Attributes:
        event_type: Event type code to check for
        after: Filter events with collection_date >= this date
        before: Filter events with collection_date <= this date
        within_days: Filter events within last N days from today
        within_months: Filter events within last N months from today
        period: Named period filter (e.g., '2024', '2024-Q1')
        states: Filter events by state (default: ['active'])

    Example:
        # has_event('assessment', within_days=365)
        EventExists(
            event_type='assessment',
            within_days=365,
            states=['active']
        )
    """

    event_type: str

    # Temporal filters
    after: date | None = None
    before: date | None = None
    within_days: int | None = None
    within_months: int | None = None
    period: str | None = None

    # State filter
    states: list[str] | None = None


@dataclass
class EventsAggregate:
    """Aggregate over multiple events (count, sum, avg, min, max).

    This node represents an aggregation operation across multiple events,
    optionally filtered by temporal constraints, state, and a where predicate.
    The result is compared against a target value.

    Attributes:
        event_type: Event type code to aggregate over
        field_name: Field in event's data_json to aggregate (None for count)
        agg: Aggregation function ('count', 'sum', 'avg', 'min', 'max')
        after: Filter events with collection_date >= this date
        before: Filter events with collection_date <= this date
        within_days: Filter events within last N days from today
        within_months: Filter events within last N months from today
        period: Named period filter (e.g., '2024', '2024-Q1')
        states: Filter events by state
        where_predicate: CEL expression string for filtering events before aggregation
        op: Comparison operator to apply to aggregated result
        rhs: Value to compare aggregated result against

    Example:
        # events_count('attendance', period='2024', where='attended == true') >= 150
        EventsAggregate(
            event_type='attendance',
            field_name=None,  # count doesn't need a field
            agg='count',
            period='2024',
            where_predicate='attended == true',
            op='>=',
            rhs=150
        )

        # events_avg('survey', 'income', within_days=365) < 500
        EventsAggregate(
            event_type='survey',
            field_name='income',
            agg='avg',
            within_days=365,
            op='<',
            rhs=500
        )
    """

    event_type: str
    field_name: str | None
    agg: str

    # Temporal/state filters
    after: date | None = None
    before: date | None = None
    within_days: int | None = None
    within_months: int | None = None
    period: str | None = None
    states: list[str] | None = None

    # Where predicate (CEL expression string for filtering events)
    where_predicate: str | None = None

    # Comparison
    op: str = ">="
    rhs: Any = 0


@dataclass
class EventsCollection:
    """Collection operation over events (exists, count, all, any with predicate).

    This node represents a collection operation that applies a predicate to
    multiple events. The predicate is evaluated for each event, and the
    operation determines how to combine the results.

    Attributes:
        event_type: Event type code to iterate over
        operation: Collection operation ('exists', 'count', 'all', 'any')
        var_name: Loop variable name used in predicate
        predicate: CEL predicate AST node (evaluated per event)
        after: Filter events with collection_date >= this date
        before: Filter events with collection_date <= this date
        within_days: Filter events within last N days from today
        within_months: Filter events within last N months from today
        period: Named period filter (e.g., '2024', '2024-Q1')
        states: Filter events by state
        op: For 'count' operation, comparison operator
        rhs: For 'count' operation, value to compare count against

    Example:
        # events('survey', period='2024').any(e, e.income < 500)
        EventsCollection(
            event_type='survey',
            operation='any',
            var_name='e',
            predicate=<AST node for: e.income < 500>,
            period='2024'
        )

        # events('assessment').all(e, e.passed == true)
        EventsCollection(
            event_type='assessment',
            operation='all',
            var_name='e',
            predicate=<AST node for: e.passed == true>
        )

        # events('visit', within_days=365).count(e, e.verified == true) >= 4
        EventsCollection(
            event_type='visit',
            operation='count',
            var_name='e',
            predicate=<AST node for: e.verified == true>,
            within_days=365,
            op='>=',
            rhs=4
        )
    """

    event_type: str
    operation: str
    var_name: str
    predicate: Any

    # Pre-filters (applied before predicate evaluation)
    after: date | None = None
    before: date | None = None
    within_days: int | None = None
    within_months: int | None = None
    period: str | None = None
    states: list[str] | None = None

    # For count comparison
    op: str | None = None
    rhs: int | None = None


@dataclass
class EventFieldRef:
    """Reference to an event field (intermediate representation).

    This node represents a reference to an event or event field that will be
    resolved during evaluation. Used as an intermediate step during translation
    before being converted to EventValueCompare or other concrete operations.

    When field_name is None, this represents a reference to the entire event
    object (for use in predicates or further field access).

    Attributes:
        event_type: Event type code
        field_name: Field in event's data_json (None means entire event object)
        select: Selection mode ('active', 'latest', 'latest_active', 'first', 'any', 'auto')
        after: Filter events with collection_date >= this date
        before: Filter events with collection_date <= this date
        within_days: Filter events within last N days from today
        within_months: Filter events within last N months from today
        period: Named period filter (e.g., '2024', '2024-Q1')
        states: Filter events by state
        default: Value to return if no matching event found

    Example:
        # event('survey', within_days=365)  [before field access]
        EventFieldRef(
            event_type='survey',
            field_name=None,  # No specific field yet
            select='auto',
            within_days=365
        )

        # event('survey', 'income', default=0)
        EventFieldRef(
            event_type='survey',
            field_name='income',
            select='auto',
            default=0
        )
    """

    event_type: str
    field_name: str | None = None
    select: str = "auto"
    after: date | None = None
    before: date | None = None
    within_days: int | None = None
    within_months: int | None = None
    period: str | None = None
    states: list[str] | None = None
    default: Any = None
