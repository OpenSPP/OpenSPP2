# SPDCI Demo — Modules & Reset Procedure

Reference sheet for resetting both OpenSPP instances (SP + DR) from scratch and
reinstalling the modules required for the federated CEL ↔ DCI eligibility demo
(ADR-024).

The SP container plays the Social Protection platform that runs CEL eligibility rules;
the DR container plays the standalone Disability Registry that answers `has_disability`
lookups over DCI. They share the same `db` Postgres container but use different
databases (`openspp` vs. `openspp_dr`).

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

## Full reset procedure

### 1. Stop and wipe both instances

```bash
# Stop the DR first (depends on SP's shared network)
docker compose -f docker-compose.dr.yml down -v

# Stop SP + jobworker + db (the -v wipes the SP filestore volume)
./spp stop
docker compose down -v
```

### 2. Drop the DR database

`docker compose down -v` removes the SP filestore volume but the `db` Postgres container
is shared and only the `openspp` database is re-created by the SP boot. The DR's
`openspp_dr` database lives in the same Postgres and needs an explicit drop:

```bash
./spp start                                   # brings up db + SP
docker compose exec db dropdb -U odoo --if-exists openspp_dr
```

### 3. Re-init the SP

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

### 4. Re-init the DR

```bash
# DR uses a separate compose. Its default init module is exactly what
# we need; override only if you want to add demo registrants alongside
# the server endpoint.
docker compose -f docker-compose.dr.yml up -d
```

Default init is `spp_dci_server_disability` (see `docker-compose.dr.yml` line 80).
Override with `ODOO_DR_INIT_MODULES=...` only if you need additional modules — for the
federated demo, the default is enough because the demo-setup script seeds the partners +
disability assessments after boot.

---

## Post-install wiring

After both containers are up, the SP needs a couple of records the data XML does not
seed automatically (because the SP doesn't know your DR's URL or your demo CEL rule):

### 4a. Point the SP's DR data source at the running DR

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

### 4b. Seed demo registrants on both sides

Edit the persona list in `scripts/demo/setup_spdci_demo.py` if needed, then run it
inside each container. The script is idempotent (re-runs update existing partners by
UIN).

```bash
# SP side: enrolls 15 IND-NSR-XXXX partners into program id=1 as draft.
docker compose exec openspp-dev odoo shell -d openspp --no-http \
    < scripts/demo/setup_spdci_demo.py

# DR side: creates approved disability assessments for 8 of those UINs.
docker compose -f docker-compose.dr.yml exec openspp-dr \
    odoo shell -d openspp_dr --no-http \
    < scripts/demo/setup_spdci_demo.py
```

The same file detects which side it's running on by inspecting installed modules — no
flag needed.

### 4c. (Optional) Allow unsigned DCI requests for the demo

The DR enforces DCI envelope signature + bearer auth by default. For the demo, relax
both via the system parameters:

```bash
docker compose -f docker-compose.dr.yml exec openspp-dr \
    odoo shell -d openspp_dr --no-http <<'PY'
P = env["ir.config_parameter"].sudo()
P.set_param("dci.allow_unsigned_requests", "true")
P.set_param("dci.bypass_bearer_auth", "true")
env.cr.commit()
PY
```

Production: register the SP's public key in the DR's DCI Sender Registry instead.

### 4d. Operator-driven SR import (alternative to the seed script)

After the SP is up, an operator can populate registrants via the wizard under **Registry
→ Import from External Registry**:

- Source Registry: select **Social Registry** (the only option).
- Discovery: Range sweep `IND-NSR-` `0001..0015` (pad=4).
- Auto-enroll into program: pick the demo program if you want memberships created in one
  step.
- Preview → Import Selected.

This produces the same SP-side state as `setup_spdci_demo.py`, minus the DR-side
assessments (DR seeding still needs the script).

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
