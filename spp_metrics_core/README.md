# OpenSPP Metrics Core

Shared foundation for all metrics (statistics, simulation metrics, etc.) in OpenSPP.

## Overview

`spp_metrics_core` provides the base model and categorization system that eliminates duplication of genuinely shared
fields across different metric types. All domain modules (statistics, simulations, dashboards) inherit from the base
model and add their own computation-specific fields.

## Architecture

```
spp.metric.base (AbstractModel)
    │
    ├── spp.statistic (extends with publication flags)
    ├── spp.simulation.metric (extends with scenario-specific fields)
    └── [Your custom metric models]
```

## Models

### spp.metric.base

Abstract model providing genuinely shared fields for all metric types.

Concrete models define their own computation-specific fields (metric_type, format, expressions, etc.) since these vary
incompatibly between metric types.

**Identity**

- `name` - Technical identifier (e.g., 'children_under_5')
- `label` - Human-readable display label (translated)
- `description` - Detailed description (translated)

**Presentation**

- `unit` - Unit of measurement (e.g., 'people', 'USD', '%')
- `decimal_places` - Decimal precision for display

**Categorization**

- `category_id` - Many2one to `spp.metric.category`

**Metadata**

- `sequence` - Display order within category
- `active` - Inactive metrics are hidden

**What's NOT in the base** (defined by concrete models):

- `metric_type` / `format` - Each concrete model defines its own selections
- `cel_expression` / `variable_id` - Computation approaches vary by type
- `aggregation` - Only relevant for certain metric types

### spp.metric.category

Shared categorization for all metric types:

- `name` - Category name (e.g., "Population")
- `code` - Technical code (e.g., "population")
- `description` - Category description
- `sequence` - Display order
- `parent_id` - Optional parent category for hierarchical organization

## Default Categories

- **Population** - Population counts and demographics
- **Coverage** - Program coverage and reach metrics
- **Targeting** - Targeting accuracy and fairness metrics
- **Distribution** - Distribution and entitlement metrics

## Defining Metrics

Since `spp.metric.base` is an **AbstractModel**, it does not store data directly. Domain modules define concrete metrics
by inheriting from the base:

- `spp_statistic` - Defines published statistics
- `spp_simulation` - Defines simulation metrics
- Custom modules - Define domain-specific metrics

See the [Usage](#usage) section below for examples.

## Usage

### Creating Custom Metrics

Inherit from `spp.metric.base` to create domain-specific metrics:

```python
class CustomMetric(models.Model):
    _name = "custom.metric"
    _inherit = ["spp.metric.base"]
    _description = "Custom Metric Type"

    # Shared fields inherited from base:
    # - name, label, description
    # - unit, decimal_places
    # - category_id, sequence, active

    # Define your computation-specific fields
    metric_type = fields.Selection([...])  # Your type selections
    computation_field = fields.Text()       # Your computation approach

    # Add domain-specific fields
    custom_field = fields.Boolean()
    custom_config = fields.Text()
```

### Using Categories

Reference categories in your metrics:

```xml
<record id="my_custom_metric" model="custom.metric">
    <field name="name">my_metric</field>
    <field name="label">My Custom Metric</field>
    <field name="category_id" ref="spp_metrics_core.category_population"/>
</record>
```

### Creating Custom Categories

Add domain-specific categories:

```xml
<record id="category_health" model="spp.metric.category">
    <field name="name">Health</field>
    <field name="code">health</field>
    <field name="description">Health-related metrics</field>
    <field name="sequence">50</field>
</record>
```

## Migration

### From spp_statistic.category

The migration automatically renames `spp.statistic.category` to `spp.metric.category` while preserving all data and
external references.

**Before**:

```python
category = env['spp.statistic.category'].search([...])
```

**After**:

```python
category = env['spp.metric.category'].search([...])
```

See [Migration Guide](../../docs/migration/statistics-refactoring.md) for details.

## Benefits

1. **No Duplication**: Genuinely shared fields defined once, reused everywhere
2. **Model-Specific Freedom**: Each concrete model defines its own computation fields without conflicts
3. **Consistent UI**: Common fields (name, label, category) display the same way
4. **Shared Categories**: One categorization system for all metrics
5. **Future-Proof**: New metric types easily add their own computation approaches

## Dependencies

- `base` - Odoo core

## Used By

- `spp_metrics_services` - Aggregation and computation services
- `spp_statistic` - Published statistics
- `spp_simulation` - Simulation metrics
- Domain modules with custom metrics

## Architecture Documentation

See [Statistics System Architecture](../../docs/architecture/statistics-systems.md) for the complete system design.

## License

LGPL-3
