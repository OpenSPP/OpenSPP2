Tracks data provenance for registrants, identifiers, and program memberships. Records the source system, collection method, and timestamps for each record. Provides merge capabilities with complete audit trails and relationship transfer.

### Key Capabilities

- Source detection: Distinguishes between Odoo UI, API, bulk import, mobile app, migration, and merge operations via context and HTTP headers
- Immutable creation tracking: Records source system, source reference, collection method, and collection date at creation
- Update tracking: Maintains last update system and reference for all modifications
- Registrant merge: Transfers identifiers, relationships, and program memberships from merged record to survivor
- Merge provenance: Preserves audit trail with JSON data snapshots and merge chain pointers
- Merge chain resolution: Follows `merged_into_id` pointers to find current active partner

### Key Models

| Model                       | Description                                              |
| --------------------------- | -------------------------------------------------------- |
| `spp.mixin.source.tracking` | Abstract mixin providing source tracking fields          |
| `spp.merge.provenance`      | Audit record of merge operations with data snapshots     |
| `res.partner`               | Extended with source tracking and merge capabilities     |
| `spp.registry.id`           | Extended with source tracking for identifier provenance  |
| `spp.program.membership`    | Extended with source tracking for enrollment provenance  |

### UI Location

- **Source Tracking Tab**: Individual and group registrant forms under "Source Tracking"
- **Merge History Menu**: Registry > Configuration > Merge History
- **Search Filters**: Partner search includes filters for source system, collection method, merged records, and records with merge history

### Security

| Group                                 | Access                          |
| ------------------------------------- | ------------------------------- |
| `base.group_user`                     | Read merge provenance           |
| `spp_registry.group_registry_manager` | Read/Write/Create (no delete)   |
| `spp_security.group_spp_admin`        | Perform merge operations        |

### Extension Points

- Override `_selection_collection_method()` to add custom collection methods
- Inherit `spp.mixin.source.tracking` in any model to enable source tracking
- Override `_get_merge_snapshot()` to customize which fields are preserved in merge audit trail
- Override `_transfer_relationships()` or `_transfer_memberships()` to customize merge behavior

### Configuration

After installing:

1. Source tracking is automatically enabled for `res.partner`, `spp.registry.id`, and `spp.program.membership`
2. API clients should set `X-Source-System` HTTP header for accurate source detection
3. Context variables control behavior: `source_system`, `source_reference`, `collection_method`, `skip_source_tracking`
4. Merge operations require admin or registry manager access via `_check_merge_access()`

### Dependencies

`base`, `spp_security`, `spp_registry`, `spp_programs`
