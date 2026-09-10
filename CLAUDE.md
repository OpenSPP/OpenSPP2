# OpenSPP2 — Contributor & PR Review Guide

OpenSPP2 is an Odoo 19 monorepo of OpenSPP addons. This file is the **repo-wide
source of truth for how we review pull requests** — for human reviewers and for
AI-assisted review (Claude Code auto-loads it). The PR template links here.

> **Status: proposal.** Opened for the team to weigh in — refine, cut, or add
> rules as we agree on them.

## PR Review Checklist

When reviewing a PR, explicitly check each of these and cite `file:line` for
anything raised:

### 1. Correctness

- **Deleted code** — diff *both* directions. Count deleted test methods and
  confirm coverage isn't quietly dropped.
- **Runtime behavior** — verify the changed path actually works (drive it or run
  the module's tests), not just that the code reads correctly. A "column-shape"
  test can pass green while the total is wrong.
- **Dependency completeness** — trace what happens when an *optional* dependency
  isn't installed.
- **Edge cases** — None/empty handling; migrations (`migrations/*`) must be
  idempotent and safe to re-run.

### 2. Scope

- Flag unrelated changes bundled into one PR. Prefer one concern per PR — it
  makes review and rollback cleaner.

### 3. Release hygiene — REQUIRED (the most-missed rule)

- **Every changed module gets a `readme/HISTORY.md` changelog entry AND a
  matching `__manifest__.py` version bump.** (See _Changelog & versioning_
  below.) This is the rule that most often slips — check it first.
- If any `readme/` fragment changed, **regenerate** `README.rst` and
  `static/description/index.html` with the OCA generator
  (`oca-gen-addon-readme`) and commit the regenerated files.

### 4. Odoo 19 compatibility

- `view_mode` uses **`list`**, not `tree`.
- No deprecated `attrs=` / `states=` — use `invisible=` / `readonly=` /
  `required=` expressions.
- Manifest `depends` is complete and correct.
- The `openspp-check-odoo19-python` / `openspp-check-odoo19-xml` pre-commit
  hooks catch common cases, but the reviewer still verifies.

### 5. Security

- **No PII or secrets in logs** (`openspp-no-pii-in-logs`, `gitleaks`).
- **API v2 / DCI / controllers:** endpoints are authenticated; JWT is
  algorithm-pinned with audience/issuer validated; token comparisons are
  constant-time; no unauthenticated PII exposure; **SQL is parameterized** (no
  string-interpolated queries); controller routes set `auth=` correctly.
- New models have **ACLs** (`openspp-check-acl`); XML IDs follow naming
  (`openspp-check-xml-ids`); no over-broad `sudo()` (scope + annotate).

### 6. Tests

- CI runs the module test matrix on PRs, but **run the affected module's suite
  locally** too before opening/updating — and again after a rebase (git merges
  text, not behavior). See _Running tests_.
- **Pre-commit must be clean** via the CI-matching container — see _Pre-commit_.

## Review protocol (esp. for AI-assisted review)

- **Recommend first**, then get maintainer confirmation **before submitting a
  formal GitHub review** (Approve / Request changes).
- **Verify load-bearing claims against the actual code** — don't rely on the PR
  description; spot-check the riskiest assertions.
- **Run the tests.** A green PR check is not proof everything passes.

## Changelog & versioning (`readme/HISTORY.md`)

Every module tracks changes in `readme/HISTORY.md`, rendered as the "Changelog"
in the generated `README.rst`.

```
### {version}          # must match `version` in __manifest__.py

- type(scope): description (#PR)
```

- **Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- Newest version on top; newest entry first within a version.
- **Version bump:** patch for fixes, minor for features, major for breaking
  changes.
- _Open question for the team:_ bump in the feature branch vs. on `19.0` after
  merge. Both patterns exist today — let's settle it here.

## Running locally

### Pre-commit (CI-matching container)

Run the same hooks CI runs, on your changed files, before pushing:

```bash
/Users/<you>/Projects/ci-local/run.sh OpenSPP2 --files <changed files>
# regenerate READMEs when a readme/ fragment changed:
/Users/<you>/Projects/ci-local/run.sh OpenSPP2 oca-gen-addon-readme --all-files --hook-stage manual
```

Hooks include: `ruff` / `ruff-format`, `pylint_odoo`, the OCA checks, the
`openspp-*` custom checks (naming, XML IDs, ACL, PII-in-logs, performance,
Odoo-19 py/xml, API-auth), `gitleaks`, `bandit`, `semgrep`.

### Module tests (Docker)

```bash
cd OpenSPP2
docker compose exec -T db psql -U odoo -d postgres -c "CREATE DATABASE test_MODULE;"
docker compose run --rm --entrypoint "" test \
  /opt/odoo/odoo/odoo-bin \
  --addons-path=/opt/odoo/odoo/addons,/opt/odoo/odoo/odoo/addons,/mnt/extra-addons/openspp,/mnt/extra-addons/server-ux,/mnt/extra-addons/server-tools,/mnt/extra-addons/queue,/mnt/extra-addons/odoo-job-worker,/mnt/extra-addons/server-backend,/mnt/extra-addons/rest-framework,/mnt/extra-addons/muk-it \
  -d test_MODULE --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --stop-after-init --no-http -i MODULE --test-tags /MODULE --log-level=test 2>&1 | tail -80
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS test_MODULE;"
```

Look for the summary line: `0 failed, 0 error(s) of N tests`.
