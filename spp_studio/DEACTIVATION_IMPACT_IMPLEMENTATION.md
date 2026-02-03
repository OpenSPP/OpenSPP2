# Deactivation Impact Warnings Implementation

## Overview

Implemented impact warnings when deactivating Studio configurations in OpenSPP Studio, as specified in section 2.3 of
the spec:

> "Deactivating shows impact warning ('This field is used by 1,247 records')"

## What Was Implemented

### 1. Deactivation Confirmation Wizard

**File**: `/wizard/deactivate_wizard.py`

- Transient model `spp.studio.deactivate.wizard`
- Displays impact warnings before deactivation
- Extracts record count from impact messages (handles formatted numbers like "1,247")
- Provides Confirm/Cancel actions
- Logs deactivation decisions

**Fields**:

- `config_model`: Model name of configuration being deactivated
- `config_id`: ID of configuration record
- `config_name`: Display name (computed)
- `config_type`: Type of configuration (computed)
- `impact_message`: Warning message from model's `_get_deactivation_impact()`
- `record_count`: Extracted count of affected records (computed)

### 2. Wizard View

**File**: `/wizard/deactivate_wizard_views.xml`

- Clean, user-friendly warning dialog
- Shows configuration name and type
- Displays affected record count
- Shows detailed impact message
- Info box explaining data preservation
- Danger-styled "Confirm Deactivation" button
- Cancel button

### 3. Impact Checking Logic (Already Existed!)

The infrastructure for impact checking was already in place:

**`studio_mixin.py`** (lines 112-150):

- `action_deactivate()` calls `_get_deactivation_impact()`
- If impact exists, shows wizard via `_show_deactivation_warning()`
- Otherwise proceeds with `_do_deactivate()`

Each Studio model implements `_get_deactivation_impact()`:

#### **Studio Fields** (`spp_studio_fields/models/studio_field.py`, lines 288-306)

- Counts records where field has non-empty values
- Returns message: "This field contains data in N records. Deactivating will hide the field but preserve the data."

#### **Event Types** (`spp_studio_events/models/studio_event_type.py`, lines 257-273)

- Counts `spp.event.data` records using this event type
- Returns message: "This event type is used by N event record(s). Deactivating will hide the event type but preserve
  existing events."

#### **Change Request Types** (`spp_studio_change_requests/models/studio_change_request_type.py`, lines 263-279)

- Counts active/pending change requests of this type
- Returns message: "This change request type has N active or pending requests. Deactivating will prevent new requests
  but existing ones will remain."

#### **Eligibility Rules** (`spp_studio_eligibility/models/studio_eligibility_rule.py`, lines 265-278)

- Checks if rule is linked to a program
- Returns message: "This rule is linked to program 'X'. Deactivating will not remove the eligibility manager, but the
  rule can no longer be edited."

### 4. Security Access

**File**: `/security/ir.model.access.csv`

- Added access rules for wizard:
  - `access_studio_deactivate_wizard_editor`: For Studio Editors
  - `access_studio_deactivate_wizard_manager`: For Studio Managers

### 5. Tests

#### **Unit Tests** (`/tests/test_deactivate_wizard.py`)

- Wizard creation with context values
- Record count extraction (with/without commas)
- Config info computation
- Cancel action
- Error handling for invalid models/records

#### **Integration Tests** (`spp_studio_fields/tests/test_deactivation_impact.py`)

- Full deactivation flow with no data (no wizard)
- Full deactivation flow with data (shows wizard)
- Wizard confirmation actually deactivates
- Impact message format validation
- Config info computed correctly

### 6. Module Updates

**Files Modified**:

- `spp_studio/__init__.py`: Added wizard import
- `spp_studio/__manifest__.py`: Added wizard views to data files
- `spp_studio/tests/__init__.py`: Added wizard tests
- `spp_studio_fields/tests/__init__.py`: Added integration tests

## How It Works

### User Flow

1. **User clicks "Deactivate" on a Studio configuration**

   - System calls `action_deactivate()` on the configuration

2. **System checks for impact**

   - Calls model-specific `_get_deactivation_impact()`
   - Each model type has custom logic to count affected records

3. **If no impact (no data)**

   - Proceeds directly with `_do_deactivate()`
   - Configuration becomes inactive
   - No wizard shown

4. **If impact exists (data would be affected)**

   - Returns wizard action with impact message in context
   - Wizard opens showing:
     - Configuration name and type
     - Number of affected records
     - Detailed impact description
     - Warning that data will be preserved

5. **User decides**
   - **Cancel**: Closes wizard, configuration remains active
   - **Confirm**: Calls `_do_deactivate()`, configuration becomes inactive

### Example Impact Messages

**Field with 1,247 records:**

```
This field contains data in 1,247 records. Deactivating will hide
the field but preserve the data.
```

**Event type with 5 events:**

```
This event type is used by 5 event record(s). Deactivating will
hide the event type but preserve existing events.
```

**Change request type with pending requests:**

```
This change request type has 3 active or pending requests.
Deactivating will prevent new requests but existing ones will remain.
```

## Testing Results

All tests pass:

```
88 total | 88 passed | 100.0% pass rate | 0 failed | 0 errors | 0 skipped
✅ All tests passed!
```

## Files Created/Modified

### Created:

1. `/spp_studio/wizard/__init__.py`
2. `/spp_studio/wizard/deactivate_wizard.py`
3. `/spp_studio/wizard/deactivate_wizard_views.xml`
4. `/spp_studio/tests/test_deactivate_wizard.py`
5. `/spp_studio_fields/tests/test_deactivation_impact.py`
6. `/spp_studio/DEACTIVATION_IMPACT_IMPLEMENTATION.md` (this file)

### Modified:

1. `/spp_studio/__init__.py`
2. `/spp_studio/__manifest__.py`
3. `/spp_studio/security/ir.model.access.csv`
4. `/spp_studio/tests/__init__.py`
5. `/spp_studio_fields/tests/__init__.py`

## Notes

- All existing `_get_deactivation_impact()` implementations were already in place
- The wizard integrates seamlessly with existing lifecycle management
- Data is never deleted - only hidden by deactivation
- Users can reactivate configurations later if needed
- Logging tracks all deactivation decisions for audit purposes
