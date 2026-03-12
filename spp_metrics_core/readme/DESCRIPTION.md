Unified metric foundation providing abstract base models for statistics, simulations, and reporting across OpenSPP modules.

### Key Capabilities

- Abstract base model for defining reusable metrics with label, unit, and decimal precision
- Hierarchical metric categories with unique code constraints
- Category tree with parent-child recursion prevention
- Default metric categories for population, coverage, targeting, and distribution

### Key Models

| Model                 | Type     | Description                                      |
| --------------------- | -------- | ------------------------------------------------ |
| `spp.metric.base`     | Abstract | Base fields and logic inherited by concrete metrics |
| `spp.metric.category` | Concrete | Hierarchical grouping of metrics by domain        |

### Configuration

No configuration required. Default categories are created via data files on install.

### Dependencies

`base`
