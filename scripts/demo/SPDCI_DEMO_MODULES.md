# SPDCI Demo — Modules & SP Reset Procedure

Reference sheet for resetting the **SP** instance only (DR stays up) and reinstalling
the modules required for the federated CEL ↔ DCI eligibility demo (ADR-024).

The SP container plays the Social Protection platform that runs CEL eligibility rules;
the DR container plays the standalone Disability Registry that answers `has_disability`
lookups over DCI. They share the same `db` Postgres container but use different
databases (`openspp` vs. `openspp_dr`).

This doc covers the **SP-only reset** flow: the DR's `openspp_dr` database, its 8 seeded
disability assessments, and its DCI-server config are preserved across the reset, so
only the SP needs to be re-installed and re-pointed at the still-running DR. For
first-time setup of both sides (or a full both-instances rebuild), follow the expanded
recipe in `docker-compose.dr.yml`'s header comment and run the seed script on both
sides.

---

## Top-level modules to install

You only need to install the **leaf modules** below — Odoo's dependency solver pulls in
everything else (`spp_cel_domain`, `spp_dci_client`, `spp_dci_server`, `spp_registry`,
`spp_vocabulary`, `spp_programs`, `spp_studio`, etc.).

### SP container (`openspp` database)

| Module               | What it provides                                                                                                                                              |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `spp_dci_openspp_dr` | Preset that wires the `has_disability` CEL variable to the OpenSPP-DR over DCI. Brings in `spp_cel_dci_bridge` and `spp_dci_client_dr`.                       |
| `spp_dci_openg2p`    | Preset that wires the `is_poor` CEL variable to a DCI-compliant Social Registry (income_level → is_poor). Also hosts the **SR-import wizard** under Registry. |

### DR container (`openspp_dr` database)

| Module                      | What it provides                                                                                                                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `spp_dci_server_disability` | DCI-server endpoint that answers `/dci_api/v1/disability/registry/sync/search` and exposes the disability assessment data. Brings in `spp_dci_server`, `spp_registry`, `spp_vocabulary`. |

### Dependency tree (informational)

```
SP container:
  spp_dci_openspp_dr
   └── spp_cel_dci_bridge
   │     ├── spp_cel_domain
   │     ├── spp_dci_client
   │     ├── spp_dci_client_dr
   │     ├── spp_dci_client_crvs
   │     ├── spp_dci_client_ibr
   │     ├── spp_programs
   │     └── spp_studio
   ├── spp_dci_client_dr
   └── spp_vocabulary

  spp_dci_openg2p
   ├── spp_cel_dci_bridge   (already pulled in above)
   ├── spp_vocabulary
   └── spp_registry

DR container:
  spp_dci_server_disability
   ├── spp_dci_server
   │     └── spp_dci
   ├── spp_registry
   └── spp_vocabulary
```

---

## SP-only reset procedure

Resets the SP database (`openspp`) from scratch. **The DR stays up untouched** — its
`openspp_dr` database and the 8 seeded disability assessments are preserved, so the SP's
`has_disability` lookups will keep working against the still-live DR once the SP
re-installs and re-points at it.

### 1. Stop the SP (keep DR running)

```bash
./spp stop
docker compose down -v   # removes SP filestore volume
```

Verify the DR is still up — it shares the network but has its own container and DB:

```bash
docker compose -f docker-compose.dr.yml ps     # openspp-dr should be Up (healthy)
```

If you wiped the SP network (rare), the DR will have lost its external-network link and
you'll need to restart it:

```bash
docker compose -f docker-compose.dr.yml up -d
```

### 2. Re-init the SP

```bash
# Set the SP's init modules and start. The two presets pull every
# dependency listed in the tree above.
export ODOO_INIT_MODULES="spp_dci_openspp_dr,spp_dci_openg2p"
./spp start
```

Watch the boot log; it will exit cleanly when install finishes:

```bash
docker compose logs -f openspp-dev | grep -E "Modules loaded|ERROR|init "
```

---

## Post-install wiring (SP side only)

After the SP is back up, it needs a couple of records the data XML does not seed
automatically (because the SP doesn't know your DR's URL):

### 2a. Point the SP's DR data source at the running DR

The `spp_dci_openspp_dr` preset creates an `spp.dci.data.source` record with a
placeholder URL. Set it to the in-network DR hostname:

