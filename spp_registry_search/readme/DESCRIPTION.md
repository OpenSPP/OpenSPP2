Search-first registry interface that protects beneficiary privacy by requiring users to search before viewing registrants. Replaces browse-all list views with a custom search portal showing recently viewed records. Tracks view history per user and provides auditor-only bypass for compliance purposes.

### Key Capabilities

- Search-first landing page with no records loaded by default (privacy-by-design)
- Quick search across name, ID numbers, phone, and email with 3-character minimum
- Advanced filters for registrant type (individual/group) and registration date range
- Recently viewed section showing user's last 10 accessed registrants with avatars
- Automatic view tracking when registrant forms are opened
- Archive/unarchive permission enforcement (officers and managers only)
- Auditor bypass group for browse-all access to full registrant lists

### Key Models

| Model                       | Description                                               |
| --------------------------- | --------------------------------------------------------- |
| `spp.registry.view.history` | Tracks user's recently viewed registrants with timestamps |
| `res.partner` (extended)    | Adds view tracking on form open and archive restrictions  |

### Configuration

After installing:

1. Navigate to **Settings > Users & Companies > Users**
2. Grant `Auditor (Browse All)` privilege only to users with legitimate audit responsibilities
3. Verify search portal appears at **Registry > Search** for registry users
4. Test that non-auditor users cannot access **Registry > Browse All (Audit)** submenu

### UI Location

- **Default landing**: Registry > Search (replaces individuals/groups menus for non-auditors)
- **Auditor menus**: Registry > Browse All (Audit) > All Individuals / All Groups
- **Recently viewed**: Displayed in search portal below the search form

### Security

| Group                                               | Access                                                           |
| --------------------------------------------------- | ---------------------------------------------------------------- |
| `spp_registry.group_registry_read`                  | Full CRUD on view history (restricted to own records via IR rule) |
| `spp_registry_search.group_registry_search_auditor` | Bypass search requirement, access browse-all menus               |

Archive/unarchive permission check enforces these groups:
- `base.group_system`
- `spp_security.group_spp_admin`
- `spp_registry.group_registry_manager`
- `spp_registry.group_registry_officer`

### Extension Points

- Override `res.partner.get_formview_action()` to customize view tracking behavior
- Inherit `spp.registry.view.history.get_recent_registrants()` to modify area filtering or result format
- Override `res.partner._check_archive_permission()` to add custom permission logic
- Extend OWL component `spp_registry_search.search_portal` to modify search interface

### Dependencies

`spp_registry`
