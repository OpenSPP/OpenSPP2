# OpenSPP Development Guidelines

Social protection platform built on Odoo 19. ~90 modules (`spp_*`).

## Principles (MUST read before changes)

All principles are in `docs/principles/`:

- [naming-conventions.md](docs/principles/naming-conventions.md) - Module, model, field, security group naming
- [access-rights.md](docs/principles/access-rights.md) - Three-tier security architecture
- [module-architecture.md](docs/principles/module-architecture.md) - Module organization and extension patterns
- [module-visibility.md](docs/principles/module-visibility.md) - application, auto_install, and category settings
- [api-design.md](docs/principles/api-design.md) - External identifiers, never expose DB IDs
- [performance-scalability.md](docs/principles/performance-scalability.md) - Batch processing with queue_job
- [testing.md](docs/principles/testing.md) - Coverage targets (85%+ for core)
- [approval-workflows.md](docs/principles/approval-workflows.md) - State machines and mixins
- [error-handling.md](docs/principles/error-handling.md) - Exceptions, logging, no PII in logs
- [audit-compliance.md](docs/principles/audit-compliance.md) - Audit trails, data integrity
- [ui-design.md](docs/principles/ui-design.md) - Form layouts, tabs, multi-column patterns
- [pretty-urls.md](docs/principles/pretty-urls.md) - User-friendly URL paths for actions
- [odoo19-compatibility.md](docs/principles/odoo19-compatibility.md) - Odoo 19 gotchas (constraints, views, Command API)
- [consent-data-sharing.md](docs/principles/consent-data-sharing.md) - Consent management, notice boundaries, data
  sharing
- [module-descriptions.md](docs/principles/module-descriptions.md) - Writing readme/DESCRIPTION.md files for modules

## Architecture

- [ADRs](docs/architecture/decisions/) - Architecture Decision Records

### Layered Architecture (Dependencies flow downward)

```
Layer 3: COUNTRY/DOMAIN EXTENSIONS (spp_4ps_*, spp_farmer_*)
    ↓
Layer 2: CAPABILITIES (spp_programs, spp_entitlement_*, spp_change_request_v2)
    ↓
Layer 1: FOUNDATION (spp_registry, spp_security, spp_area)
```

### Extension Patterns

- **Inherit and Extend**: `_inherit = "res.partner"` + add fields
- **Hook Methods**: `_pre_enrollment_hook()`, `_post_enrollment_hook()`
- **Never expose DB IDs** in APIs - use `spp.reg.id` external identifiers

## Quick Checklist

When auditing or modifying a module:

- [ ] Naming follows `spp_*` / `spp.*` conventions
- [ ] `application` and `auto_install` set correctly per [module-visibility](docs/principles/module-visibility.md)
- [ ] `ir.model.access.csv` exists and complete
- [ ] No `print()` - use `_logger`
- [ ] No bare `except:` clauses
- [ ] No `cr.commit()` in loops - use `queue_job`
- [ ] No PII in log messages
- [ ] Tests exist for core functionality

## Bug Fixing Approach

When fixing issues: first write a failing test that reproduces the bug, then fix it. Fix problems at the source (e.g.,
correct XML/ACL definitions) rather than working around them in tests or code. If a root fix isn't possible, document
why and propose alternatives.

## Known Pitfalls (from recurring issues)

### Access Rights (Most Common Error)

- **Always check `ir.model.access.csv`** before declaring a module complete
- When tests fail with `AccessError`, fix the ACL, don't bypass with `sudo()`
- Tests must run with appropriate user context (officer, manager), not just admin
- After security changes, **always re-run affected tests** - they often break
- Related models need ACLs too (e.g., if `spp.program` has ACL, `spp.program.membership` likely needs one)

### Demo Data

- Demo data must create **complete, consistent records** - check all required relations
- Approval states must match approval records (e.g., `approval_state='pending'` requires pending review records)
- Use `with_context(tracking_disable=True)` when creating demo data to avoid sending notifications
- Test demo data generation with dedicated tests that verify all expected records exist

### Views and XML

- XPath must use `hasclass('classname')` not `@class='classname'` (Odoo 19)
- Always use `Command.create()` not `(0, 0, {...})` tuples for relational writes
- When updating views, verify the correct view is being displayed (not cached old version)
- Search views: check `<filter>` and `<group>` syntax against Odoo 19 docs

### Tests

- **NEVER remove or weaken existing tests** without explicit approval
- After subagent implementations, verify: "Can you confirm no tests were removed or weakened?"
- When fixing security, tests often need user context updates - fix tests, don't skip them
- If tests cannot run due to install issues, fix the install, don't mark tests as skipped

### State Machines and Approvals

- `spp.approval.mixin` records must have consistent state:
  - `approval_state='pending'` → must have pending `spp.approval.review` records
  - `approval_state='approved'` → all reviews must be approved