```bash
docker compose exec openspp-dev odoo shell -d openspp --no-http <<'PY'
src = env.ref("spp_dci_openspp_dr.openspp_dr_source")
src.write({
    "base_url": "http://openspp-dr:8069",
    "active": True,
})
env.cr.commit()
print(f"DR source -> {src.base_url}")
PY
```

### 2b. Seed SP-side registrants

Two options — pick one.

**Option A: seed script (matches prior demo runs)**

```bash
# Enrolls 15 IND-NSR-XXXX partners into program id=1 as draft.
docker compose exec openspp-dev odoo shell -d openspp --no-http \
    < scripts/demo/setup_spdci_demo.py
```

The script is idempotent (re-runs update existing partners by UIN). It also detects when
run on the DR and seeds the disability assessments instead — but **don't run it on the
DR this time**; the DR already has its 8 assessments from the previous run.

**Option B: SR-import wizard (operator-driven, recommended for the demo presentation)**

After the SP is up, an operator can populate registrants via the wizard under **Registry
→ Import from External Registry**:

- Source Registry: select **Social Registry** (the only option).
- Discovery: Range sweep `IND-NSR-` `0001..0015` (pad=4).
- Auto-enroll into program: pick the demo program if you want memberships created in one
  step.
- Preview → Import Selected.

This produces the same SP-side state as the seed script.

### 2c. DR config — NO ACTION NEEDED

The DR's previous setup is preserved:

- `dci.allow_unsigned_requests=true` system parameter (set in a prior run)
- `dci.bypass_bearer_auth=true` system parameter (set in a prior run)
- 8 approved disability assessments seeded against `IND-NSR-0001`/`0003`/`0005`/…

Skip the optional bypass and DR seeding steps from earlier docs — they remain in effect
across SP wipes because the DR database is untouched.

---

## Reset between demo runs (no reinstall)

If you want to re-run the demo without wiping the database:

```bash
# Resets the 15 memberships to draft and wipes the DCI cache, so the
# next eligibility evaluation goes through to DR + SR again.
docker compose exec openspp-dev odoo shell -d openspp --no-http \
    < scripts/demo/reset_spdci_demo.py
```

---

## Sanity checks before the demo

| Check                             | Command                                                                                                                                                                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SP installed modules look right   | `docker compose exec openspp-dev odoo shell -d openspp --no-http -c "print([m.name for m in env['ir.module.module'].search([('name','in',['spp_dci_openspp_dr','spp_dci_openg2p']), ('state','=','installed')])])"`              |
| DR installed modules look right   | `docker compose -f docker-compose.dr.yml exec openspp-dr odoo shell -d openspp_dr --no-http -c "print([m.name for m in env['ir.module.module'].search([('name','=','spp_dci_server_disability'), ('state','=','installed')])])"` |
| SP can resolve `openspp-dr`       | `docker compose exec openspp-dev getent hosts openspp-dr`                                                                                                                                                                        |
| DR endpoint is up                 | `curl -sS http://localhost:8070/web/health`                                                                                                                                                                                      |
| SR-import wizard finds the source | Open Registry → Import from External Registry. Source Registry should pre-fill **Social Registry**.                                                                                                                              |
| 15 demo personas seeded           | SP: `SELECT count(*) FROM res_partner WHERE is_registrant = true;` (expect 15)                                                                                                                                                   |
| 8 DR assessments seeded           | DR: `SELECT count(*) FROM spp_disability_assessment WHERE state='approved';` (expect 8)                                                                                                                                          |

---

## Quick reference: container/database names

| Container              | Service       | Database     | DB host            | Network alias |
| ---------------------- | ------------- | ------------ | ------------------ | ------------- |
| openspp2-openspp-dev-1 | `openspp-dev` | `openspp`    | `db:5432` (shared) | `openspp-dev` |
| openspp-dr             | `openspp-dr`  | `openspp_dr` | `db:5432` (shared) | `openspp-dr`  |
| openspp2-db-1          | `db`          | both         | n/a                | `db`          |
| openspp2-jobworker-1   | `jobworker`   | `openspp`    | `db:5432`          | —             |

UI ports:

- SP: dynamic (`./spp url`) — usually `http://localhost:<random>`
- DR: `http://localhost:8070` (admin/admin)

In-container DNS:

- SP → DR: `http://openspp-dr:8069`
- DR → SP: not used in this demo topology.
