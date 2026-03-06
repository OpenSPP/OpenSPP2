Extends case management with program entitlement tracking. Links cases to entitlements via many2many relationship, computes statistics (total, approved, pending counts and value), and provides filtered views. Auto-loads beneficiary entitlements when partner is selected.

### Key Capabilities

- Link multiple entitlements to a case via many2many relationship
- Auto-populate entitlements when case partner is selected
- Compute entitlement statistics: total count, approved count, pending count, total value
- Filter entitlements by state (all, approved, pending) via dedicated action methods
- Display entitlement counts and status in list, kanban, and form views
- Search and group cases by entitlement status

### Extended Models

| Model      | Description                                                  |
| ---------- | ------------------------------------------------------------ |
| `spp.case` | Extended with entitlement relationships and computed metrics |

### Configuration

No configuration required. The module auto-installs when both `spp_case_base` and `spp_programs` are installed.

### UI Location

- **Menu**: Case Management > Cases > All Cases
- **Smart Buttons**: Case form header displays total, approved, and pending entitlement counts
- **Tab**: "Entitlements" tab on case form with summary statistics and entitlement list
- **List Columns**: Entitlement count and approved count appear in case list view
- **Kanban Icons**: Entitlement indicators appear in case kanban cards
- **Search Filters**: "Has Entitlements", "No Entitlements", "Has Approved Entitlements", "Has Pending Entitlements"

### Security

| Group                              | Access                        |
| ---------------------------------- | ----------------------------- |
| `spp_case_base.group_case_officer` | Read/Write/Create (no delete) |
| `spp_case_base.group_case_manager` | Full CRUD                     |

### Extension Points

- Override `_compute_entitlement_info()` to customize entitlement statistics or add domain-specific calculations
- Override `_onchange_partner_entitlements()` to filter which entitlements auto-populate based on case criteria
- Inherit `action_view_entitlements()`, `action_view_approved_entitlements()`, or `action_view_pending_entitlements()` to modify entitlement list views or add filtering logic

### Dependencies

`spp_security`, `spp_case_base`, `spp_programs`
