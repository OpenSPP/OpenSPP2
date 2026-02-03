Foundation registry module for OpenSPP that manages individuals, groups, and their relationships. Consolidates base registrant functionality, group membership tracking, ID document management, and relationship mapping. Extends `res.partner` to support social protection use cases.

### Key Capabilities

- Manage individual and group registrants with demographic fields (gender, birthdate, civil status, occupation)
- Track group membership with configurable roles, start/end dates, and automatic status computation
- Store and validate ID documents with regex-based validation and expiry tracking
- Define relationships between registrants (individual-to-individual, group-to-group, individual-to-group)
- Manage multiple phone numbers per registrant with validation and sanitization
- Tag registrants using vocabulary-based classification
- Disable registrants and relationships with audit trail (disabled date, disabled by, reason)

### Key Models

| Model                       | Description                                             |
| --------------------------- | ------------------------------------------------------- |
| `res.partner`               | Extended for registrant management (individuals/groups) |
| `spp.group.membership`      | Links individuals to groups with roles and dates        |
| `spp.registry.id`           | ID documents attached to registrants                    |
| `spp.id.type`               | ID type definitions with validation rules               |
| `spp.registry.relationship` | Relationships between registrants                       |
| `spp.relationship`          | Relationship type definitions                           |
| `spp.phone.number`          | Phone numbers with country-based validation             |

### Configuration

After installing:

1. Navigate to **Registry > Configuration** (requires Admin or Config Admin role)
2. Define ID types with optional regex validation under ID Types action
3. Configure relationship types and group membership types via vocabularies

### UI Location

- **Menu**: Registry (top-level menu)
- **Configuration**: Registry > Configuration
- **Form tabs** (Individuals): Profile, Identity, Participation, History
- **Form tabs** (Groups): Profile, Identity, Participation, History
- **Relationships**: Accessible from registrant forms under the "Identity" tab
- **Membership**: Accessible from individual forms under the "Participation" tab (group memberships) or group forms under the "Participation" tab (group members)

Note: This module defines no top-level menu items for Individuals or Groups lists. These actions are typically exposed by domain-specific modules (e.g., `spp_base_demo`).

### Security

| Group                                      | Access                      |
| ------------------------------------------ | --------------------------- |
| `spp_registry.group_registry_viewer`       | Read-only                   |
| `spp_registry.group_registry_officer`      | Read/Write/Create (no delete) |
| `spp_registry.group_registry_manager`      | Full CRUD                   |
| `spp_registry.group_registry_config_admin` | Configuration menu access   |

### Extension Points

- Inherit `res.partner` to add custom fields for individuals or groups
- Override `_compute_calc_age()` to customize age computation logic
- Inherit `spp.group.membership` to add domain-specific membership fields
- Override `count_individuals()` on `res.partner` to customize group member counting with complex filters
- Use `invalidate_group_metrics()` to trigger metric recalculation when group composition changes

### Dependencies

`base`, `mail`, `contacts`, `web`, `portal`, `phone_validation`, `spp_security`, `spp_vocabulary`, `muk_web_chatter`
