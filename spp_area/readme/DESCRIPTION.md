Manages geographical administrative areas in hierarchical structures with bulk import from Excel files. Links registrants and beneficiary groups to areas for targeted program delivery and geographic access control. Supports multi-language translations and validation against area types.

### Key Capabilities

- Define hierarchical area structures with up to 10 levels (country, province, district, etc.)
- Assign unique codes and multi-language names to each area
- Import bulk area data from Excel files in COD (Common Operational Dataset) format from HDX
- Tag areas with classifications (urban, remote, priority) for filtering and reporting
- Link registrants and groups to their geographical areas
- Restrict user access to specific geographic areas via role-based area assignments
- Automatically detect and activate required languages during import

### Key Models

| Model                                | Description                                              |
| ------------------------------------ | -------------------------------------------------------- |
| `spp.area`                           | Hierarchical geographical area with code and name        |
| `spp.area.kind`                      | Area type definition (country, province, district, etc.) |
| `spp.area.tag`                       | Classification tags for areas                            |
| `spp.area.import`                    | Excel import wizard with validation and bulk processing  |
| `spp.area.import.raw`                | Staging table for import validation                      |
| `spp.area.import.json`               | Parsed JSON storage from Excel files                     |
| `spp.area.import.language.wizard`    | Wizard for activating languages during import            |

### Configuration

After installing:

1. Navigate to **Area > Areas > Area Type** to review default types
2. Create custom area types if needed
3. Import areas via **Area > Areas > Area Import**
4. Upload Excel file in COD format (ADM0_EN, ADM1_PCODE columns)
5. Click "Process File" to parse, validate, and review data
6. Review validation errors in Imported Data tab if any
7. Click "Save to Area Records" to finalize import

### UI Location

- **Area Menu**: Area > Areas > Area
- **Area Type Menu**: Area > Areas > Area Type
- **Area Tags Menu**: Area > Areas > Area Tags
- **Import Menu**: Area > Areas > Area Import
- **Registrant Form**: Area field appears on registrant and group profile forms

### Views and Tabs

| View                 | Tabs/Pages                         |
| -------------------- | ---------------------------------- |
| Area form            | Child Areas                        |
| Area Tag form        | Areas                              |
| Area Import form     | Imported Data, JSON Batches        |

### Security

| Group                        | Access                                    |
| ---------------------------- | ----------------------------------------- |
| `group_area_viewer`          | Read-only access to areas and types       |
| `group_area_officer`         | Create and edit areas, types, and tags    |
| `group_area_manager`         | Full CRUD including delete and imports    |
| `spp_security.group_spp_admin` | Full access (inherits manager)           |

### Extension Points

- Inherit `spp.area` to add custom fields or computed attributes
- Override `_prepare_domain()` in models to customize area-based filtering logic
- Extend `spp.area.import.raw` to add custom validation rules for imports
- Inherit `spp.area.tag` to add domain-specific classification schemes

### Dependencies

`base`, `spp_base_common`, `spp_user_roles`, `spp_registry`, `queue_job`, `spp_security`
