# OpenSPP Linting Scripts

Custom linting checks for OpenSPP modules to enforce development principles and coding standards.

## Overview

These scripts automate enforcement of [OpenSPP Development Principles](../../docs/principles/):

| Check              | Principle                                                                                                         | Severity | Auto-Fix |
| ------------------ | ----------------------------------------------------------------------------------------------------------------- | -------- | -------- |
| PII in Logs        | [error-handling.md](../../docs/principles/error-handling.md)                                                      | Warning  | No       |
| g2p Namespace      | [naming-conventions.md](../../docs/principles/naming-conventions.md) + ADR-001                                    | Warning  | No       |
| Naming Conventions | [naming-conventions.md](../../docs/principles/naming-conventions.md)                                              | Error    | No       |
| XML ID Patterns    | [naming-conventions.md](../../docs/principles/naming-conventions.md)                                              | Error    | No       |
| ACL Files          | [access-rights.md](../../docs/principles/access-rights.md)                                                        | Warning  | No       |
| Logger Setup       | [error-handling.md](../../docs/principles/error-handling.md)                                                      | Warning  | No       |
| Performance        | [performance-scalability.md](../../docs/principles/performance-scalability.md)                                    | Warning  | No       |
| UI Patterns        | [ui-design.md](../../docs/principles/ui-design.md) + [ui-performance.md](../../docs/principles/ui-performance.md) | Warning  | No       |

## Features

- **Unified Runner**: Run all checks with a single command (`openspp_lint.py`)
- **Multiple Output Formats**: text, json, github (for CI annotations)
- **Configuration File**: Customize via `.openspp-lint.yaml`
- **Severity Levels**: ERROR, WARNING, INFO with filtering
- **Suggestions**: Each violation includes fix suggestions and doc links
- **VS Code Integration**: Tasks and settings for in-editor feedback

## Quick Start

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run unified linter
python scripts/lint/openspp_lint.py --summary

# Run on specific module
python scripts/lint/openspp_lint.py --module spp_programs

# Run specific checks
python scripts/lint/openspp_lint.py --check naming xml_ids

# Output in JSON for CI
python scripts/lint/openspp_lint.py --format json

# Only show errors
python scripts/lint/openspp_lint.py --severity error
```

## Configuration

Create `.openspp-lint.yaml` in your project root to customize linting behavior:

```yaml
# OpenSPP Lint Configuration

# Module-specific overrides
modules:
  spp_api:
    allow_model_patterns:
      - "spp_api.*"

# Rule configurations
rules:
  naming:
    # Additional Boolean field exceptions
    boolean_exceptions:
      - "bidirectional"
      - "recurring"
    # Additional verb prefixes for Boolean fields
    boolean_verb_prefixes:
      - "compute_"
      - "generate_"
    # Additional Many2one exceptions (fields that don't need _id suffix)
    many2one_exceptions:
      - "parent"
      - "company"
      - "currency"

  xml_ids:
    # Allow legacy patterns during migration
    allow_legacy_patterns: false

  performance:
    # Threshold for N+1 warning
    n_plus_one_threshold: 1

# Severity overrides (change default severity for rules)
# Valid values: error, warning, info
severity:
  naming.boolean_prefix: warning
  naming.many2one_suffix: warning
  performance.offset_pagination: info

# Patterns to ignore (glob patterns)
ignore:
  - "**/migrations/**"
  - "**/tests/**"
  - "**/__pycache__/**"
```

## Individual Scripts

### 1. Unified Runner (`openspp_lint.py`)

Runs all checks in a single command with combined output.

```bash
# Run all checks
python scripts/lint/openspp_lint.py

# Run with summary
python scripts/lint/openspp_lint.py --summary

# Run specific checks
python scripts/lint/openspp_lint.py --check naming xml_ids acl

# Output in different formats
python scripts/lint/openspp_lint.py --format json
python scripts/lint/openspp_lint.py --format github  # For CI annotations

