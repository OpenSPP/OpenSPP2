FastAPI-based REST endpoints for simulation scenario management, execution,
comparison, and population aggregation. Provides external systems (dashboards, mobile
apps, third-party tools) programmatic access to the simulation and analytics engine.

### Key Capabilities

- CRUD operations on simulation scenarios with entitlement rules
- Execute simulations and retrieve run results (distribution, fairness, geographic data)
- Compare multiple simulation runs side-by-side with overlap analysis
- Compute population aggregation with demographic breakdowns via the aggregation engine
- List available demographic dimensions and scenario templates
- Convert simulation scenarios to real programs

### API Endpoints

| Method | Path                                         | Description                     |
| ------ | -------------------------------------------- | ------------------------------- |
| GET    | `/simulation/scenarios`                      | List scenarios                  |
| POST   | `/simulation/scenarios`                      | Create scenario                 |
| GET    | `/simulation/scenarios/{id}`                 | Get scenario details            |
| PUT    | `/simulation/scenarios/{id}`                 | Update draft scenario           |
| DELETE | `/simulation/scenarios/{id}`                 | Archive scenario                |
| POST   | `/simulation/scenarios/{id}/ready`           | Mark scenario ready             |
| POST   | `/simulation/scenarios/{id}/run`             | Execute simulation              |
| POST   | `/simulation/scenarios/{id}/convert-to-program` | Convert to program           |
| GET    | `/simulation/runs`                           | List runs                       |
| GET    | `/simulation/runs/{id}`                      | Get run with optional details   |
| POST   | `/simulation/comparisons`                    | Create run comparison           |
| GET    | `/simulation/comparisons/{id}`               | Get comparison                  |
| GET    | `/simulation/templates`                      | List scenario templates         |
| POST   | `/aggregation/compute`                       | Compute population aggregation  |
| GET    | `/aggregation/dimensions`                    | List demographic dimensions     |

### OAuth Scopes

| Scope                 | Operations                          |
| --------------------- | ----------------------------------- |
| `simulation:read`     | List/get scenarios, runs, templates |
| `simulation:write`    | Create/update/archive scenarios     |
| `simulation:execute`  | Run simulations                     |
| `simulation:convert`  | Convert scenario to program         |
| `aggregation:read`    | Compute aggregation, list dimensions|

### UI Location

No standalone menu; API-only module.

### Dependencies

`spp_api_v2`, `spp_simulation`, `spp_aggregation`
