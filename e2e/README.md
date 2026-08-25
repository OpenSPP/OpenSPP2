# E2E Tests

Playwright-based end-to-end tests for OpenSPP.

## Prerequisites

- Docker running with WSL Ubuntu
- Node.js 20+ installed
- Playwright and Chromium installed

## First-time setup

```bash
cd e2e
npm install
npx playwright install chromium --with-deps
```

## Running tests

```bash
cd e2e
npx playwright test --headed
```

Tests run sequentially (1 worker). Each test file resets the database before running.

## Test files

| File                                     | Module                        | Description                                                     |
| ---------------------------------------- | ----------------------------- | --------------------------------------------------------------- |
| `01-spp-starter-spmis.spec.ts`           | `spp_starter_sp_mis`          | Installs OpenSPP Starter SP-MIS and verifies nav menus          |
| `02-spp-starter-farmer-registry.spec.ts` | `spp_starter_farmer_registry` | Installs OpenSPP Starter Farmer Registry and verifies nav menus |

## How each test works

1. `beforeAll` — tears down and rebuilds a fresh Docker stack via
   `docker compose --profile ui down -v && docker compose --profile ui up -d`
2. Waits for Odoo to be healthy at `http://localhost:8069/web/health`
3. Logs in as `admin` / `admin`
4. Goes to Apps, removes the preset filter, searches by module technical name
5. Clicks Activate and waits for installation to complete
6. Waits 1 minute for nav menus to settle
7. Verifies nav menus are present and takes a screenshot

## Running tests in a container (`e2e-runner`)

Instead of installing Node/Playwright locally, you can run the suite inside a container
defined in the repo root's `docker-compose.yml`:

```bash
docker compose --profile e2e up -d
docker compose --profile e2e run --rm e2e-runner
```

The first command brings up `db` + `openspp` and waits for `openspp` to report healthy.
The second builds `e2e/Dockerfile` and runs `npx playwright test` inside it, pointed at
the already-running `openspp` service over the shared Docker network
(`ODOO_URL=http://openspp:8069`).

Because `openspp`'s healthcheck already guarantees a fresh stack before `e2e-runner`
starts — and because that container has no Docker CLI/socket to run `docker compose`
with — `resetStack()` skips its own teardown/rebuild whenever
`E2E_SKIP_STACK_RESET=true` is set (already configured on the `e2e-runner` service). It
only waits for health there.

## Why `docker compose down -v && up` instead of `spp resetdb`

The `spp` CLI has a `resetdb` command that resets only the database (faster, keeps
containers running). However, this workflow is designed to run automatically on every
merge to `branch 19.0` via GitHub Actions. In that context, a full
`docker compose down -v && up` is intentional because:

- It pulls and uses the latest image built from the merged code
- It guarantees no leftover state from previous runs (volumes, cached data)
- It ensures every test run reflects exactly what was merged

Use `spp resetdb` for local dev iteration only. Do not replace the `docker compose`
reset in `helpers.ts` for CI purposes.

## Known frontend timing races (why `slowMo: 500` is always-on)

`playwright.config.ts` runs every action with a fixed 0.5s delay. This is
deliberate and always-on — not opt-in for debugging — because running this
suite without it doesn't just make tests faster, it reliably (not rarely)
exposes real races in Odoo's own OWL frontend. Confirmed via 5 clean runs
with the delay vs. repeated failures without it, on the same code:

1. **Navbar "Configuration" button ambiguity.** Switching between two apps
   that each have a same-named top-level Configuration menu — e.g.
   `spp_approval`'s `menu_approval_config`
   (`spp_approval/views/menus.xml:38-44`) and `spp_change_request_v2`'s
   `menu_change_request_config`
   (`spp_change_request_v2/views/menus.xml:59-65`) — can transiently leave
   both apps' "Configuration" buttons mounted in the DOM at once. Odoo's
   navbar is a single persistent OWL component; switching apps means a keyed
   diff removes the old section and inserts the new one, and that isn't
   guaranteed atomic with the rest of the app-switch flow. A `getByRole`
   locator that resolves to 2 elements throws a strict-mode violation instead
   of picking one.
2. **Vocabulary "Add a line" row-insertion race.** Filling a newly-added row
   immediately via `page.locator(".o_data_row").last()` can race Odoo's own
   row insertion, scrambling which code/display pair lands in which row.
3. **sessionStorage action-restore race.** Odoo's webclient persists the last
   visited `current_action`/`menu_id` to sessionStorage to restore your place
   on reload. On a fresh login, it can read that stale value and render it
   instead of waiting for the server's actual default-action response —
   landing on a leftover page from a previous session.

None of these are reachable by an actual human — nobody clicks fast enough to
land inside a sub-100ms rendering window. The delay isn't papering over a
missing wait in this suite; it's keeping tests running at a human-realistic
pace so they test real user-facing behavior instead of Odoo's frontend
internals. **Do not make this opt-in again** without addressing all three
races directly (e.g. scoping ambiguous locators to the currently-active app,
waiting for the previous app's elements to actually detach, or asserting the
row count before filling a newly-added row).

## Adding new tests

When adding a new test to any spec file:

1. Use `test.describe.serial` and share a single `page` across all tests via
   `let page: Page` at the describe scope
2. Number tests sequentially (`01`, `02`, `03` …) so the report shows them in order
3. **Always update the comment block at the top of the spec file** to include the new
   test — one line per test in the format:
   ```
   //   NN - Plain-language description of what the test does
   ```
4. Use codegen to record actions (`npx playwright codegen http://localhost:8069`), then
   polish the output — remove redundant clicks, replace CSS locators with
   role/label/placeholder locators, add `waitForLoadState`, and add `expect` assertions
   to verify the result was saved

## Reports

After a run, open the HTML report:

```bash
cd e2e
npm run report
```

Screenshots on failure and post-install screenshots are saved in `e2e/reports/`.
