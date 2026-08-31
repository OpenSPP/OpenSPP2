### 19.0.2.0.2

- fix(security): enforce manager-only approval of graduation assessments server-side. `action_approve` / `action_reject` / `action_reset_draft` now require the graduation manager group (the view-level button gating was UI-only and bypassable via RPC), and non-managers can no longer set the approval fields (`approved_by_id` / `approved_date` / `graduation_date`), move `state` beyond `draft → submitted`, or edit a submitted assessment's content. Prevents a user from self-approving their own assessment.

### 19.0.2.0.1

- fix(views): add a "Graduation Criteria" menu item directly under the Graduation root, plus a list/form/search view and action for `spp.graduation.criteria`. The model and ACL were already shipped, but no UI surface existed — criteria could only be edited indirectly through the pathway form. Visible to `group_spp_graduation_user` and above.
- fix(security): rename the module's `res.groups` and `res.groups.privilege` records from generic "User" / "Manager" to "Graduation User" / "Graduation Manager" so they are unambiguous in the Settings → Users access-rights UI.

### 19.0.2.0.0

- Initial migration to OpenSPP2
