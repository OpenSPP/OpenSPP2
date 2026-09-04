### 19.0.2.0.1

- fix(case): the generator no longer seeds intervention plans that are both
  `completed` and their case's current plan. The `close_case` journey step and the
  random-plan helper now complete plans through `action_complete()`, so a finished
  demo plan gets an `actual_end_date` and releases `is_current`.

### 19.0.2.0.0

- Initial migration to OpenSPP2
