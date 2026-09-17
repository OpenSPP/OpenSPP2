## **Why is this change needed?**

## **How was the change implemented?**

## **New unit tests**

## **Unit tests executed by the author**

## **How to test manually**

## **Related links**

---

### Reviewer checklist

<!-- Full rules: see CLAUDE.md → "PR Review Checklist". Tick what applies. -->

- [ ] **Changelog + version** — every changed module has a `readme/HISTORY.md` entry **and** a matching `__manifest__.py` version bump; `README.rst`/`index.html` regenerated if a `readme/` fragment changed
- [ ] **Odoo 19** — `view_mode` uses `list` (not `tree`); no `attrs=`/`states=`
- [ ] **Security** — no PII/secrets in logs; API/DCI endpoints authenticated; parameterized SQL; new models have ACLs
- [ ] **Scope** — no unrelated changes bundled in
- [ ] **Tests** — affected module suite run locally (not just CI); pre-commit clean via `ci-local`
- [ ] **Runtime** — the changed path was actually exercised, not just read
