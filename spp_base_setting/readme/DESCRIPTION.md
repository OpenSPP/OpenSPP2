Provides Country Office management and administrative UI configuration for OpenSPP implementations. Extends `res.company` to represent organizational units (national, regional, district offices) and adds user/group management menus to the Registry configuration area. Establishes the administrative foundation required for multi-office deployments.

### Key Capabilities

- Define Country Offices as administrative units using company records with custom form and list views
- Organize hierarchical office structures through parent-child company relationships
- Expose user and group management in the Registry configuration menu
- Provide standardized Country Office form including address, contact details, currency, and branding

### Key Models

| Model         | Description                                         |
| ------------- | --------------------------------------------------- |
| `res.company` | Extended to represent Country Offices in OpenSPP    |
| `res.users`   | Accessible via Registry configuration menu          |
| `res.groups`  | Accessible via Registry configuration menu (admins) |

### Configuration

After installing:

1. Navigate to **Registry > Configuration > Users** to manage user accounts
2. Navigate to **Registry > Configuration > Groups** (system admins only) to manage security groups
3. Access Country Offices through Settings or by direct action reference (no standalone menu provided)

### UI Location

- **User Management**: Registry > Configuration > Users
- **Group Management**: Registry > Configuration > Groups (system admins only, `base.group_no_one`)
- **Country Offices**: No standalone menu; accessed via `action_res_country_office` action or Settings

### Form Views

The Country Office form (`view_country_office_form`) includes one tab:

- **General Information**: Address fields, phone, email, website, VAT, currency, and parent office

### Security

This module does not define custom security groups. Access to Country Office management and user/group configuration follows standard Odoo security rules:

- User management requires standard Odoo access rights
- Group management restricted to `base.group_no_one` (system admins)
- Country Office (company) records follow `res.company` access rules

### Extension Points

- Inherit `res.company` to add Country Office-specific fields (e.g., office codes, regional metadata)
- Override `view_country_office_form` to customize the Country Office form layout
- Extend the "social_media" placeholder group in the Country Office form to add social media fields

### Dependencies

`spp_security`, `base`, `spp_registry`
