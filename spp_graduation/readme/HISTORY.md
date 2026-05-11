### 19.0.2.0.1

- fix(views): add a "Graduation Criteria" menu item directly under the Graduation root, plus a list/form/search view and action for `spp.graduation.criteria`. The model and ACL were already shipped, but no UI surface existed — criteria could only be edited indirectly through the pathway form. Visible to `group_spp_graduation_user` and above.
- fix(security): rename the module's `res.groups` and `res.groups.privilege` records from generic "User" / "Manager" to "Graduation User" / "Graduation Manager" so they are unambiguous in the Settings → Users access-rights UI.

### 19.0.2.0.0

- Initial migration to OpenSPP2
