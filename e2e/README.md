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

Instead of installing Node/Playwright locally, you can run the suite inside a
container defined in the repo root's `docker-compose.yml`:

```bash
docker compose --profile e2e up -d
docker compose --profile e2e run --rm e2e-runner
```

The first command brings up `db` + `openspp` and waits for `openspp` to report
healthy. The second builds `e2e/Dockerfile` and runs `npx playwright test`
inside it, pointed at the already-running `openspp` service over the shared
Docker network (`ODOO_URL=http://openspp:8069`).

Because `openspp`'s healthcheck already guarantees a fresh stack before
`e2e-runner` starts — and because that container has no Docker CLI/socket to
run `docker compose` with — `resetStack()` skips its own teardown/rebuild
whenever `E2E_SKIP_STACK_RESET=true` is set (already configured on the
`e2e-runner` service). It only waits for health there.

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
