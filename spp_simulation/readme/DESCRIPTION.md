# Targeting Simulation & Fairness Analysis

Simulate targeting scenarios, analyze fairness and distribution, and compare
different targeting strategies before committing to criteria.

## Key Features

- **Scenario Builder**: Define targeting criteria using CEL expressions with
  live preview counts
- **Template Library**: Pre-built templates for common targeting patterns
  (elderly pension, female-headed households, etc.)
- **Distribution Analysis**: Gini coefficient, Lorenz curve, percentile
  breakdown
- **Fairness Analysis**: Disparity ratios across gender, disability, location
  with traffic-light status indicators
- **Targeting Efficiency**: Confusion matrix, leakage rate, undercoverage
  against ideal populations
- **Budget Simulation**: Fixed cap and proportional reduction strategies
- **Scenario Comparison**: Side-by-side comparison of multiple targeting
  approaches with overlap analysis
- **Custom Metrics**: Define CEL-based aggregate, coverage, and ratio metrics

## Privacy

Only aggregated counts, percentages, and metrics are stored. No individual
beneficiary records are persisted in simulation results.

## Models

| Model | Description |
|-------|-------------|
| `spp.simulation.scenario.template` | Pre-built targeting scenario templates |
| `spp.simulation.scenario` | Targeting scenario definitions |
| `spp.simulation.entitlement.rule` | Amount calculation rules |
| `spp.simulation.run` | Aggregated simulation results (non-deletable) |
| `spp.simulation.comparison` | Side-by-side run comparisons |
| `spp.simulation.metric` | Custom evaluation metrics |

## Security Groups

| Group | Access |
|-------|--------|
| Simulation Viewer | Read-only access to all simulation data |
| Simulation Officer | Create/edit scenarios, run simulations |
| Simulation Manager | Full access including comparisons and archiving |

## Menu Path

Social Protection > Simulation > Scenarios / Results / Comparisons

Configuration: Social Protection > Simulation > Configuration > Templates / Custom Metrics
