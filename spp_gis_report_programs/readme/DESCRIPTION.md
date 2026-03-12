Auto-install glue module that adds program context filtering to GIS reports. Extends GIS report models and wizard to filter geographic data by program enrollment, enabling program-specific spatial analysis and visualization.

### Key Capabilities

- Filter GIS reports to show only registrants enrolled in a specific program
- Add program selector to report forms and wizard interface
- Validate program selection requirements before generating reports
- Include program identifier in generated report codes
- Grant GIS report access to program officers and managers

### Key Models

- `spp.gis.report` — Adds `program_id` field and filters domain by program members
- `spp.gis.report.wizard` — Adds `program_id` selection with validation and code suffix

### Configuration

No configuration required. Auto-installs when both `spp_gis_report` and `spp_programs` are present.

### UI Location

- **Report Form**: Program field appears in the "context_group" on GIS report forms (accessed via **GIS Reports > Reports**)
- **Wizard**: Program field appears in the "context_filters" group when generating reports from templates

### Security

- `spp_programs.group_programs_officer` — Read GIS reports, data, templates, etc.
- `spp_programs.group_programs_manager` — Read/Write (no create/unlink) all models
- `spp_gis_report.group_gis_report_user` — Implied for program managers via XML

Models with access: `spp.gis.report`, `spp.gis.report.data`, `spp.gis.report.threshold`, `spp.gis.report.template`, `spp.gis.report.category`

### Extension Points

- Override `_apply_context_filters()` on `spp.gis.report` to add custom program-based filtering
- Override `_validate_context_requirements()` on `spp.gis.report.wizard` for additional validation
- Override `_get_context_code_suffix()` to customize report code generation with program identifiers
- Override `_get_context_filter_vals()` to modify report creation values

### Dependencies

`spp_gis_report`, `spp_programs`