# Filter by severity
python scripts/lint/openspp_lint.py --severity error
python scripts/lint/openspp_lint.py --severity warning
```

### 2. Naming Conventions (`check_naming.py`)

Validates:

- Module names follow `spp_*` pattern
- Model names use `spp.*` namespace (not `g2p.*`)
- Boolean fields use `is_*` or `has_*` prefix
- Many2one fields end with `_id`
- One2many/Many2many fields end with `_ids`
- Generic `kind` schema fields emit a warning (prefer `*_type` / `*_role`; allowed list: `in_kind` or config
  `kind_allowed`)

```bash
# Check module names
python scripts/lint/check_naming.py --check-modules

# Check Python files
python scripts/lint/check_naming.py spp_programs/models/*.py

# Output in JSON
python scripts/lint/check_naming.py --format json spp_programs/models/*.py
```

### 3. XML ID Patterns (`check_xml_ids.py`)

Validates XML record IDs follow conventions:

| Model                   | Pattern                  | Example                  |
| ----------------------- | ------------------------ | ------------------------ |
| `ir.ui.view`            | `view_{model}_{type}`    | `view_spp_program_form`  |
| `ir.actions.act_window` | `action_{model}`         | `action_spp_program`     |
| `ir.ui.menu`            | `menu_{model}`           | `menu_spp_program`       |
| `res.groups`            | `group_{domain}_{level}` | `group_registry_officer` |
| `ir.module.category`    | `category_spp_{domain}`  | `category_spp_registry`  |
| `ir.rule`               | `rule_{model}_{purpose}` | `rule_partner_company`   |

```bash
# Check specific module
python scripts/lint/check_xml_ids.py --module spp_grm

# Check specific files
python scripts/lint/check_xml_ids.py spp_grm/views/*.xml

# Enable strict mode
python scripts/lint/check_xml_ids.py --strict --module spp_grm
```

### 4. ACL Files (`check_acl.py`)

Checks that each module has `security/ir.model.access.csv`.

```bash
# Check all modules
python scripts/lint/check_acl.py

# Report only (no failure)
python scripts/lint/check_acl.py --check-only
```

### 5. Performance Anti-Patterns (`check_performance.py`)

Detects:

- **Offset pagination**: `.search(..., offset=...)` - use cursor-based instead
- **cr.commit() in loops**: Should use `queue_job` for batch processing
- **N+1 queries**: Related field access in loops without prefetch

```bash
python scripts/lint/check_performance.py spp_programs/models/*.py
```

### 6. Logger Setup (`check_logger.py`)

Checks:

- Files using logging have `_logger = logging.getLogger(__name__)`
- No PII in log messages

```bash
python scripts/lint/check_logger.py spp_registry_base/models/*.py
```

### 7. UI Patterns (`check_ui_patterns.py`)

Validates XML view patterns based on [ui-design.md](../../docs/principles/ui-design.md) and
[ui-performance.md](../../docs/principles/ui-performance.md):

- **XPath class**: XPath must use `hasclass()` not `@class` (Odoo 19 requirement)
- **Statusbar location**: Statusbar widget must be in `<header>` not `<sheet>`
- **Extension points**: Forms with tabs should have extension point placeholders
- **Large O2M editable**: Large O2M fields (>100 records) should not be editable

```bash
# Check specific module
python scripts/lint/check_ui_patterns.py --module spp_programs

# Check specific files
python scripts/lint/check_ui_patterns.py spp_programs/views/*.xml

# Output in JSON
python scripts/lint/check_ui_patterns.py --format json --module spp_grm
```

**Configuration**: Large models, search panel thresholds, and editable O2M exceptions are configurable in
`.openspp-lint.yaml` under `rules.ui`.

## Output Formats

### Text (default)

```
=== ERRORS (must fix) ===
❌ spp_example/models/model.py:15: Model uses deprecated 'g2p.example' namespace
    💡 Suggestion: Change to 'spp.example'
    📖 See: docs/principles/naming-conventions.md

=== WARNINGS (should fix) ===
⚠️  spp_example/models/model.py:20: Boolean field 'active_flag' should use 'is_' or 'has_' prefix
    💡 Suggestion: Rename to 'is_active_flag'

Summary: 1 error(s), 1 warning(s), 0 info
```

### JSON

```json
{
  "violations": [
    {
      "file": "spp_example/models/model.py",
      "line": 15,
      "column": 0,
      "message": "Model uses deprecated 'g2p.example' namespace",
      "rule_id": "naming.g2p_model",
      "severity": "error",
      "suggestion": "Change to 'spp.example'",
      "doc_link": "docs/principles/naming-conventions.md"
    }
  ],
  "summary": {
    "total": 1,
    "errors": 1,
    "warnings": 0,
    "info": 0
  }
}
```

### GitHub Actions

```
::error file=spp_example/models/model.py,line=15,col=0::Model uses deprecated 'g2p.example' namespace
::warning file=spp_example/models/model.py,line=20,col=0::Boolean field 'active_flag' should use 'is_' or 'has_' prefix
```

## VS Code Integration

The `.vscode/` folder includes:

- **tasks.json**: Pre-configured tasks for running linters
- **settings.json**: Editor settings for Python/XML
- **extensions.json**: Recommended extensions

### Running Tasks

1. Open Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`)
2. Type "Tasks: Run Task"
3. Select from available OpenSPP tasks:
   - `OpenSPP: Run All Linters`
   - `OpenSPP: Lint Current Module`
   - `OpenSPP: Check Naming Conventions`
   - `OpenSPP: Check Performance Anti-Patterns`
   - `OpenSPP: Check XML IDs`
   - `OpenSPP: Check ACL Files`

## Pre-commit Integration

All checks are configured in `.pre-commit-config.yaml`. The hooks run automatically on git commit.

```bash
# Run all hooks manually
pre-commit run --all-files

# Run specific hook
pre-commit run openspp-check-naming --all-files

# Skip a hook temporarily
SKIP=openspp-check-performance git commit -m "message"
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: OpenSPP Lint Checks
  run: |
    python scripts/lint/openspp_lint.py --format github --severity error

- name: OpenSPP Lint Report
  run: |
    python scripts/lint/openspp_lint.py --format json > lint-report.json
  continue-on-error: true

- name: Upload Lint Report
  uses: actions/upload-artifact@v4
  with:
    name: lint-report
    path: lint-report.json
```

## Troubleshooting

### Suppressing False Positives

Add exceptions to `.openspp-lint.yaml`:

```yaml
rules:
  naming:
    boolean_exceptions:
      - "my_custom_field"
    many2one_exceptions:
      - "my_special_field"
```

Or add to script whitelists:

- **Module names**: `MODULE_WHITELIST` in `check_naming.py`
- **Model names**: `STANDARD_MODEL_WHITELIST` in `check_naming.py`
- **XML patterns**: `EXCEPTION_PATTERNS` in `check_xml_ids.py`

### Common Issues

1. **"No violations found" but hook fails**: Check if files match the hook's type filter
2. **Config not loading**: Ensure `.openspp-lint.yaml` is in project root
3. **Import errors**: Run from project root directory

## References

| Document                                                                                       | Purpose                     |
| ---------------------------------------------------------------------------------------------- | --------------------------- |
| [docs/principles/naming-conventions.md](../../docs/principles/naming-conventions.md)           | Module, model, field naming |
| [docs/principles/access-rights.md](../../docs/principles/access-rights.md)                     | ACL and security groups     |
| [docs/principles/error-handling.md](../../docs/principles/error-handling.md)                   | Logging and PII             |
| [docs/principles/performance-scalability.md](../../docs/principles/performance-scalability.md) | Performance patterns        |
| [ADR-001](../../docs/architecture/decisions/ADR-001-namespace-migration.md)                    | g2p -> spp migration        |

---

**Maintained by**: OpenSPP Development Team **Last Updated**: 2025-11-26
