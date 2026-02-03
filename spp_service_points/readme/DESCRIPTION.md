Manages physical or virtual service delivery locations (agents, offices, or distribution centers) that interact with registrants. Service points can be linked to companies, assigned to geographic areas, classified by service type using vocabulary-based categorization, and enabled or disabled with reason tracking.

### Key Capabilities

- Create service points with contact information including phone validation and address
- Link service points to companies and automatically track company contacts as individuals
- Assign service points to hierarchical geographic areas via `spp.area`
- Classify service points using vocabulary codes in the `urn:openspp:vocab:service-types` namespace
- Enable and disable service points with date stamping and reason tracking
- Create user accounts for service point contacts with security group assignment
- Track contract status and operational state of each service point

### Key Models

| Model              | Description                                                    |
| ------------------ | -------------------------------------------------------------- |
| `spp.service.point` | Service delivery location with area assignment and type classification |

### Extends

| Model         | Fields Added                                              |
| ------------- | --------------------------------------------------------- |
| `res.partner` | `service_point_ids`, `individual_service_points_ids`      |
| `res.users`   | `service_point_ids` (related to partner service points)   |

### Configuration

After installing:

1. Navigate to **Vocabulary > Service Types** to define service type codes in the `urn:openspp:vocab:service-types` namespace
2. Verify phone validation settings match your country requirements

### UI Location

- **Menu**: Service Point > Service Points
- **Registrant Tab**: Accessible from registrant forms under the "Service Points" tab

### Security

| Group                                          | Access                     |
| ---------------------------------------------- | -------------------------- |
| `spp_security.group_spp_admin`                 | Full CRUD                  |
| `group_service_points_viewer`                  | Read                       |
| `group_service_points_officer`                 | Read/Write/Create (no delete) |
| `group_service_points_manager`                 | Full CRUD                  |
| `group_service_points_user`                    | Read/Write/Create (deprecated) |
| `spp_registry.group_registry_read`             | Read                       |
| `spp_registry.group_registry_write`            | Read/Write/Create (no delete) |

### Extension Points

- Inherit `spp.service.point` to add domain-specific fields or custom validation
- Override `_compute_phone_sanitized()` to customize phone formatting logic
- Extend service point forms via XPath to add tabs for country-specific requirements

### Dependencies

`spp_registry`, `phone_validation`, `spp_area`, `spp_security`, `spp_vocabulary`
