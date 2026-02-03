# DMS File Versioning Implementation

## Overview

This document describes the native versioning feature implemented in the `spp_dms` module for OpenSPP.

## Implementation Date

December 14, 2025

## Components Created

### 1. Core Model: `spp.dms.file.version`

**File**: `/home/user/openspp-modules-v2/spp_dms/models/dms_file_version.py`

**Key Features**:

- Stores complete file content snapshots
- Tracks version number, checksum, size, and mimetype
- Records creator and creation timestamp
- Supports version comments for change descriptions
- Enforces only one current version per file via constraint
- Automatic checksum calculation using SHA512

**Fields**:

- `file_id`: Link to parent file (cascade delete)
- `version_number`: Sequential version number
- `content`: Binary content (stored as attachment)
- `checksum`: SHA512 hash for integrity
- `size`: File size in bytes
- `mimetype`: MIME type
- `created_by_id`: User who created the version
- `created_date`: Creation timestamp
- `comment`: Description of changes
- `is_current`: Boolean flag for current version

**Constraints**:

- Unique version number per file (SQL constraint)
- Only one current version per file (Python constraint)

### 2. Extended Model: `spp.dms.file`

**File**: `/home/user/openspp-modules-v2/spp_dms/models/dms_file.py`

**New Fields**:

- `version_ids`: One2many to versions
- `current_version_number`: Computed field
- `is_versioned`: Enable/disable versioning flag
- `version_count`: Computed count of versions

**New Methods**:

- `_create_new_version(comment=None)`: Create version snapshot
- `action_restore_version(version_id)`: Restore from version
- `action_enable_versioning()`: Enable versioning + create initial version
- `action_disable_versioning()`: Disable versioning (preserves history)
- `action_view_versions()`: Open version list view
- `write()`: Override to auto-create versions on content changes

**Auto-versioning Behavior**:

