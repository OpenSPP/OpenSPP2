Publishable statistics layer that connects CEL variables to presentation contexts
(GIS maps, dashboards, APIs, reports). Each statistic wraps a CEL variable with
format, privacy thresholds, and per-context overrides so a single computation
can be published in multiple places with different labels and suppression rules.

### Key Capabilities

- Bind a CEL variable to one or more publication channels (GIS, dashboard, API, report)
- Apply k-anonymity small-cell suppression with configurable thresholds per context
- Override labels, formats, icons, and color thresholds for each publication context
- Query published statistics by context and category
- Serialize statistics to dictionaries for API and UI consumption

### Key Models

| Model                  | Description                                            |
| ---------------------- | ------------------------------------------------------ |
| `spp.statistic`        | A publishable statistic linked to a CEL variable       |
| `spp.statistic.context`| Per-context presentation and privacy overrides         |

### Configuration

After installing:

1. Create statistics via the Studio UI (requires `spp_statistic_studio`) or programmatically
2. Link each statistic to an active CEL variable
3. Enable publication flags (`is_published_gis`, `is_published_dashboard`, etc.)
4. Optionally add context-specific overrides for label, format, and suppression threshold

### UI Location

No standalone menu; configuration UI is provided by `spp_statistic_studio`.

### Security

| Group                              | Access    |
| ---------------------------------- | --------- |
| `base.group_user`                  | Read      |
| `spp_security.group_spp_admin`     | Full CRUD |

### Extension Points

- Override `apply_suppression()` to implement custom privacy rules
- Override `get_context_config()` to add context-specific logic
- Inherit `spp.statistic` to add domain-specific publication flags

### Dependencies

`spp_cel_domain`, `spp_metrics_core`, `spp_security`
