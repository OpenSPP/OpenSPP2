Advanced search interface for the registry using CEL (Common Expression Language) expressions. Provides a dedicated portal where users can write CEL queries to filter registrants based on demographics, eligibility criteria, or custom data fields.

### Key Capabilities

- **CEL Expression Editor**: Write and validate CEL expressions with syntax highlighting, autocomplete, and real-time validation
- **Profile Selection**: Search across Individuals or Groups with profile-specific field validation
- **Live Validation**: See match counts before executing the search, with inline error messages for invalid syntax
- **Clickable Results**: View search results in a list, click any registrant to open their form view
- **Result Limiting**: Displays up to 50 results with a count indicator when more matches exist

### Key Models

This module does not define any Python models. It provides a client-side JavaScript component (`CelSearchPortal`) that calls `spp.cel.service` from `spp_cel_domain` to compile and execute CEL expressions.

### Configuration

No configuration required. After installation, the **Advanced Search** menu appears automatically under Registry.

### UI Location

- **Menu**: Registry > Advanced Search
- **URL Path**: `/odoo/registry-cel`
- **Results**: Click any search result to open the registrant form view

### Security

| Group                                      | Access                                      |
| ------------------------------------------ | ------------------------------------------- |
| `spp_cel_registry_search.group_cel_search_user` | Access to Advanced Search portal            |
| `spp_registry.group_registry_officer`      | Automatically includes CEL Search access    |

The `group_cel_search_user` group implies `spp_registry.group_registry_viewer`, ensuring users can only search registrants they have permission to view.

### Extension Points

- **Inherit `CelSearchPortal` component**: Override `performSearch()` to customize query logic or add filters
- **Extend result display**: Modify the QWeb template `spp_cel_registry_search.CelSearchPortal` to show additional registrant fields
- **Add custom actions**: Override `openRegistrant()` to trigger custom workflows when clicking search results

### Dependencies

`spp_registry`, `spp_cel_domain`, `spp_cel_widget`
