# OpenSPP Source Tracking

Track data provenance and merge history for registrants and related records.

## Overview

This module implements
[ADR-005](../docs/architecture/decisions/ADR-005-source-tracking-provenance.md) to
provide:

- **Source tracking**: Know where data originated (system, reference, collection method)
- **Update tracking**: Track which system last modified a record
- **Merge provenance**: Audit trail when records are deduplicated/merged

## Features

### Source Tracking Fields

The `spp.mixin.source.tracking` mixin adds these fields to models:

| Field                   | Type      | Description                                                           |
| ----------------------- | --------- | --------------------------------------------------------------------- |
| `source_system`         | Char      | Original system that created the record (immutable)                   |
| `source_reference`      | Char      | ID/reference in the source system (immutable)                         |
| `collection_method`     | Selection | How data was collected: manual, import, api, mobile, migration, merge |
| `collection_date`       | Datetime  | When data was originally collected                                    |
| `last_update_system`    | Char      | System that made the most recent update                               |
| `last_update_reference` | Char      | Reference for the update (request ID, batch ID, etc.)                 |

### Models with Source Tracking

- `res.partner` (registrants)
- `spp.registry.id` (identifiers)
- `spp.program.membership` (program enrollments)

## Usage

### Setting Source on Create

```python
# Via context (recommended)
partner = self.env["res.partner"].with_context(
    source_system="external-mpi",
    source_reference="MPI-12345",
    collection_method="api",
).create({
    "name": "John Doe",
    "is_registrant": True,
})

# Auto-detection
# - Creates via UI default to source_system="odoo-ui", collection_method="manual"
# - Creates via API default to source_system="api", collection_method="api"
# - Creates with import_file context default to collection_method="import"
```

### Setting Source on Update

```python
# Via context
partner.with_context(
    source_system="mobile-app",
    source_reference="SYNC-789",
).write({"phone": "+1234567890"})

# Skip tracking (for internal operations)
partner.with_context(skip_source_tracking=True).write({"active": False})
```

### API Integration

External systems should pass the `X-Source-System` HTTP header:

```bash
curl -X POST https://openspp.example.com/api/v1/registrants \
  -H "X-Source-System: external-mpi" \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe"}'
```

## Merge Functionality

### Merging Records

```python
# Merge source into target (source becomes inactive)
target = source.merge_into(target, reason="Duplicate detected by MPI")

# What happens:
# 1. Merge provenance record created with data snapshot
# 2. Identifiers (reg_ids) transferred to target
# 3. Relationships transferred to target
# 4. Program memberships transferred (duplicates archived)
# 5. Source archived with merged_into_id pointing to target
```

### Resolving Merged Records

```python
# Follow merge chain to find active record
active_partner = self.env["res.partner"].resolve_partner(old_partner_id)
```

### Access Control

Merge operations require one of:

- System administrator
- `spp_security.group_spp_admin`
- `spp_registry_base.group_registry_manager`

### Viewing Merge History

Navigate to: **Registry > Configuration > Merge History**

Or on any registrant form: **Source Tracking** tab shows merge history.

## Security

| Group            | Read | Write | Create | Delete |
| ---------------- | ---- | ----- | ------ | ------ |
| All Users        | ✓    |       |        |        |
| Registry Manager | ✓    | ✓     | ✓      |        |

## Migration

Existing registrants are updated on module install:

```sql
UPDATE res_partner
SET source_system = 'v1-migration',
    collection_method = 'migration',
    collection_date = create_date
WHERE source_system IS NULL
  AND is_registrant = TRUE
```

## Technical Details

### Collection Methods

| Value       | Description                       |
| ----------- | --------------------------------- |
| `manual`    | Manual data entry via UI          |
| `import`    | Bulk import (CSV/Excel)           |
| `api`       | API integration                   |
| `mobile`    | Mobile app submission             |
| `migration` | Data migration from legacy system |
| `merge`     | Created during merge operation    |

### Dependencies

- `base`
- `spp_security`
- `spp_registry_base`
- `spp_programs_base`
