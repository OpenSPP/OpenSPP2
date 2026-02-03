Foundation security infrastructure for OpenSPP modules. Defines 22 domain-specific security categories, the central Administrator group, two base record rules for multi-company and self-only access, and the privilege framework. Domain modules register their security groups within these predefined categories.

### Key Capabilities

- Define 22 domain-specific security categories (Registry, Programs, Entitlements, GRM, etc.) organizing security groups in user settings UI
- Provide central Administrator group (`group_spp_admin`) that automatically inherits all manager-level permissions from installed domain modules
- Implement multi-company record rule for `res.partner` restricting access to records from user's companies
- Implement self-only record rule for `res.users` restricting users in `group_access_restrict_self` to viewing only their own user record
- Link Odoo system administrators (`base.group_system`) to automatically inherit OpenSPP Administrator privileges

### Configuration

No configuration required. This module provides infrastructure only. When domain modules are installed, their security groups automatically appear under the appropriate category in **Settings > Users & Companies > Users**.

### Security

This module defines no model access rights (empty `ir.model.access.csv`). It provides only security groups and record rules.

| Group                     | XML ID                       | Purpose                                           |
| ------------------------- | ---------------------------- | ------------------------------------------------- |
| Administrator             | `group_spp_admin`            | Inherits all manager permissions from all domains |
| Restricted: Self Only     | `group_access_restrict_self` | Restricts users to viewing only their own record  |

Record rules:

- `rule_partner_company`: Multi-company access for `res.partner` (company_ids filter)
- `rule_user_self_only`: Self-only access for `res.users` (applied to `group_access_restrict_self`)

### Extension Points

Domain modules must follow this pattern to integrate with the security framework:

1. Add `spp_security` to `depends` in `__manifest__.py`
2. Define privileges referencing categories like `spp_security.category_spp_registry`
3. Create domain-specific groups (Viewer, Officer, Manager) linked to those privileges
4. Link the Manager group to `spp_security.group_spp_admin` using `implied_ids` so admins automatically inherit domain permissions

Example from a domain module's `security/groups.xml`:

```xml
<record id="spp_security.group_spp_admin" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_registry_manager'))]"/>
</record>
```

### Available Categories

Administration: `category_spp_admin`

Domain categories: `category_spp_registry`, `category_spp_programs`, `category_spp_scoring`, `category_spp_entitlements`, `category_spp_change_request`, `category_spp_approvals`, `category_spp_payments`, `category_spp_grm`, `category_spp_case`, `category_spp_health_monitoring`, `category_spp_hazard`, `category_spp_drims`, `category_spp_farmer`, `category_spp_service_points`, `category_spp_area`, `category_spp_identity`, `category_spp_api`, `category_spp_audit`, `category_spp_graduation`, `category_spp_services`, `category_spp_sessions`

Empty categories are automatically hidden by Odoo. Categories only appear when domain modules install groups under them.

### Architecture

Categories are centrally defined in `spp_security` but security groups are distributed to domain modules. This design ensures groups only exist when their domain module is installed, preventing UI clutter from unused permissions and enabling flexible installation combinations.

### Dependencies

`base`