- When `is_versioned=True` and content changes, automatically creates a new version
- Uses context flag `skip_auto_version` to prevent recursive version creation
- Gracefully handles failures in auto-versioning (logs warning, doesn't block save)

### 3. Restore Wizard: `spp.dms.restore.version.wizard`

**Files**:

- `/home/user/openspp-modules-v2/spp_dms/wizard/restore_version_wizard.py`
- `/home/user/openspp-modules-v2/spp_dms/wizard/restore_version_wizard_views.xml`

**Purpose**: Provides user-friendly interface for version restoration

**Features**:

- Displays version metadata before restore
- Shows warning about restore process
- Validates version belongs to file
- Returns success notification

### 4. Views

#### File Version Views

**File**: `/home/user/openspp-modules-v2/spp_dms/views/dms_file_version_views.xml`

**Components**:

- Tree view: List all versions with key metadata
- Form view: Detailed version information with restore button
- Action: Navigate to version list

#### Updated File Views

**File**: `/home/user/openspp-modules-v2/spp_dms/views/dms_file_views.xml`

**Enhancements**:

- Header buttons: Enable/Disable versioning
- Stat button: Version count with quick access
- Notebook tab: Version history (visible when versioned)
- Inline version tree with restore action

### 5. Security

**File**: `/home/user/openspp-modules-v2/spp_dms/security/ir.model.access.csv`

**Access Rights**:

| Model                            | Admin (Manager) | User                |
| -------------------------------- | --------------- | ------------------- |
| `spp.dms.file.version`           | CRUD (1,1,1,1)  | Read-only (1,0,0,0) |
| `spp.dms.restore.version.wizard` | CRUD (1,1,1,1)  | CRUD (1,1,1,1)      |

**Rationale**:

- Admins have full control over versions
- Users can read versions and restore them (via wizard)
- Version creation is handled automatically by the system

### 6. Tests

**File**: `/home/user/openspp-modules-v2/spp_dms/tests/test_dms_file_version.py`

**Test Coverage** (18 test cases):

1. `test_01_enable_versioning`: Basic enable functionality
2. `test_02_enable_versioning_twice_should_fail`: Duplicate enable protection
3. `test_03_auto_create_version_on_content_change`: Auto-versioning
4. `test_04_manual_version_creation`: Manual version with comment
5. `test_05_version_without_versioning_enabled_should_fail`: State validation
6. `test_06_restore_version`: Full restore workflow
7. `test_07_restore_nonexistent_version_should_fail`: Error handling
8. `test_08_restore_wrong_file_version_should_fail`: Cross-file protection
9. `test_09_disable_versioning`: Disable preserves history
10. `test_10_disable_versioning_without_enabled_should_fail`: State validation
11. `test_11_only_one_current_version_constraint`: Constraint enforcement
12. `test_12_version_number_uniqueness`: SQL constraint
13. `test_13_version_checksum_calculation`: Data integrity
14. `test_14_version_name_get`: Display name
15. `test_15_action_view_versions`: Action structure
16. `test_16_version_metadata`: Metadata capture
17. `test_17_restore_version_wizard`: Wizard functionality
18. `test_18_no_auto_version_when_disabled`: Conditional auto-versioning

## Usage Workflow

### Enabling Versioning

1. Open a file in form view
2. Click "Enable Versioning" button in header
3. System creates initial version (version 1)
4. Version History tab becomes visible

### Automatic Versioning

1. When versioning is enabled
2. Any content change triggers auto-version
3. New version created with comment "Auto-saved"
4. Previous versions marked as non-current

### Manual Versioning

```python
file_record._create_new_version(comment="Before major changes")
```

### Restoring a Version

**Method 1: From Version History Tab**

1. Open file form view
2. Go to "Version History" tab
3. Click "Restore" button on desired version
4. System creates backup, restores content, creates new version

**Method 2: From Version Form**

1. Open version record
2. Click "Restore This Version" button (hidden for current version)
3. Wizard opens with version details
4. Click "Restore Version"

**Method 3: Programmatically**

```python
file_record.action_restore_version(version_id)
```

### Disabling Versioning

1. Open file form view
2. Click "Disable Versioning" button
3. Confirm action
4. Versioning stops, history preserved

## Technical Details

### Version Numbering

- Sequential integers starting at 1
- Auto-incremented on each version creation
- Unique per file (SQL constraint)

### Content Storage

- Binary content stored as Odoo attachment
- Full snapshot (not delta-based)
- Checksum for integrity verification

### Current Version Management

- Only one version can be `is_current=True` per file
- Automatically managed by `_create_new_version()`
- Enforced by Python constraint

### Restore Process

1. Create backup version of current state (auto-saved)
2. Update file content with selected version content
3. Create new version for restored content (marked as current)

**Example**: Restoring version 2 when on version 5

- Before: Versions 1, 2, 3, 4, 5 (current)
- After: Versions 1, 2, 3, 4, 5, 6 (backup), 7 (current, restored from v2)

### Performance Considerations

- Each version stores full file content (not delta)
- Large files with many versions consume storage
- Consider periodic version pruning for large deployments
- Checksums use SHA512 for strong integrity

## Database Schema

```sql
-- spp_dms_file_version table
CREATE TABLE spp_dms_file_version (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES spp_dms_file ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    content BYTEA,  -- Stored as attachment
    checksum VARCHAR,
    size FLOAT,
    mimetype VARCHAR,
    created_by_id INTEGER REFERENCES res_users,
    created_date TIMESTAMP,
    comment TEXT,
    is_current BOOLEAN,
    UNIQUE(file_id, version_number)
);

-- Indexes
CREATE INDEX idx_file_version_file_id ON spp_dms_file_version(file_id);
CREATE INDEX idx_file_version_is_current ON spp_dms_file_version(is_current);
CREATE INDEX idx_file_version_checksum ON spp_dms_file_version(checksum);
CREATE INDEX idx_file_version_created_by ON spp_dms_file_version(created_by_id);
CREATE INDEX idx_file_version_created_date ON spp_dms_file_version(created_date);
```

## Logging

All version operations are logged at INFO level:

```python
_logger.info("Created version %d for file: file_id=%s, checksum=%s", ...)
_logger.info("Enabled versioning for file: file_id=%s", ...)
_logger.info("Disabled versioning for file: file_id=%s", ...)
_logger.info("Restored file from version: file_id=%s, restored_version=%d, new_version=%d", ...)
```

Failed auto-versioning logged at WARNING level (non-blocking).

## Future Enhancements (Not Implemented)

1. **Version Comparison**: Diff view between versions
2. **Version Pruning**: Automatic cleanup of old versions
3. **Delta Storage**: Store only changes for efficiency
4. **Version Tags**: Named versions (e.g., "v1.0", "Release")
5. **Version Notes**: Rich text comments with formatting
6. **Branching**: Multiple version branches
7. **Access Control**: Per-version permissions
8. **Version Search**: Search content across versions

## Migration Notes

- Existing files start with `is_versioned=False`
- No automatic migration of existing files
- Admins must manually enable versioning per file
- No data loss risk (versioning is opt-in)

## Version History

- **v1.4.0** (2025-12-14): Initial versioning implementation
  - spp.dms.file.version model
  - Auto-versioning on content change
  - Restore wizard
  - Comprehensive test coverage (18 tests)
  - Full UI integration

## Files Modified/Created

### Created

- `spp_dms/models/dms_file_version.py`
- `spp_dms/wizard/__init__.py`
- `spp_dms/wizard/restore_version_wizard.py`
- `spp_dms/wizard/restore_version_wizard_views.xml`
- `spp_dms/views/dms_file_version_views.xml`
- `spp_dms/tests/test_dms_file_version.py`

### Modified

- `spp_dms/__init__.py` (added wizard import)
- `spp_dms/models/__init__.py` (added dms_file_version import)
- `spp_dms/models/dms_file.py` (added versioning fields and methods)
- `spp_dms/views/dms_file_views.xml` (added versioning UI)
- `spp_dms/security/ir.model.access.csv` (added version model access)
- `spp_dms/tests/__init__.py` (added version test import)
- `spp_dms/__manifest__.py` (updated version to 1.4.0, added data files)

## Compliance with OpenSPP Standards

- ✅ Naming: `spp.dms.file.version` follows conventions
- ✅ Security: Three-tier access (admin CRUD, user read)
- ✅ Logging: Uses `_logger`, no PII in logs
- ✅ Error Handling: Specific exceptions (UserError, ValidationError)
- ✅ Testing: 18 test cases with @tagged decorator
- ✅ Documentation: Docstrings on all methods
- ✅ Odoo 19: Uses Command API patterns, proper constraints
- ✅ Performance: No `cr.commit()` in loops
- ✅ Code Quality: No `print()`, no bare `except:`
