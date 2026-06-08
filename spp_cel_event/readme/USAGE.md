## UI Testing Guide

This guide covers manual QA testing for the `spp_cel_event` module. All tests
start from the variable configuration form.

### Prerequisites

- Module `spp_cel_event` is installed (auto-installs when `spp_cel_domain`,
  `spp_event_data`, and `spp_studio` are all present)
- At least one **Event Type** exists (e.g., code `payment`, target type
  `individual`)
- User has access to the Studio menu

### Navigating to the Form

1. Go to **Studio > Rules > Variables > All Variables**
2. Click **New** to create a variable, or open an existing one

### Test 1: Event Aggregation Section Visibility

| Step | Action                                    | Expected Result                                                   |
| ---- | ----------------------------------------- | ----------------------------------------------------------------- |
| 1    | Set **Source Type** to "Aggregate"        | Aggregate fields appear                                           |
| 2    | Set **Aggregate Target** to "Members"     | Event Aggregation section is **hidden**                           |
| 3    | Set **Aggregate Target** to "Events"      | Event Aggregation section appears with: Event Type, Time Range, Event States, and Generated Expression preview |

### Test 2: Count Aggregation

| Step | Action                                         | Expected Result                             |
| ---- | ---------------------------------------------- | ------------------------------------------- |
| 1    | Set **Source Type** = Aggregate                 |                                             |
| 2    | Set **Aggregate Target** = Events              | Event Aggregation section appears           |
| 3    | Set **Aggregate Type** = Count                 |                                             |
| 4    | Set **Event Type** = Payment Event             | Warning disappears                          |
| 5    | Leave **Time Range** = All Time                |                                             |
| 6    | Check **Generated Expression**                 | `events_count('payment')`                   |
| 7    | **Event Field** should be **hidden**           | Field not visible (count doesn't need it)   |

### Test 3: Exists Aggregation

| Step | Action                                         | Expected Result                             |
| ---- | ---------------------------------------------- | ------------------------------------------- |
| 1    | Set **Aggregate Type** = Exists               |                                             |
| 2    | Set **Event Type** = Payment Event             |                                             |
| 3    | Check **Generated Expression**                 | `has_event('payment')`                      |
| 4    | **Event Field** should be **hidden**           | Field not visible (exists doesn't need it)  |

### Test 4: Sum Aggregation (also applies to avg, min, max)

| Step | Action                                         | Expected Result                                 |
| ---- | ---------------------------------------------- | ----------------------------------------------- |
| 1    | Set **Aggregate Type** = Sum                   | **Event Field** becomes visible and **required** |
| 2    | Set **Event Type** = Payment Event             |                                                 |
| 3    | Type `amount` in **Event Field**               |                                                 |
| 4    | Check **Generated Expression**                 | `events_sum('payment', 'amount')`               |
| 5    | Change **Aggregate Type** to Avg               | Expression updates to `events_avg('payment', 'amount')` |
| 6    | Change **Aggregate Type** to Min               | Expression updates to `events_min('payment', 'amount')` |
| 7    | Change **Aggregate Type** to Max               | Expression updates to `events_max('payment', 'amount')` |

### Test 5: Temporal Filters

**5a: Named Periods**

| Step | Action                                         | Expected Result                                              |
| ---- | ---------------------------------------------- | ------------------------------------------------------------ |
| 1    | Set up a Count aggregation with an event type  |                                                              |
| 2    | Set **Time Range** = This Year                 | Expression: `events_count('payment', period=this_year())`    |
| 3    | Set **Time Range** = This Quarter              | Expression: `events_count('payment', period=this_quarter())` |
| 4    | Set **Time Range** = This Month                | Expression: `events_count('payment', period=this_month())`   |
| 5    | **Number of Days/Months** field is **hidden**  | Field not visible for named periods                          |

**5b: Within N Days**

| Step | Action                                         | Expected Result                                       |
| ---- | ---------------------------------------------- | ----------------------------------------------------- |
| 1    | Set **Time Range** = Within N Days             | **Number of Days/Months** field appears and is required |
| 2    | Enter `90`                                     | Expression: `events_count('payment', within_days=90)` |

**5c: Within N Months**

| Step | Action                                         | Expected Result                                           |
| ---- | ---------------------------------------------- | --------------------------------------------------------- |
| 1    | Set **Time Range** = Within N Months           | **Number of Days/Months** field appears and is required    |
| 2    | Enter `6`                                      | Expression: `events_count('payment', within_months=6)`    |

### Test 6: Event States Filter

| Step | Action                                         | Expected Result                                                                   |
| ---- | ---------------------------------------------- | --------------------------------------------------------------------------------- |
| 1    | Set up a Count aggregation with an event type  |                                                                                   |
| 2    | **Event States** defaults to "Active Only"     | No `states=` in expression                                                        |
| 3    | Set **Event States** = All States              | Expression includes `states=['active', 'superseded', 'expired']`                  |
| 4    | Example full expression                        | `events_count('payment', states=['active', 'superseded', 'expired'])`             |

### Test 7: Combined Filters

| Step | Action                                         | Expected Result                                                                     |
| ---- | ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| 1    | **Aggregate Type** = Sum                       |                                                                                     |
| 2    | **Event Type** = Payment Event                 |                                                                                     |
| 3    | **Event Field** = `amount`                     |                                                                                     |
| 4    | **Time Range** = Within N Months, value = `6`  |                                                                                     |
| 5    | **Event States** = All States                  |                                                                                     |
| 6    | Check **Generated Expression**                 | `events_sum('payment', 'amount', within_months=6, states=['active', 'superseded', 'expired'])` |

### Test 8: Validation Errors

**8a: Missing Event Type**

| Step | Action                                         | Expected Result                                  |
| ---- | ---------------------------------------------- | ------------------------------------------------ |
| 1    | Set **Source Type** = Aggregate                 |                                                  |
| 2    | Set **Aggregate Target** = Events              |                                                  |
| 3    | Set **Aggregate Type** = Count                 |                                                  |
| 4    | Leave **Event Type** empty                     |                                                  |
| 5    | Fill remaining required fields and click Save  | **ValidationError**: event type is required      |

**8b: Missing Event Field for Sum/Avg/Min/Max**

| Step | Action                                         | Expected Result                                  |
| ---- | ---------------------------------------------- | ------------------------------------------------ |
| 1    | Set **Aggregate Type** = Sum                   |                                                  |
| 2    | Set **Event Type** = Payment Event             |                                                  |
| 3    | Leave **Event Field** empty                    |                                                  |
| 4    | Click Save                                     | **ValidationError**: field is required for sum   |

**8c: Missing Temporal Value**

| Step | Action                                         | Expected Result                                  |
| ---- | ---------------------------------------------- | ------------------------------------------------ |
| 1    | Set **Time Range** = Within N Days             |                                                  |
| 2    | Leave **Number of Days/Months** empty or `0`   |                                                  |
| 3    | Click Save                                     | **ValidationError**: positive value required     |

### Test 9: Onchange Field Clearing

**9a: Switching Away from Events**

| Step | Action                                         | Expected Result                                     |
| ---- | ---------------------------------------------- | --------------------------------------------------- |
| 1    | Create a variable with **Aggregate Target** = Events, fully configured |                                  |
| 2    | Change **Aggregate Target** to "Members"       | Event Type, Time Range, Event Field, Event States reset to defaults |
| 3    | Change back to "Events"                        | Fields are blank/default and need reconfiguration   |

**9b: Switching Aggregate Type to Count/Exists**

| Step | Action                                         | Expected Result                                     |
| ---- | ---------------------------------------------- | --------------------------------------------------- |
| 1    | Set **Aggregate Type** = Sum, **Event Field** = `amount` |                                            |
| 2    | Change **Aggregate Type** to Count             | **Event Field** is cleared and hidden               |
| 3    | Change **Aggregate Type** to Exists            | **Event Field** remains cleared and hidden          |

**9c: Switching Temporal Type**

| Step | Action                                         | Expected Result                                     |
| ---- | ---------------------------------------------- | --------------------------------------------------- |
| 1    | Set **Time Range** = Within N Days, value = `30` |                                                   |
| 2    | Change **Time Range** to This Year             | **Number of Days/Months** is cleared and hidden     |

### Test 10: Expression Preview Warning

| Step | Action                                         | Expected Result                                                         |
| ---- | ---------------------------------------------- | ----------------------------------------------------------------------- |
| 1    | Set **Aggregate Target** = Events              | Generated Expression preview appears                                    |
| 2    | Leave **Event Type** empty                     | Warning icon with: "Configuration incomplete. Select an event type to generate the expression." |
| 3    | Select an **Event Type**                       | Warning disappears, valid expression shown                              |

### Test 11: Aggregate Filter is Excluded

| Step | Action                                         | Expected Result                                           |
| ---- | ---------------------------------------------- | --------------------------------------------------------- |
| 1    | Set up any event aggregation (e.g., Sum)       |                                                           |
| 2    | Enter a value in **Aggregate Filter** (e.g., `e.amount > 1000`) |                                              |
| 3    | Check **Generated Expression**                 | Expression does **NOT** contain `where=`                  |
| 4    | The filter value is stored but not included in the generated expression | This is by design (where_predicate is not yet implemented in the executor) |