- When creating test data for approval flows, create the full approval chain

### Self-Improvement

- After every correction or mistake, propose an update to this Known Pitfalls section
- After every PR, consider whether patterns or pitfalls were discovered that should be documented here

## Running OpenSPP Locally

**Quick Start** (Docker Compose with UI):

```bash
# Launch Odoo UI for development
docker compose --profile ui up -d

# Access at: http://localhost:8069 (admin/admin)

# Stop when done
docker compose --profile ui down
```

**With specific demo modules:**

```bash
# MIS Demo (full demo)
ODOO_INIT_MODULES=spp_mis_demo_v2 docker compose --profile ui up -d

# DRIMS Demo
ODOO_INIT_MODULES=spp_drims_sl_demo docker compose --profile ui up -d

# Base modules only
ODOO_INIT_MODULES=spp_base docker compose --profile ui up -d
```

**Clean restart:**

```bash
# Stop and remove volumes (fresh database)
docker compose --profile ui down -v
```

## Running Tests

**Recommended** (using the `spp` CLI, Docker-based, isolated):

```bash
./spp test <module_name>
# or short form:
./spp t <module_name>
```

This creates an isolated test environment and cleans up automatically. Supports parallel runs across multiple clones.

**Alternative** (direct script):

```bash
./scripts/test_single_module.sh <module_name>
```

## Linting and Compliance

**Using `spp` CLI** (preferred):

```bash
./spp lint                           # Lint changed files
```

**Pre-commit hooks** (run automatically, or manually):

```bash
pre-commit run ruff --files <changed_files>
pre-commit run ruff-format --files <changed_files>
pre-commit run prettier --files <changed_files>
```

**Security/Access Rights Audit**:

```bash
./.Codex/scripts/audit-security.sh          # Audit all modules
./.Codex/scripts/audit-security.sh spp_api  # Audit single module
./.Codex/scripts/fix-security.sh spp_api    # Auto-fix security issues (review changes!)
./.Codex/scripts/fix-security.sh --mechanical-only spp_api  # Only mechanical fixes (no AI)
```

**Module Audit** (requires cursor-agent):

```bash
./.Codex/scripts/audit-modules.sh           # Check module structure and compliance
./.Codex/scripts/audit-modules.sh spp_api   # Audit single module
./.Codex/scripts/audit-modules.sh --fix     # Auto-fix simple issues
```

**Lint Fixes**:

```bash
./.Codex/scripts/fix-lint.sh spp_api        # Run linters + AI-assisted fixes
./.Codex/scripts/fix-lint.sh --lint-only spp_api  # Run linters only, no AI
```

When linters suggest fixes, verify the suggestion is correct before applying. Some automated fixes may:

- Use wrong syntax for Odoo 19
- Remove intentional patterns
- Break existing functionality

## Verification Workflow

Before marking any task complete:

1. **Run tests**: `./spp t <module>`
2. **Run linters**: `pre-commit run --files <changed_files>`
3. **Run security audit** (if security changed): `./.Codex/scripts/audit-security.sh <module>`
4. **Verify no tests were removed**: `/verify-tests` or compare test count before/after
5. **Check demo data** (if modified): Verify records are created correctly
6. **Test in UI** (for UX changes): Confirm the correct view is displayed

## Custom Commands

Available slash commands in `.Codex/commands/`:

| Command          | Purpose                                                        |
| ---------------- | -------------------------------------------------------------- |
| `/commit`        | Create conventional commit (feat/fix/chore/docs/refactor/test) |
| `/implement`     | Full TDD workflow with subagents and expert review             |
| `/expert-review` | Parallel code review from multiple perspectives                |
| `/pr`            | Create GitHub PR with OpenProject linking                      |
| `/op-task`       | Implement OpenProject task end-to-end                          |
| `/verify-tests`  | Check test integrity after changes (catch removed tests)       |
| `/analyze`       | Deep analysis mode - understand before implementing            |

### When to Use Each

- **Starting work**: Enter Plan mode (shift+tab twice) for brainstorming
- **Implementing**: `/implement` for full TDD workflow
- **After subagent work**: `/verify-tests` to catch removed tests
- **Debugging**: `/analyze` for structured error/code analysis
- **Before commit**: `/commit` for conventional commit format
- **Creating PR**: `/pr` with OpenProject linking

## Subagents

Available agents in `.Codex/agents/`:

| Agent              | Model  | Use For                                |
| ------------------ | ------ | -------------------------------------- |
| `@odoo-developer`  | sonnet | Core implementation work               |
| `@code-reviewer`   | opus   | Security, naming, Odoo 19 compliance   |
| `@ux-expert`       | opus   | UI/UX patterns and form layouts        |
| `@code-simplifier` | sonnet | Reduce complexity, improve readability |
| `@verify-module`   | sonnet | Test module installation and tests     |
