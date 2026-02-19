# CEL Event Functions

Utility functions for working with event data in CEL expressions.

## Overview

This module provides pure Python functions that can be used in CEL expressions to:

- Parse period strings into date ranges
- Generate dynamic period strings (current/previous quarter, month, year, etc.)
- Resolve event selection modes and states
- Apply and combine temporal filters

## Usage in CEL Expressions

These functions are designed to be called from CEL expressions in eligibility rules,
entitlement formulas, and other CEL-based logic.

### Period Parsing

```python
# Parse various period formats
parse_period('2024')           # Full year: (2024-01-01, 2024-12-31)
parse_period('2024-Q2')        # Quarter: (2024-04-01, 2024-06-30)
parse_period('2024-H1')        # Half-year: (2024-01-01, 2024-06-30)
parse_period('2024-03')        # Month: (2024-03-01, 2024-03-31)
parse_period('2024-W15')       # ISO week: (2024-04-08, 2024-04-14)
```

### Dynamic Period Generators

```python
# Current periods
this_year()          # '2024'
this_quarter()       # '2024-Q4'
this_month()         # '2024-12'

# Previous periods
last_year()          # '2023'
last_quarter()       # '2024-Q3'
last_month()         # '2024-11'

# Historical periods
quarters_ago(2)      # '2024-Q2' (2 quarters ago)
months_ago(6)        # '2024-06' (6 months ago)

# Period boundaries
year_start()         # date(2024, 1, 1)
quarter_start()      # date(2024, 10, 1)
month_start()        # date(2024, 12, 1)
```

### Selection Mode Helpers

```python
# Get default selection mode for an event type
get_default_select_mode(env, 'household_survey')  # 'active' or 'latest'

# Get states for a selection mode
get_states_for_select_mode('active')         # ['active']
get_states_for_select_mode('latest')         # ['active', 'superseded', 'expired']
get_states_for_select_mode('latest_active')  # ['active']
```

### Temporal Filters

```python
# Single filter
apply_temporal_filters(within_days=30)
# Returns: (date 30 days ago, today)

apply_temporal_filters(period='2024-Q2')
# Returns: (2024-04-01, 2024-06-30)

# Combined filters (intersection)
apply_temporal_filters(
    period='2024',
    after=date(2024, 6, 1),
    before=date(2024, 9, 30)
)
# Returns: (2024-06-01, 2024-09-30)
```

### Utility Functions

```python
# Calculate days between dates
days_between(date(2024, 1, 1), date(2024, 12, 31))  # 365

# Check if date is within range
is_within_range(date(2024, 6, 15), start=date(2024, 1, 1), end=date(2024, 12, 31))  # True

# Validate temporal range
validate_temporal_range(start_date, end_date)  # Returns (start, end) or (None, None) if invalid
```

## Implementation Notes

### Pure Functions

Most functions are pure (no side effects) and can be tested independently:

- `parse_period`
- All period generators (`this_year`, `last_quarter`, etc.)
- `get_states_for_select_mode`
- `apply_temporal_filters`
- Utility functions

### Odoo Environment Required

Only one function requires the Odoo environment:

- `get_default_select_mode(env, event_type_code)` - Looks up event type configuration

### Error Handling

- Invalid period strings raise `ValueError` with descriptive messages
- Invalid date ranges are logged as warnings
- Missing event types default to 'latest' selection mode
- Unknown selection modes default to ['active'] states

### Type Hints

All functions include type hints for better IDE support and documentation:

```python
def parse_period(period: str) -> tuple[date, date]:
def apply_temporal_filters(
    base_date: date | None = None,
    after: date | str | None = None,
    # ...
) -> tuple[date | None, date | None]:
```

## Testing

Comprehensive unit tests are provided in `tests/test_cel_event_functions.py`:

- Period parsing (all formats)
- Dynamic period generation
- Selection mode resolution
- Temporal filter combinations
- Edge cases (year boundaries, leap years, etc.)

Run tests with:

```bash
./scripts/test_single_module.sh spp_cel_event
```

## Examples

### Eligibility Rule: "Has recent survey"

```python
# Check if registrant has a survey within the last year
has_event('household_survey', period=this_year())
```

### Eligibility Rule: "Income in last survey"

```python
# Get income from most recent survey in current quarter
event('household_survey', select='latest', period=this_quarter()).income > 500
```

### Entitlement Formula: "Average attendance"

```python
# Average attendance across all events in 2024
events_avg('attendance', 'days_attended', period='2024')
```

### Complex Filter: "Recent high-value surveys"

```python
# Count surveys with high income in last 6 months
events_count(
    'household_survey',
    period=months_ago(6) + '/' + this_month(),
    where='income > 1000',
    states=['active']
)
```

## See Also

- [CEL Event Data Integration Spec](../../../docs/specs/CEL_EVENT_DATA_INTEGRATION_SPEC.md)
- [Query Plan Nodes](cel_event_queryplan.py)
- [Event Data Model](../../spp_event_data/models/event_data.py)
