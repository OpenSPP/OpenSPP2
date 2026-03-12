Shared service layer providing demographic dimensions, fairness analysis, distribution statistics, privacy enforcement, and breakdown computation for OpenSPP aggregation and reporting modules.

### Key Capabilities

- Define demographic dimensions (gender, age group, disability) as field-based or CEL expression-based
- Compute fairness metrics with disparity ratios and equity scores
- Calculate distribution statistics including Gini coefficient, Lorenz curve, percentiles, and standard deviation
- Enforce k-anonymity privacy with complementary suppression to prevent differencing attacks
- Compute multi-dimensional breakdowns of registrant populations
- Cache dimension evaluations using Odoo ORM cache for performance

### Key Models

| Model                          | Type     | Description                                          |
| ------------------------------ | -------- | ---------------------------------------------------- |
| `spp.demographic.dimension`    | Concrete | Configurable demographic dimensions for breakdowns   |
| `spp.metrics.dimension.cache`  | Abstract | ORM-cached dimension evaluation service              |
| `spp.metrics.fairness`         | Abstract | Fairness and equity analysis service                 |
| `spp.metrics.distribution`     | Abstract | Distribution statistics (Gini, Lorenz, percentiles)  |
| `spp.metrics.privacy`          | Abstract | K-anonymity enforcement with complementary suppression |
| `spp.metrics.breakdown`        | Abstract | Multi-dimensional population breakdown service       |

### Configuration

- Demographic dimensions are managed via **Settings > Aggregation > Demographic Dimensions**
- Default dimensions for gender and age group are created on install
- K-anonymity threshold defaults to 5 (configurable per access rule)

### Security

| Group              | Access                                          |
| ------------------ | ----------------------------------------------- |
| `base.group_user`  | Read-only access to demographic dimensions      |
| `base.group_system`| Full CRUD access to demographic dimensions      |

### Dependencies

`base`, `spp_cel_domain`, `spp_area`, `spp_registry`
