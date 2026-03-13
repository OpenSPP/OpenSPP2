Shared foundation for all metric types in OpenSPP (statistics, simulation metrics,
and custom domain metrics). Provides an abstract base model with identity,
presentation, and categorization fields, plus a hierarchical category system.
Concrete metric modules inherit from the base and add their own computation fields.

### Key Capabilities

- Abstract base model (`spp.metric.base`) with shared identity, presentation, and metadata fields
- Hierarchical metric category system with unique codes
- Default categories: Demographics, Vulnerability, Programs, Geographic, Economic, Fairness

### Key Models

| Model                | Description                                           |
| -------------------- | ----------------------------------------------------- |
| `spp.metric.base`    | Abstract model inherited by all concrete metric types |
| `spp.metric.category`| Hierarchical categorization for organizing metrics    |

### Configuration

After installing, default metric categories are created automatically. Add custom
categories via **Settings > Technical > Metric Categories** or in XML data files.

### UI Location

No standalone menu; library module consumed by `spp_statistic`, `spp_simulation`,
and other metric modules.

### Security

| Group              | Access                         |
| ------------------ | ------------------------------ |
| `base.group_user`  | Read categories                |
| `base.group_system`| Full CRUD on categories        |

### Extension Points

- Inherit `spp.metric.base` to create domain-specific metric models
- Add custom categories via XML data records referencing `spp.metric.category`

### Dependencies

`base`
