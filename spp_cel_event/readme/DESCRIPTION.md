Integrates event data with CEL expressions for eligibility and entitlement rules. Extends the CEL domain framework to query event data records collected through surveys, field visits, and assessments. Translates CEL expressions into optimized SQL queries when possible, with Python fallback for complex cases.

### Key Capabilities

- Query event field values with temporal filtering (within_days, within_months, named periods) and selection modes (active, latest, latest_active, first, any)
- Check event existence with date-based filtering
- Aggregate event data using count, sum, avg, min, max functions
- Generate period strings using helper functions (this_year, this_quarter, etc.)
- Optimize queries using SQL fast paths with automatic fallback to Python evaluation

### Key Models

| Model                | Description                                       |
| -------------------- | ------------------------------------------------- |
| `spp.cel.variable`   | Extended with event aggregation configuration     |
| `spp.cel.translator` | Extended to translate event functions to SQL/plan |
| `spp.cel.executor`   | Extended to execute event queries with SQL        |

### Configuration

After installing:

1. Navigate to **Studio > Rules > Variables > All Variables**
2. Create or edit a CEL variable and set **Source Type** to "Aggregate"
3. Set **Aggregate Target** to "Events"
4. Configure event type, temporal range, and aggregation function
5. The module automatically loads CEL function profiles from `data/cel_profiles.yaml` via `spp.cel.registry`

Database indexes are created automatically via post-init hook for optimal query performance.

### UI Location

- **Menu**: Studio > Rules > Variables > All Variables
- **Form**: Event aggregation fields appear in the Source Configuration section when **Aggregate Target** is set to "Events"

### Security

No module-specific security. Access control inherits from `spp_cel_domain` and `spp_studio` parent modules.

### Extension Points

- Override `spp.cel.translator._to_plan()` to add custom event query plan nodes
- Override `spp.cel.executor._exec_event_value_sql()` to customize SQL execution logic
- Extend period helper functions in `models/cel_event_functions.py`
- Implement custom aggregation functions following the events_count/sum/avg pattern

### Dependencies

`spp_cel_domain`, `spp_event_data`, `spp_studio`
