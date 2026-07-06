Shared computation services for fairness analysis, distribution statistics,
demographic breakdowns, privacy enforcement, and dimension caching. These abstract
services are consumed by `spp_aggregation`, `spp_simulation`, GIS APIs, and
dashboards. No standalone UI; provides only programmatic service models.

### Key Capabilities

- Fairness analysis: compute equity scores and disparity ratios across demographic dimensions
- Distribution statistics: Gini coefficient, Lorenz curve, percentiles, descriptive stats
- Demographic breakdowns: multi-dimensional grouping with cached CEL evaluations
- Privacy enforcement: k-anonymity with complementary suppression to prevent differencing attacks
- Configurable demographic dimensions: field-based or CEL expression-based

### Key Models

| Model                            | Description                                          |
| -------------------------------- | ---------------------------------------------------- |
| `spp.demographic.dimension`      | Configurable dimension for breakdowns (field or CEL) |
| `spp.metrics.fairness`           | Abstract service: equity/parity analysis             |
| `spp.metrics.distribution`       | Abstract service: distribution statistics            |
| `spp.metrics.breakdown`          | Abstract service: multi-dimensional grouping         |
| `spp.metrics.privacy`            | Abstract service: k-anonymity enforcement            |
| `spp.metrics.dimension.cache`    | Abstract service: dimension evaluation cache         |

### Configuration

After installing:

1. Default demographic dimensions (gender, disability, age group) are created via data file
2. Add custom dimensions at **Settings > Aggregation > Configuration > Demographic Dimensions**
   (menu provided by `spp_aggregation`)

### UI Location

No standalone menu; extends existing views. Dimension management UI provided
by `spp_aggregation`.

### Security

| Group              | Access                              |
| ------------------ | ----------------------------------- |
| `base.group_user`  | Read demographic dimensions         |
| `base.group_system`| Full CRUD on demographic dimensions |

### Extension Points

- Override `_analyze_dimension()` in `spp.metrics.fairness` for custom analysis logic
- Add new dimension types by extending `spp.demographic.dimension`
- Override `enforce()` in `spp.metrics.privacy` for custom suppression strategies

### Dependencies

`base`, `spp_cel_domain`, `spp_area`, `spp_registry`
