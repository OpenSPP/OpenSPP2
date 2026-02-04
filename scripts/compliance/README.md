# OpenSPP Access Management Compliance Framework

A declarative framework for enforcing and verifying access control compliance across all
OpenSPP modules.

## Overview

This framework provides:

1. **Declarative Specifications** (`compliance.yaml`) - Define expected access control
   in YAML
2. **Static Checker** (`checker.py`) - Validate module configuration against specs
3. **Test Generator** (`test_generator.py`) - Generate runtime tests from specs
4. **CI Integration** - Fail builds on compliance violations

## Quick Start

```bash
# Check a single module
python -m scripts.compliance.checker spp_registry_base

# Check all modules with compliance.yaml
python -m scripts.compliance.checker --all

# Generate detailed report
python -m scripts.compliance.checker --all --report --format markdown

# Generate runtime tests
python -m scripts.compliance.test_generator spp_registry_base
```

## Creating a compliance.yaml

Create `security/compliance.yaml` in your module:

```yaml
module: spp_my_module
domain: my_domain
version: "1.0"

# Group definitions (ADR-004 three-tier)
groups:
  # Tier 3: Technical
  - id: group_my_domain_read
    tier: 3
    comment: "Read access"

  # Tier 2: User-facing
  - id: group_my_domain_viewer
    tier: 2
    privilege_id: privilege_my_domain_viewer
    implied_ids: [group_my_domain_read]

  - id: group_my_domain_officer
    tier: 2
    privilege_id: privilege_my_domain_officer
    implied_ids: [group_my_domain_viewer]

  - id: group_my_domain_manager
    tier: 2
    privilege_id: privilege_my_domain_manager
    implied_ids: [group_my_domain_officer]

admin_link_group: group_my_domain_manager

# Model access (ir.model.access.csv)
model_access:
  - model: my.model
    viewer: [read]
    officer: [read, write, create]
    manager: [read, write, create, unlink]

# Record rules (ir.rule)
record_rules:
  - id: rule_my_model_company
    model: my.model
    groups: []
    domain_description: "Company isolation"
    is_global: true

# Menu visibility
menus:
  - id: menu_my_domain_root
    name: "My Domain"
    groups: [group_my_domain_viewer, group_my_domain_officer, group_my_domain_manager]

  - id: menu_my_domain_config
    name: "Configuration"
    parent: menu_my_domain_root
    groups: [group_my_domain_manager]

# Field restrictions in views
field_restrictions:
  - view_id: view_my_model_form
    field_name: sensitive_field
    groups: [group_my_domain_manager]
    reason: "Only managers can see sensitive data"

# Action restrictions
actions:
  - id: action_dangerous_operation
    action_type: server
    name: "Dangerous Operation"
    groups: [group_my_domain_manager]
```

## What Gets Checked

### Static Analysis (checker.py)

| Check                | Severity | Description                            |
| -------------------- | -------- | -------------------------------------- |
| Group existence      | ERROR    | All defined groups exist in XML        |
| Group hierarchy      | WARNING  | implied_ids match specification        |
| Privilege assignment | WARNING  | Tier 2 groups have privilege_id        |
| ACL completeness     | ERROR    | All models have required ACL entries   |
| ACL permissions      | WARNING  | Permissions match specification        |
| Record rule patterns | ERROR    | No empty domain_force with write perms |
| Menu groups          | WARNING  | Menus have expected group restrictions |
| Action groups        | WARNING  | Actions have expected restrictions     |
| Admin linkage        | WARNING  | Manager linked to admin group          |

### Runtime Tests (test_generator.py)

Generated tests validate:

1. **Group hierarchy** - `implied_ids` work correctly at runtime
2. **Model CRUD** - Users can/cannot perform expected operations
3. **Menu visibility** - Correct menus appear for each role
4. **Action access** - Users can/cannot execute restricted actions

## Schema Reference

### groups

```yaml
groups:
  - id: group_id # Required: XML ID of the group
    tier: 2 # Required: 1=role, 2=functional, 3=technical
    privilege_id: priv_id # Optional: Required for tier 2
    implied_ids: [group_a] # Optional: Groups this implies
    comment: "Description" # Optional: Documentation
```

### model_access

