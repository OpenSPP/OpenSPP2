### 19.0.2.0.1

- fix(case): completing an intervention plan now clears `is_current`, so a finished plan
  stops being the case's current plan. Previously only the revision path released the
  flag, leaving `current_plan_id` pointing at completed work while `has_active_plan` read
  False, and blocking any new plan from being marked current.

### 19.0.2.0.0

- Initial migration to OpenSPP2
