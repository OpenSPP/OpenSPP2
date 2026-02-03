Foundation module providing version history, scheduled activation, and lifecycle management for any Odoo model. Stores field snapshots with temporal validity tracking, optional approval workflow, and usage tracking to prevent archiving in-use artifacts.

### Key Capabilities

- Store version snapshots in JSON with three relation strategies: shallow (IDs), embed (snapshot data), follow (cascade versions)
- Schedule versions for future activation via daily cron job with supersession chain tracking
- Optional approval workflow (draft → pending → approved → scheduled/current) and test gate enforcement
- Usage tracking prevents archiving artifacts referenced by programs or consumers

### Key Models

| Model                                  | Description                                                     |
| -------------------------------------- | --------------------------------------------------------------- |
| `spp.versioned.mixin`                  | Abstract mixin to add versioning capabilities to any model      |
| `spp.artifact.version`                 | Stores version snapshots with state machine (draft/scheduled/current) |
| `spp.artifact.usage`                   | Tracks where artifacts are used (prevents orphan archiving)     |
| `spp.artifact.version.schedule.wizard` | Wizard for scheduling version activation with conflict detection|

### Configuration

After installing:

1. Verify cron **Activate Scheduled Artifact Versions** is active under **Settings > Technical > Scheduled Actions**
2. Enable approval globally via system parameter `spp_versioning.require_approval = True` or per-artifact via `is_approval_required` field

### UI Location

- Versioned artifacts call `action_view_versions()` to open version history or `action_open_schedule_wizard()` for scheduling
- When used with `spp_studio`, menus appear under **Studio > Settings > Versioning**:
  - **Scheduled Changes** (shows upcoming activations)
  - **Version History** (all versions across models)
  - **Artifact Usages** (dependency tracking)

### Security

| Group                          | Access                       |
| ------------------------------ | ---------------------------- |
| `base.group_user`              | Read versions and usages     |
| `spp_security.group_spp_admin` | Full CRUD, approve/reject    |

### Extension Points

To add versioning to your model:

1. Inherit `spp.versioned.mixin`:
   ```python
   class MyModel(models.Model):
       _inherit = ["my.model", "spp.versioned.mixin"]
   ```

2. Implement `_get_version_snapshot_fields()` to specify fields to snapshot:
   ```python
   def _get_version_snapshot_fields(self):
       return ["name", "category_id", ("program_id", "embed"), ("variable_ids", "follow")]
   ```

3. Optionally implement `_get_test_records()` for test gate validation or `_apply_version_snapshot(data)` to customize snapshot application

### Dependencies

`spp_security`, `mail`