```yaml
model_access:
  - model: model.name # Required: Odoo model name
    viewer: [read] # Permissions for viewer role
    officer: [read, write, create]
    manager: [read, write, create, unlink]
    custom: # Optional: Custom roles
      approver: [read, write]
```

Valid permissions: `read`, `write`, `create`, `unlink`

### record_rules

```yaml
record_rules:
  - id: rule_id # Required: XML ID
    model: model.name # Required: Model the rule applies to
    groups: [group_a] # Groups this rule applies to (empty = global)
    domain_description: "..." # Human description of domain
    is_global: false # Whether this is a global rule
    perm_read: true # Permissions this rule affects
    perm_write: false
    perm_create: false
    perm_unlink: false
```

### menus

```yaml
menus:
  - id: menu_id # Required: XML ID
    name: "Menu Name" # Human-readable name
    parent: parent_menu_id # Optional: Parent menu
    groups: [group_a, group_b] # Groups that should see this menu
```

### field_restrictions

```yaml
field_restrictions:
  - view_id: view_id # Required: View XML ID
    field_name: field # Required: Field name
    groups: [group_a] # Groups that can see this field
    reason: "Why restricted" # Optional: Documentation
```

### actions

```yaml
actions:
  - id: action_id # Required: Action XML ID
    action_type: act_window # Type: act_window, server, report
    name: "Action Name" # Human-readable name
    groups: [group_a] # Groups that can execute
```

## CI Integration

Add to your CI pipeline:

```yaml
# .github/workflows/compliance.yml
name: Access Control Compliance

on: [push, pull_request]

jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Check Compliance
        run: |
          python -m scripts.compliance.checker --all --errors-only
          if [ $? -ne 0 ]; then
            echo "Compliance check failed!"
            exit 1
          fi

      - name: Generate Report
        if: always()
        run: |
          python -m scripts.compliance.checker --all --report > compliance_report.md

      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: compliance-report
          path: compliance_report.md
```

## Best Practices

### 1. Start with the Spec

Before implementing access control, write the `compliance.yaml` first. This ensures you
think through the security model.

### 2. Use Standard Patterns

Follow ADR-004 three-tier architecture:

- **Tier 3**: Technical groups (read, write, create)
- **Tier 2**: User-facing groups (viewer, officer, manager)
- **Tier 1**: Composite roles (optional)

### 3. Document Restrictions

Use the `reason` and `comment` fields to explain why restrictions exist. This helps
future maintainers.

### 4. Test Critical Paths

Generate tests and run them regularly:

```bash
# Generate tests
python -m scripts.compliance.test_generator spp_my_module

# Run tests
pytest spp_my_module/tests/test_compliance_generated.py -v
```

### 5. Review Reports

Regularly generate and review compliance reports:

```bash
python -m scripts.compliance.checker --all --report > COMPLIANCE_REPORT.md
```

## Troubleshooting

### "Expected group not found"

The group defined in compliance.yaml doesn't exist in `security/groups.xml`.

**Fix**: Add the group to groups.xml or remove from compliance.yaml.

### "Missing ACL entry"

The model defined in compliance.yaml doesn't have a corresponding entry in
`ir.model.access.csv`.

**Fix**: Add the ACL entry to ir.model.access.csv.

### "Empty domain with write permissions"

A record rule has `domain_force="[]"` with write permissions, which is a security
anti-pattern.

**Fix**: Use `[(1, '=', 1)]` for "see all" pattern, never empty `[]`.

### "Menu has no group restrictions"

A menu is expected to have group restrictions but none are defined.

**Fix**: Add `groups="group_a,group_b"` attribute to the menuitem.

## Architecture

```
scripts/compliance/
  __init__.py          # Package exports
  schema.py            # Dataclass definitions for spec
  loader.py            # YAML loading and parsing
  checker.py           # Static compliance checker
  test_generator.py    # Runtime test generator
  README.md            # This documentation

spp_*/security/
  compliance.yaml      # Module-specific compliance spec
  groups.xml           # Actual group definitions
  privileges.xml       # Privilege definitions
  rules.xml            # Record rules
  ir.model.access.csv  # ACL entries
```

## Related Documentation

- [ADR-004: Access Rights Management](../docs/architecture/decisions/ADR-004-access-rights-management.md)
- [Access Rights Principles](../docs/principles/access-rights.md)
- [Naming Conventions](../docs/principles/naming-conventions.md)
